"""
Parity Lens: a real exchange rate (RER) app
-------------------------------------------
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
# Look and feel
# --------------------------------------------------------------------------
THEMES = {
    "light": dict(bg="#FFFFFF", side="#F5F3F9", text="#1F1F24", muted="#5F5F6B",
                  border="#D6D3DE", field="#FFFFFF", hover="#ECE8F4", grid="#E7E4EE",
                  plotly="plotly_white"),
    "dark": dict(bg="#0E1117", side="#171B26", text="#F1F1F4", muted="#A4A6B3",
                 border="#353A4A", field="#1E2331", hover="#2A3044", grid="#262B38",
                 plotly="plotly_dark"),
}

# (real line, nominal line), with a brighter variant for dark mode
PALETTES = {
    "Purple & Orange": {"light": ("#4E2A84", "#D9821F"), "dark": ("#B79CEB", "#F5A94A")},
    "Blue & Red": {"light": ("#1F5FA8", "#C0392B"), "dark": ("#71A9F7", "#F2766B")},
    "Green & Gray": {"light": ("#1E7D5A", "#6F7480"), "dark": ("#4FD1A1", "#C3C6CF")},
    "Teal & Gold": {"light": ("#0F7C8C", "#B07D0B"), "dark": ("#3CC9D6", "#E9C54B")},
}


def inject_theme_css(tm: dict, accent: str) -> None:
    """Restyle the page. Streamlit has no API to switch its theme at runtime, so this uses CSS."""
    st.markdown(
        f"""
<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stMain"] {{ background-color: {tm['bg']} !important; color: {tm['text']} !important; }}
[data-testid="stSidebar"], [data-testid="stSidebar"] > div {{ background-color: {tm['side']} !important; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label, .stApp li,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"] *,
[data-testid="stMetricValue"], [data-testid="stMetricValue"] *, [data-testid="stMetricLabel"] * {{
    color: {tm['text']} !important; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *,
[data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {{ color: {tm['muted']} !important; }}
[data-testid="stSelectbox"] [role="group"], [data-testid="stSelectbox"] [role="group"] button,
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, .stApp input {{
    background-color: {tm['field']} !important; color: {tm['text']} !important;
    border-color: {tm['border']} !important; }}
[data-testid="stSelectbox"] [role="group"] svg, div[data-baseweb="select"] svg {{ color: {tm['muted']} !important; fill: {tm['muted']} !important; }}
[data-testid="stTooltipIcon"] svg {{ color: {tm['muted']} !important; }}
[data-testid="stSelectboxVirtualDropdown"], div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li {{
    background-color: {tm['field']} !important; color: {tm['text']} !important; border-color: {tm['border']} !important; }}
[data-testid="stSelectboxVirtualDropdown"] [role="option"] {{ color: {tm['text']} !important; }}
[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
[data-testid="stSelectboxVirtualDropdown"] [role="option"][data-focused],
[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
div[data-baseweb="popover"] li:hover {{ background-color: {tm['hover']} !important; }}
[data-testid="stExpander"] details {{ background-color: {tm['bg']} !important; border-color: {tm['border']} !important; }}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {{ color: {tm['text']} !important; }}
.stDownloadButton button {{ background-color: {tm['field']} !important; color: {tm['text']} !important;
    border-color: {tm['border']} !important; }}
[data-testid="stAlert"] * {{ color: {tm['text']} !important; }}
.stApp [data-testid^="stBaseButton"] {{ background-color: {tm['field']} !important; color: {tm['text']} !important;
    border-color: {tm['border']} !important; }}
.stApp [data-testid^="stBaseButton"] * {{ color: inherit !important; }}
.stApp [data-testid^="stBaseButton"]:disabled {{ opacity: 0.45; }}
.stApp [data-testid="stButtonGroup"] button {{ background-color: {tm['field']} !important; color: {tm['text']} !important;
    border-color: {tm['border']} !important; }}
.stApp [data-testid="stButtonGroup"] button * {{ color: inherit !important; }}
.stApp [data-testid="stButtonGroup"] button[aria-checked="true"], .stApp [data-testid="stButtonGroup"] button[aria-pressed="true"] {{
    background-color: {tm['hover']} !important; color: {accent} !important; border-color: {accent} !important;
    font-weight: 600; }}
.stApp [role="tab"] p {{ color: {tm['muted']} !important; }}
.stApp [role="tab"][aria-selected="true"] p {{ color: {tm['text']} !important; font-weight: 600; }}
.stApp hr {{ border-color: {tm['border']} !important; }}
.stApp .katex {{ color: {tm['text']} !important; font-size: 1.1em; }}
.block-container {{ padding-top: 2.2rem; }}
.stApp h1 {{ letter-spacing: -0.02em; margin-bottom: 0 !important; }}
.stApp .hero {{ border-left: 5px solid {accent}; background: {tm['side']}; border-radius: 10px;
    padding: 1.1rem 1.4rem; height: 100%; }}
.stApp .hero .kicker {{ color: {tm['muted']} !important; font-size: 0.85rem; text-transform: uppercase;
    letter-spacing: 0.06em; margin: 0 0 0.35rem 0; }}
.stApp .hero .headline {{ color: {tm['text']} !important; font-size: 1.9rem; font-weight: 700; line-height: 1.2;
    margin: 0 0 0.5rem 0; }}
.stApp .hero .headline span {{ color: {accent} !important; }}
.stApp .hero .sub {{ color: {tm['muted']} !important; font-size: 0.95rem; margin: 0; }}
.stApp .footer {{ color: {tm['muted']} !important; font-size: 0.8rem; text-align: center; margin-top: 2rem; }}
</style>
""",
        unsafe_allow_html=True,
    )


def decimals_for(ref: float) -> int:
    """#,##0.0 by default; more decimals only when the number is small enough to need them."""
    if not np.isfinite(ref) or ref <= 0 or ref >= 10:
        return 1
    if ref >= 1:
        return 2
    return min(8, int(-np.floor(np.log10(ref))) + 2)


def fmt(x: float, decimals: int = 1) -> str:
    return f"{x:,.{decimals}f}"


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------
def make_chart(window: pd.DataFrame, view: str, cur1: str, cur2: str, colors: tuple,
               tm: dict, title: str, subtitle: str, s_dec: int) -> go.Figure:
    both = view == "Both"
    fig = make_subplots(specs=[[{"secondary_y": both}]])
    real_color, nom_color = colors

    lines = []
    if view in ("Real", "Both"):
        lines.append(("Real_Index", "Real Index (sample avg = 100)", real_color, 1, False))
    if view in ("Nominal", "Both"):
        lines.append(("S", f"Nominal: {cur2} per {cur1}", nom_color, s_dec, both))

    for col, name, color, dec, secondary in lines:
        s = window[col]
        kw = {"secondary_y": secondary} if both else {}
        fig.add_trace(go.Scatter(
            x=s.index, y=s, name=name, mode="lines", connectgaps=False,
            line=dict(color=color, width=2.2),
            hovertemplate=f"{name}: %{{y:,.{dec}f}}<extra></extra>",
        ), **kw)
        last = s.last_valid_index()
        if last is not None:  # label the latest point in the line's colour
            fig.add_trace(go.Scatter(
                x=[last], y=[s[last]], mode="markers+text", showlegend=False, hoverinfo="skip",
                marker=dict(color=color, size=8), cliponaxis=False,
                text=[f" {fmt(s[last], dec)}"], textposition="middle right",
                textfont=dict(color=color, size=13),
            ), **kw)

    if view in ("Real", "Both"):
        fig.add_hline(y=100, line_dash="dot", line_color=tm["muted"], opacity=0.7)

    # Leave room on the right for the end-of-line labels
    span = window.index.max() - window.index.min()
    pad = max(span * 0.06, pd.Timedelta(days=62))
    fig.update_xaxes(range=[window.index.min(), window.index.max() + pad], hoverformat="%b %Y",
                     gridcolor=tm["grid"], title_text=None)

    if both:
        fig.update_yaxes(title_text="Real Index (sample avg = 100)", tickformat=",.1f",
                         secondary_y=False, gridcolor=tm["grid"])
        fig.update_yaxes(title_text=f"{cur2} per {cur1}", tickformat=f",.{s_dec}f", tickmode="auto",
                         nticks=8, secondary_y=True, showgrid=False)
    elif view == "Real":
        fig.update_yaxes(title_text="Real Index (sample avg = 100)", tickformat=",.1f", gridcolor=tm["grid"])
    else:
        fig.update_yaxes(title_text=f"{cur2} per {cur1}", tickformat=f",.{s_dec}f", gridcolor=tm["grid"])

    fig.update_layout(
        template=tm["plotly"], paper_bgcolor=tm["bg"], plot_bgcolor=tm["bg"],
        font=dict(color=tm["text"]),
        title=dict(text=f"<b>{title}</b>", x=0.01, xanchor="left",
                   subtitle=dict(text=subtitle, font=dict(color=tm["muted"], size=13))),
        hovermode="x unified", height=540,
        hoverlabel=dict(bgcolor=tm["field"], font_color=tm["text"], bordercolor=tm["border"]),
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=95, b=40),
    )
    return fig


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
def label(iso: str) -> str:
    name, cur = COUNTRIES[iso]
    return f"{name} ({iso}, {cur})"


def clamp_sample(months: list) -> tuple:
    """Return the stored sample, clamped to the months available for the current country pair."""
    lo, hi = months[0], months[-1]
    s = min(max(st.session_state.get("start", lo), lo), hi)
    e = min(max(st.session_state.get("end", hi), lo), hi)
    if s > e:
        s, e = lo, hi
    if (s, e) != (st.session_state.get("start"), st.session_state.get("end")):
        st.session_state.start, st.session_state.end = s, e
        st.session_state.date_v = st.session_state.get("date_v", 0) + 1  # rebuild widgets
    return s, e


APP_NAME = "Parity Lens"
TAGLINE = "How strong is a currency in real terms? Real exchange rates for 200 economies, built from IMF data."


def swap_countries() -> None:
    st.session_state.c1, st.session_state.c2 = st.session_state.c2, st.session_state.c1


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🔭", layout="wide")

    codes = list(COUNTRIES)
    st.session_state.setdefault("dark", getattr(st.context.theme, "type", None) == "dark")
    st.session_state.setdefault("c1", "GBR")
    st.session_state.setdefault("c2", "USA")

    # ---- Header: name, tagline, dark-mode switch --------------------------
    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_r:
        st.toggle("🌙 Dark", key="dark")
    mode = "dark" if st.session_state.dark else "light"
    tm = THEMES[mode]
    with head_l:
        st.title(f"🔭 {APP_NAME}")
        st.caption(TAGLINE)

    # ---- Sidebar: pair, then sample period, then display ------------------
    # Containers fix the visual order; the period box is filled once the data is known.
    sb_pair, sb_period, sb_display = st.sidebar.container(), st.sidebar.container(), st.sidebar.container()
    with sb_pair:
        st.subheader("Currency pair")
        c1 = st.selectbox("Home country", codes, key="c1", format_func=label)
        st.button("⇅  Swap countries", on_click=swap_countries, width="stretch")
        c2 = st.selectbox("Compare against", codes, key="c2", format_func=label)
    with sb_display:
        st.subheader("Display")
        view = st.segmented_control("Show", ["Real", "Nominal", "Both"], default="Both", key="view") or "Both"
        palette = st.selectbox("Line colors", list(PALETTES), key="palette")

    colors = PALETTES[palette][mode]
    inject_theme_css(tm, colors[0])

    if c1 == c2:
        st.warning("Pick two different economies in the sidebar.")
        st.stop()

    name1, cur1 = COUNTRIES[c1]
    name2, cur2 = COUNTRIES[c2]

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
            "The IMF may not publish one of these series. Try another pair."
        )
        if keys:
            st.caption(" · ".join(f"{k}: {panel[k].notna().sum()} months" for k in keys))
        st.stop()

    # ---- Sample period: month boxes and slider kept in sync ---------------
    months = list(pd.date_range(valid.index.min(), valid.index.max(), freq="MS"))
    start, end = clamp_sample(months)
    v = st.session_state.get("date_v", 0)
    month_fmt = lambda d: d.strftime("%b %Y")  # noqa: E731
    with sb_period:
        st.subheader("Sample period")
        col_a, col_b = st.columns(2)
        box_start = col_a.selectbox("Start", months, index=months.index(start), key=f"start_box_{v}",
                                    format_func=month_fmt, help="Click and type to search, e.g. 'Mar 2005'")
        box_end = col_b.selectbox("End", months, index=months.index(end), key=f"end_box_{v}",
                                  format_func=month_fmt)
        slider = st.select_slider("Drag to adjust", options=months, value=(start, end),
                                  key=f"range_slider_{v}", format_func=month_fmt, label_visibility="collapsed")
        if st.button("Reset to full history", width="stretch", disabled=(start, end) == (months[0], months[-1])):
            slider = (months[0], months[-1])
            box_start, box_end = start, end
    new = None
    if (box_start, box_end) != (start, end):
        new = tuple(sorted((box_start, box_end)))
    elif tuple(slider) != (start, end):
        new = tuple(slider)
    if new is not None:
        st.session_state.start, st.session_state.end = new
        st.session_state.date_v = v + 1
        st.rerun()

    window, rer_star = apply_sample(panel, start, end)
    n_valid = int(window["RER"].notna().sum())
    if n_valid == 0:
        st.warning("No valid months in the selected sample. Widen the date range.")
        st.stop()

    last = window["RER"].last_valid_index()
    s_dec = decimals_for(window["S"].abs().median())
    rer_dec = decimals_for(abs(rer_star))
    idx_last = window.loc[last, "Real_Index"]
    gap = idx_last - 100
    period = f"{start:%b %Y} to {end:%b %Y}"

    # ---- Data notes (shown at the bottom; flagged under the chart) --------
    notes = []
    missing = len(window) - n_valid
    if missing:
        notes.append(f"**{missing} month(s)** in the sample lack CPI or exchange-rate data. "
                     "They are left as gaps in the chart and excluded from RER*.")
    jumps = window["S"].pct_change(fill_method=None).abs()
    big = jumps[jumps > JUMP_THRESHOLD]
    if not big.empty:
        dates = ", ".join(d.strftime("%b %Y") for d in big.index[:6])
        notes.append(
            f"**S moves more than {JUMP_THRESHOLD:.0%} in a single month** at {dates}"
            f"{' …' if len(big) > 6 else ''}. This can reflect a devaluation, a currency "
            "redenomination or a data break, so check before reading too much into it."
        )
    if last < end:
        notes.append(f"The latest complete month in this sample is **{last:%b %Y}**; "
                     "later months are missing at least one input.")

    # ---- Headline result --------------------------------------------------
    if abs(gap) < 0.05:
        headline = f"{cur1} is <span>at its average</span> real value vs {cur2}"
    else:
        word = "overvalued" if gap > 0 else "undervalued"
        headline = f"{cur1} is <span>{fmt(abs(gap))}% {word}</span> vs {cur2}"

    hero_col, metrics_col = st.columns([3, 2], gap="medium")
    with hero_col:
        st.markdown(
            f'<div class="hero"><p class="kicker">{name1} vs {name2} · {last:%b %Y}</p>'
            f'<p class="headline">{headline}</p>'
            f'<p class="sub">In real terms, compared with its average over {period}. '
            f'A Real Index above 100 means {name1} is relatively expensive.</p></div>',
            unsafe_allow_html=True,
        )
    with metrics_col:
        r1a, r1b = st.columns(2)
        r2a, r2b = st.columns(2)
        r1a.metric("Real Index", fmt(idx_last), help=f"{last:%b %Y}. Sample average = 100.")
        r1b.metric(f"{cur2} per {cur1}", fmt(window.loc[last, "S"], s_dec), help=f"Nominal rate, {last:%b %Y}")
        r2a.metric("RER* (sample avg)", fmt(rer_star, rer_dec), help="Average RER over valid months in the sample")
        r2b.metric("Months of data", f"{n_valid:,}", help=f"{n_valid} of {len(window)} months have complete data")

    # ---- Chart ------------------------------------------------------------
    titles = {
        "Real": f"Real value of {cur1} against {cur2}",
        "Nominal": f"Value of 1 {cur1} in {cur2}",
        "Both": f"Value of {cur1} in {cur2}: nominal and real",
    }
    subtitle = f"{name1} vs {name2} · {period} · monthly"
    st.plotly_chart(make_chart(window, view, cur1, cur2, colors, tm, titles[view], subtitle, s_dec),
                    width="stretch", theme=None)

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
    dl_col, note_col = st.columns([1, 3], vertical_alignment="center")
    dl_col.download_button(
        "⬇  Download CSV", export.to_csv(index=False).encode("utf-8"),
        file_name=f"rer_{c1}_{c2}_{start:%Y%m}_{end:%Y%m}.csv", mime="text/csv", width="stretch",
    )
    if notes:
        note_col.caption(f"⚠️ {len(notes)} data note{'s' if len(notes) > 1 else ''} for this sample. "
                         "See **Data notes** below.")

    # ---- Bottom: method, interpretation, notes, data ----------------------
    st.divider()
    st.subheader("About the numbers")
    tab_method, tab_read, tab_notes, tab_data = st.tabs(
        ["📐 Method", "💡 How to read it", f"⚠️ Data notes ({len(notes)})", "🗂️ Data & sources"]
    )

    with tab_method:
        m_l, m_r = st.columns(2, gap="large")
        with m_l:
            st.markdown(f"**1. Nominal rate**: {cur2} per 1 {cur1}, crossed through the US dollar")
            st.latex(r"S_t = \frac{FX^{(2)}_t}{FX^{(1)}_t} \qquad FX = \text{local currency per USD}")
            st.markdown(f"**2. Real exchange rate**: {name1} prices relative to {name2} prices in a common currency")
            st.latex(r"RER_t = S_t \times \frac{P^{(1)}_t}{P^{(2)}_t}")
        with m_r:
            st.markdown(f"**3. Benchmark**: average RER over the {n_valid:,} valid months in the sample")
            st.latex(r"RER^{*} = \frac{1}{N}\sum_{t=1}^{N} RER_t")
            st.markdown("**4. Real Index and over/undervaluation**")
            st.latex(r"\text{Index}_t = 100 \times \frac{RER_t}{RER^{*}} \qquad "
                     r"\text{Over/under}_t = \text{Index}_t - 100")
        st.caption(f"P = headline CPI (monthly index). FX = IMF period-average rate. "
                   f"Country 1 = {name1}, Country 2 = {name2}. RER* is recalculated whenever the sample changes.")

    with tab_read:
        st.markdown(
            f"""
- **Index above 100**: {cur1} is stronger in real terms than its sample average. {name1} goods and services are relatively expensive for {name2} buyers.
- **Index below 100**: {cur1} is weaker in real terms. {name1} is relatively cheap.
- **Real vs nominal**: when the two lines move together, inflation differences are small and the exchange rate drives the RER. When they drift apart, inflation differences matter.
- **The benchmark is relative.** "Overvalued" means above the average for *this* sample (relative PPP), not above an absolute fair value. Changing the dates changes the benchmark and can flip the answer.
- **CPI baskets differ across countries**, so the index tracks changes in relative prices, not price levels.
"""
        )

    with tab_notes:
        if notes:
            for n in notes:
                st.markdown(f"- {n}")
        else:
            st.markdown("No gaps or unusual jumps in this sample. ✅")

    with tab_data:
        st.dataframe(export, hide_index=True, width="stretch", height=280)
        st.markdown(
            f"""
**Source:** IMF SDMX 3.0 API (`{BASE_URL}`), no API key required. Downloads are cached for six hours.

| Input | IMF series |
|---|---|
| P1: {name1} CPI | `CPI/{keys['P1']}` |
| P2: {name2} CPI | `CPI/{keys['P2']}` |
| FX1: {cur1} per USD | `ER/{keys['FX1']}` |
| FX2: {cur2} per USD | `ER/{keys['FX2']}` |
"""
        )

    st.markdown(f'<p class="footer">{APP_NAME} · Data: International Monetary Fund · '
                "For educational use, not investment advice</p>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
