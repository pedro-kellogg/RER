"""
Real Exchange Rate (RER) app
----------------------------
Pulls monthly CPI and exchange-rate data from the IMF SDMX 3.0 API and computes
the bilateral real exchange rate between any two IMF economies (or the Euro area).

Definitions (Country 1 = home, Country 2 = foreign):
    S(t)        = units of Country 2 currency per 1 unit of Country 1 currency
    P1(t), P2(t) = monthly CPI of Country 1 and Country 2
    RER(t)      = S(t) * P1(t) / P2(t)
    RER*        = average of RER(t) over valid months in the selected sample
    Real Index  = 100 * RER(t) / RER*

IMF exchange rates are local currency units per USD (XDC per USD), so
    S(t) = (Country 2 units per USD) / (Country 1 units per USD).
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
BASE_URL = "https://api.imf.org/external/sdmx/3.0"
AGENCY = "IMF.STA"
START_MONTH = pd.Timestamp("1976-01-01")
CPI_KEY = "{iso}.{index_type}._T.IX.M"  # headline CPI, index, monthly
FX_KEY = "{iso}.XDC_USD.PA_RT.M"  # local currency per USD, period average, monthly
HEADERS = {
    "Accept": "application/xml",
    "User-Agent": "Kellogg-RER-Streamlit-App/1.0",
}
JUMP_THRESHOLD = 0.5  # flag month-over-month moves in S larger than 50%

# Economies with both monthly CPI and exchange-rate series in the IMF CPI and ER
# dataflows (names from the IMF country codelist; currency codes are labels only).
COUNTRIES = {
    "AFG": ("Afghanistan, Islamic Republic of", "AFN"),
    "ALB": ("Albania", "ALL"),
    "DZA": ("Algeria", "DZD"),
    "AGO": ("Angola", "AOA"),
    "AIA": ("Anguilla, United Kingdom-British Overseas Territory", "XCD"),
    "ATG": ("Antigua and Barbuda", "XCD"),
    "ARG": ("Argentina", "ARS"),
    "ARM": ("Armenia, Republic of", "AMD"),
    "ABW": ("Aruba, Kingdom of the Netherlands", "AWG"),
    "AUS": ("Australia", "AUD"),
    "AUT": ("Austria", "EUR"),
    "AZE": ("Azerbaijan, Republic of", "AZN"),
    "BHS": ("Bahamas, The", "BSD"),
    "BHR": ("Bahrain, Kingdom of", "BHD"),
    "BGD": ("Bangladesh", "BDT"),
    "BRB": ("Barbados", "BBD"),
    "BLR": ("Belarus, Republic of", "BYN"),
    "BEL": ("Belgium", "EUR"),
    "BLZ": ("Belize", "BZD"),
    "BEN": ("Benin", "XOF"),
    "BTN": ("Bhutan", "INR"),
    "BOL": ("Bolivia", "BOB"),
    "BIH": ("Bosnia and Herzegovina", "BAM"),
    "BWA": ("Botswana", "BWP"),
    "BRA": ("Brazil", "BRL"),
    "BRN": ("Brunei Darussalam", "BND"),
    "BGR": ("Bulgaria", "EUR"),
    "BFA": ("Burkina Faso", "XOF"),
    "BDI": ("Burundi", "BIF"),
    "CPV": ("Cabo Verde", "CVE"),
    "KHM": ("Cambodia", "KHR"),
    "CMR": ("Cameroon", "XAF"),
    "CAN": ("Canada", "CAD"),
    "CYM": ("Cayman Islands", "KYD"),
    "CAF": ("Central African Republic", "XAF"),
    "TCD": ("Chad", "XAF"),
    "CHL": ("Chile", "CLP"),
    "CHN": ("China, People's Republic of", "CNY"),
    "COL": ("Colombia", "COP"),
    "COM": ("Comoros, Union of the", "KMF"),
    "COD": ("Congo, Democratic Republic of the", "CDF"),
    "COG": ("Congo, Republic of", "XAF"),
    "CRI": ("Costa Rica", "CRC"),
    "HRV": ("Croatia, Republic of", "EUR"),
    "CUW": ("Curaçao, Kingdom of the Netherlands", "XCG"),
    "CYP": ("Cyprus", "EUR"),
    "CZE": ("Czech Republic", "CZK"),
    "CIV": ("Côte d'Ivoire", "XOF"),
    "DNK": ("Denmark", "DKK"),
    "DJI": ("Djibouti", "DJF"),
    "DMA": ("Dominica", "XCD"),
    "DOM": ("Dominican Republic", "DOP"),
    "ECU": ("Ecuador", "USD"),
    "EGY": ("Egypt, Arab Republic of", "EGP"),
    "SLV": ("El Salvador", "USD"),
    "GNQ": ("Equatorial Guinea, Republic of", "XAF"),
    "EST": ("Estonia, Republic of", "EUR"),
    "SWZ": ("Eswatini, Kingdom of", "SZL"),
    "ETH": ("Ethiopia, The Federal Democratic Republic of", "ETB"),
    "G163": ("Euro Area (EA)", "EUR"),
    "FJI": ("Fiji, Republic of", "FJD"),
    "FIN": ("Finland", "EUR"),
    "FRA": ("France", "EUR"),
    "GAB": ("Gabon", "XAF"),
    "GMB": ("Gambia, The", "GMD"),
    "GEO": ("Georgia", "GEL"),
    "DEU": ("Germany", "EUR"),
    "GHA": ("Ghana", "GHS"),
    "GRC": ("Greece", "EUR"),
    "GRL": ("Greenland", "DKK"),
    "GRD": ("Grenada", "XCD"),
    "GLP": ("Guadeloupe", "EUR"),
    "GTM": ("Guatemala", "GTQ"),
    "GIN": ("Guinea", "GNF"),
    "GNB": ("Guinea-Bissau", "XOF"),
    "GUY": ("Guyana", "GYD"),
    "HTI": ("Haiti", "HTG"),
    "HND": ("Honduras", "HNL"),
    "HKG": ("Hong Kong Special Administrative Region, People's Republic of China", "HKD"),
    "HUN": ("Hungary", "HUF"),
    "ISL": ("Iceland", "ISK"),
    "IND": ("India", "INR"),
    "IDN": ("Indonesia", "IDR"),
    "IRN": ("Iran, Islamic Republic of", "IRR"),
    "IRQ": ("Iraq", "IQD"),
    "IRL": ("Ireland", "EUR"),
    "ISR": ("Israel", "ILS"),
    "ITA": ("Italy", "EUR"),
    "JAM": ("Jamaica", "JMD"),
    "JPN": ("Japan", "JPY"),
    "JOR": ("Jordan", "JOD"),
    "KAZ": ("Kazakhstan, Republic of", "KZT"),
    "KEN": ("Kenya", "KES"),
    "KIR": ("Kiribati", "AUD"),
    "KOR": ("Korea, Republic of", "KRW"),
    "KOS": ("Kosovo, Republic of", "EUR"),
    "KWT": ("Kuwait", "KWD"),
    "KGZ": ("Kyrgyz Republic", "KGS"),
    "LAO": ("Lao People's Democratic Republic", "LAK"),
    "LVA": ("Latvia, Republic of", "EUR"),
    "LBN": ("Lebanon", "LBP"),
    "LSO": ("Lesotho, Kingdom of", "ZAR"),
    "LBR": ("Liberia", "LRD"),
    "LBY": ("Libya", "LYD"),
    "LTU": ("Lithuania, Republic of", "EUR"),
    "LUX": ("Luxembourg", "EUR"),
    "MAC": ("Macao Special Administrative Region, People's Republic of China", "MOP"),
    "MDG": ("Madagascar, Republic of", "MGA"),
    "MWI": ("Malawi", "MWK"),
    "MYS": ("Malaysia", "MYR"),
    "MDV": ("Maldives", "MVR"),
    "MLI": ("Mali", "XOF"),
    "MLT": ("Malta", "EUR"),
    "MTQ": ("Martinique", "EUR"),
    "MRT": ("Mauritania, Islamic Republic of", "MRU"),
    "MUS": ("Mauritius", "MUR"),
    "MEX": ("Mexico", "MXN"),
    "FSM": ("Micronesia, Federated States of", "USD"),
    "MDA": ("Moldova, Republic of", "MDL"),
    "MNG": ("Mongolia", "MNT"),
    "MNE": ("Montenegro", "EUR"),
    "MSR": ("Montserrat, United Kingdom-British Overseas Territory", "XCD"),
    "MAR": ("Morocco", "MAD"),
    "MOZ": ("Mozambique, Republic of", "MZN"),
    "MMR": ("Myanmar", "MMK"),
    "NAM": ("Namibia", "ZAR"),
    "NRU": ("Naoero, Republic of", "AUD"),
    "NPL": ("Nepal", "NPR"),
    "ANT": ("Netherlands Antilles", "ANG"),
    "NLD": ("Netherlands, The", "EUR"),
    "NCL": ("New Caledonia", "XPF"),
    "NZL": ("New Zealand", "NZD"),
    "NIC": ("Nicaragua", "NIO"),
    "NER": ("Niger", "XOF"),
    "NGA": ("Nigeria", "NGN"),
    "MKD": ("North Macedonia, Republic of", "MKD"),
    "NOR": ("Norway", "NOK"),
    "OMN": ("Oman", "OMR"),
    "PAK": ("Pakistan", "PKR"),
    "PLW": ("Palau, Republic of", "USD"),
    "PAN": ("Panama", "PAB"),
    "PNG": ("Papua New Guinea", "PGK"),
    "PRY": ("Paraguay", "PYG"),
    "PER": ("Peru", "PEN"),
    "PHL": ("Philippines", "PHP"),
    "POL": ("Poland, Republic of", "PLN"),
    "PRT": ("Portugal", "EUR"),
    "QAT": ("Qatar", "QAR"),
    "ROU": ("Romania", "RON"),
    "RUS": ("Russian Federation", "RUB"),
    "RWA": ("Rwanda", "RWF"),
    "WSM": ("Samoa", "WST"),
    "SMR": ("San Marino, Republic of", "EUR"),
    "SAU": ("Saudi Arabia", "SAR"),
    "SEN": ("Senegal", "XOF"),
    "SRB": ("Serbia, Republic of", "RSD"),
    "SYC": ("Seychelles", "SCR"),
    "SLE": ("Sierra Leone", "SLE"),
    "SGP": ("Singapore", "SGD"),
    "SXM": ("Sint Maarten, Kingdom of the Netherlands", "XCG"),
    "SVK": ("Slovak Republic", "EUR"),
    "SVN": ("Slovenia, Republic of", "EUR"),
    "SLB": ("Solomon Islands", "SBD"),
    "SOM": ("Somalia", "SOS"),
    "ZAF": ("South Africa", "ZAR"),
    "SSD": ("South Sudan, Republic of", "SSP"),
    "ESP": ("Spain", "EUR"),
    "LKA": ("Sri Lanka", "LKR"),
    "KNA": ("St. Kitts and Nevis", "XCD"),
    "LCA": ("St. Lucia", "XCD"),
    "VCT": ("St. Vincent and the Grenadines", "XCD"),
    "SDN": ("Sudan", "SDG"),
    "SUR": ("Suriname", "SRD"),
    "SWE": ("Sweden", "SEK"),
    "CHE": ("Switzerland", "CHF"),
    "SYR": ("Syrian Arab Republic", "SYP"),
    "STP": ("São Tomé and Príncipe, Democratic Republic of", "STN"),
    "TJK": ("Tajikistan, Republic of", "TJS"),
    "TZA": ("Tanzania, United Republic of", "TZS"),
    "THA": ("Thailand", "THB"),
    "TLS": ("Timor-Leste, Democratic Republic of", "USD"),
    "TGO": ("Togo", "XOF"),
    "TON": ("Tonga", "TOP"),
    "TTO": ("Trinidad and Tobago", "TTD"),
    "TUN": ("Tunisia", "TND"),
    "TUV": ("Tuvalu", "AUD"),
    "TUR": ("Türkiye, Republic of", "TRY"),
    "UGA": ("Uganda", "UGX"),
    "UKR": ("Ukraine", "UAH"),
    "ARE": ("United Arab Emirates", "AED"),
    "GBR": ("United Kingdom", "GBP"),
    "USA": ("United States", "USD"),
    "URY": ("Uruguay", "UYU"),
    "UZB": ("Uzbekistan, Republic of", "UZS"),
    "VUT": ("Vanuatu", "VUV"),
    "VEN": ("Venezuela, República Bolivariana de", "VES"),
    "VNM": ("Vietnam", "VND"),
    "YEM": ("Yemen, Republic of", "YER"),
    "ZMB": ("Zambia", "ZMW"),
    "ZWE": ("Zimbabwe", "ZWG"),
}


# --------------------------------------------------------------------------
# IMF data access
# --------------------------------------------------------------------------
class IMFError(Exception):
    """Raised when the IMF API cannot be reached or returns unusable data."""


def _parse_period(value: str) -> pd.Timestamp | None:
    """Convert IMF time periods like '2024-M01' or '2024-01' to a month-start Timestamp."""
    if not value:
        return None
    value = str(value).strip()
    try:
        if "-M" in value:
            year, month = value.split("-M")
            return pd.Timestamp(year=int(year), month=int(month), day=1)
        return pd.Timestamp(value).to_period("M").to_timestamp()
    except (ValueError, TypeError):
        return None


def _local(tag: str) -> str:
    """Strip an XML namespace: '{ns}Obs' -> 'Obs'."""
    return tag.rsplit("}", 1)[-1]


def _parse_xml(text: str) -> dict:
    """Parse an SDMX 3.0 structure-specific XML message into {period: value} for the first series."""
    root = ET.fromstring(text)
    for series in root.iter():
        if _local(series.tag) != "Series":
            continue
        out = {}
        for obs in series:
            if _local(obs.tag) != "Obs":
                continue
            period = obs.attrib.get("TIME_PERIOD") or obs.attrib.get("TIME")
            value = obs.attrib.get("OBS_VALUE")
            if value is None:  # some formats put the value in a child element
                for child in obs:
                    if _local(child.tag).upper() in ("OBSVALUE", "OBS_VALUE"):
                        value = child.attrib.get("value") or child.text
            if period is not None and value not in (None, "", "NaN"):
                out[period] = value
        if out:
            return out
    return {}


def _parse_json(payload: dict) -> dict:
    """Parse an SDMX-JSON message into {period: value} for the first series (fallback path)."""
    data = payload.get("data", payload)
    structures = data.get("structures") or [data.get("structure", {})]
    obs_dims = structures[0].get("dimensions", {}).get("observation", [])
    time_dim = next((d for d in obs_dims if d.get("id") == "TIME_PERIOD"), None)
    if time_dim is None:
        return {}
    periods = [v.get("id") or v.get("value") for v in time_dim.get("values", [])]
    for dataset in data.get("dataSets", []):
        for series in dataset.get("series", {}).values():
            out = {}
            for idx, vals in series.get("observations", {}).items():
                if vals and vals[0] not in (None, ""):
                    out[periods[int(idx)]] = vals[0]
            if out:
                return out
    return {}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_series(dataflow: str, key: str) -> pd.Series:
    """Download one monthly series from the IMF. Returns an empty Series if the IMF has no data."""
    url = f"{BASE_URL}/data/dataflow/{AGENCY}/{dataflow}/+/{key}"
    params = {"dimensionAtObservation": "TIME_PERIOD"}
    last_error = None

    for accept in ("application/xml", "application/json"):
        headers = {**HEADERS, "Accept": accept}
        for attempt in range(3):
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=45)
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(1.5 * (attempt + 1))
                continue

            if resp.status_code == 404:  # SDMX "no records found"
                return pd.Series(dtype=float)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {resp.status_code}"
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                break

            try:
                if "json" in resp.headers.get("Content-Type", "") or resp.text.lstrip().startswith("{"):
                    raw = _parse_json(resp.json())
                else:
                    raw = _parse_xml(resp.text)
            except (ET.ParseError, ValueError, KeyError, IndexError) as exc:
                last_error = f"Could not parse IMF response: {exc}"
                break  # try the other format

            series = pd.Series(
                {_parse_period(p): pd.to_numeric(v, errors="coerce") for p, v in raw.items()},
                dtype=float,
            )
            series = series[series.index.notna()].sort_index()
            series = series[~series.index.duplicated(keep="last")]
            return series[series.index >= START_MONTH]

    raise IMFError(f"IMF request failed for {dataflow}/{key} ({last_error}). URL: {url}")


def get_cpi(iso: str) -> tuple[pd.Series, str]:
    """Headline monthly CPI. Falls back to HICP if the IMF has no 'CPI' index for this economy."""
    for index_type in ("CPI", "HICP"):
        key = CPI_KEY.format(iso=iso, index_type=index_type)
        series = fetch_series("CPI", key)
        if not series.dropna().empty:
            return series, key
    return pd.Series(dtype=float), CPI_KEY.format(iso=iso, index_type="CPI")


def get_fx(iso: str) -> tuple[pd.Series | None, str]:
    """Local currency per USD. The U.S. is the numeraire, so its rate is identically 1."""
    if iso == "USA":
        return None, "USD per USD = 1 (numeraire)"
    key = FX_KEY.format(iso=iso)
    return fetch_series("ER", key), key


# --------------------------------------------------------------------------
# Economics
# --------------------------------------------------------------------------
def build_panel(c1: str, c2: str) -> tuple[pd.DataFrame, dict]:
    """Merge CPI and FX for both countries and compute S(t) and RER(t) for every month."""
    cpi1, cpi1_key = get_cpi(c1)
    cpi2, cpi2_key = get_cpi(c2)
    fx1, fx1_key = get_fx(c1)
    fx2, fx2_key = get_fx(c2)

    pieces = [s for s in (cpi1, cpi2, fx1, fx2) if s is not None and not s.empty]
    if not pieces:
        return pd.DataFrame(), {}
    index = pd.DatetimeIndex(sorted(set().union(*[set(s.index) for s in pieces])), name="Month")

    df = pd.DataFrame(index=index)
    df["P1"] = cpi1.reindex(index)
    df["P2"] = cpi2.reindex(index)
    df["FX1"] = 1.0 if fx1 is None else fx1.reindex(index)
    df["FX2"] = 1.0 if fx2 is None else fx2.reindex(index)

    # S(t): Country 2 currency per 1 unit of Country 1 currency, via the USD cross rate
    df["S"] = df["FX2"] / df["FX1"]
    df["RER"] = df["S"] * df["P1"] / df["P2"]
    df = df.replace([np.inf, -np.inf], np.nan)
    df.loc[df["RER"] <= 0, "RER"] = np.nan

    keys = {"P1": cpi1_key, "P2": cpi2_key, "FX1": fx1_key, "FX2": fx2_key}
    return df, keys


def apply_sample(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, float]:
    """Restrict to the sample, compute RER* over valid months and the Real Index."""
    window = df.loc[start:end].copy()
    rer_star = window["RER"].dropna().mean()
    window["RER_star"] = rer_star
    window["Real_Index"] = 100 * window["RER"] / rer_star
    return window, rer_star


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def make_chart(window: pd.DataFrame, view: str, s_label: str, title: str) -> go.Figure:
    real = go.Scatter(x=window.index, y=window["Real_Index"], name="Real Index (avg = 100)",
                      mode="lines", line=dict(color="#4E2A84", width=2), connectgaps=False)
    nominal = go.Scatter(x=window.index, y=window["S"], name=f"Nominal S ({s_label})",
                         mode="lines", line=dict(color="#D98C1F", width=2), connectgaps=False)

    if view == "Both":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(real, secondary_y=False)
        fig.add_trace(nominal, secondary_y=True)
        fig.update_yaxes(title_text="Real Index (sample avg = 100)", secondary_y=False)
        fig.update_yaxes(title_text=f"S: {s_label}", secondary_y=True, showgrid=False)
    elif view == "Real":
        fig = go.Figure(real)
        fig.update_yaxes(title_text="Real Index (sample avg = 100)")
    else:
        fig = go.Figure(nominal)
        fig.update_yaxes(title_text=f"S: {s_label}")

    if view in ("Real", "Both"):
        fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.6)

    fig.update_layout(
        title=title, hovermode="x unified", height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=80, b=10),
    )
    fig.update_xaxes(title_text="Month")
    return fig


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
def label(iso: str) -> str:
    name, cur = COUNTRIES[iso]
    return f"{name} ({iso}, {cur})"


def main() -> None:
    st.set_page_config(page_title="Real Exchange Rate App", page_icon="💱", layout="wide")
    st.title("Real Exchange Rate App")
    st.caption("Monthly IMF CPI and exchange-rate data · RER(t) = S(t) × P1(t) / P2(t)")

    codes = list(COUNTRIES)
    with st.sidebar:
        st.header("Countries")
        c1 = st.selectbox("Country 1 (home)", codes, index=codes.index("GBR"), format_func=label)
        c2 = st.selectbox("Country 2 (foreign)", codes, index=codes.index("USA"), format_func=label)

    if c1 == c2:
        st.warning("Choose two different economies.")
        st.stop()

    name1, cur1 = COUNTRIES[c1]
    name2, cur2 = COUNTRIES[c2]
    s_label = f"{cur2} per {cur1}"

    try:
        with st.spinner("Downloading IMF data…"):
            panel, keys = build_panel(c1, c2)
    except IMFError as exc:
        st.error(f"Could not download data from the IMF. Please try again in a minute.\n\n{exc}")
        st.stop()

    valid = panel["RER"].dropna() if not panel.empty else pd.Series(dtype=float)
    if valid.empty:
        st.error(
            f"No overlapping monthly CPI and exchange-rate data for {name1} and {name2}. "
            "The IMF may not publish one of these series."
        )
        if keys:
            st.write({k: f"{v}: {panel[k].notna().sum()} months" for k, v in keys.items()})
        st.stop()

    months = list(pd.date_range(valid.index.min(), valid.index.max(), freq="MS"))
    with st.sidebar:
        st.header("Sample period")
        start, end = st.select_slider(
            "Start and end month", options=months, value=(months[0], months[-1]),
            format_func=lambda d: d.strftime("%b %Y"),
        )
        st.header("Chart")
        view = st.radio("Show", ["Real", "Nominal", "Both"], index=2, horizontal=True)

    window, rer_star = apply_sample(panel, start, end)
    n_valid = int(window["RER"].notna().sum())
    if n_valid == 0:
        st.warning("No valid months in the selected sample. Widen the date range.")
        st.stop()

    # Headline metrics
    last = window["RER"].last_valid_index()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("RER* (sample average RER)", f"{rer_star:,.4g}")
    m2.metric(f"Latest S ({s_label})", f"{window.loc[last, 'S']:,.4g}", help=last.strftime("%b %Y"))
    m3.metric("Latest Real Index", f"{window.loc[last, 'Real_Index']:,.1f}", help=last.strftime("%b %Y"))
    m4.metric("Valid months", f"{n_valid} of {len(window)}")

    title = f"{name1} vs {name2}: {start:%b %Y} – {end:%b %Y}"
    st.plotly_chart(make_chart(window, view, s_label, title), width="stretch")
    st.caption(
        f"Real Index above 100: {cur1} is stronger in real terms than its sample average "
        f"({name1} goods relatively more expensive than {name2} goods)."
    )

    # Data-quality notes
    missing = len(window) - n_valid
    if missing:
        st.info(f"{missing} month(s) in the sample lack CPI or FX data and are excluded from RER*.")
    jumps = window["S"].pct_change(fill_method=None).abs()
    big = jumps[jumps > JUMP_THRESHOLD]
    if not big.empty:
        dates = ", ".join(d.strftime("%b %Y") for d in big.index[:6])
        st.info(
            f"S moves more than {JUMP_THRESHOLD:.0%} in a single month at: {dates}"
            f"{' …' if len(big) > 6 else ''}. This can reflect a devaluation, a currency "
            "redenomination or a data break — worth checking before interpreting the series."
        )

    # CSV export
    export = pd.DataFrame({
        "Month": window.index.strftime("%Y-%m"),
        f"P1_CPI_{c1}": window["P1"].values,
        f"P2_CPI_{c2}": window["P2"].values,
        f"FX1_{cur1}_per_USD": window["FX1"].values,
        f"FX2_{cur2}_per_USD": window["FX2"].values,
        f"S_{cur2}_per_{cur1}": window["S"].values,
        "RER": window["RER"].values,
        "RER_star": window["RER_star"].values,
        "Real_Index": window["Real_Index"].values,
    })
    st.download_button(
        "Download CSV (selected sample)",
        export.to_csv(index=False).encode("utf-8"),
        file_name=f"rer_{c1}_{c2}_{start:%Y%m}_{end:%Y%m}.csv",
        mime="text/csv",
    )

    with st.expander("Data table"):
        st.dataframe(export, hide_index=True, width="stretch")

    with st.expander("Method and data sources"):
        st.markdown(
            f"""
- **S(t)** = {cur2} per 1 {cur1} = (FX2 per USD) / (FX1 per USD), using IMF period-average rates.
- **RER(t)** = S(t) × P1(t) / P2(t), where P1 is {name1}'s CPI and P2 is {name2}'s CPI.
- **RER\\*** = average of RER(t) over the {n_valid} valid months between {start:%b %Y} and {end:%b %Y}; recalculated whenever the sample changes.
- **Real Index(t)** = 100 × RER(t) / RER\\*, so it averages exactly 100 over the sample.
- Nominal S is shown in actual currency units (not normalized).

IMF SDMX 3.0 series used (`{BASE_URL}`):
- P1: `CPI/{keys['P1']}` · P2: `CPI/{keys['P2']}`
- FX1: `ER/{keys['FX1']}` · FX2: `ER/{keys['FX2']}`
"""
        )


if __name__ == "__main__":
    main()
