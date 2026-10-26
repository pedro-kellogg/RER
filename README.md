# Parity Lens

How strong is a currency in real terms? Parity Lens is a Streamlit app that computes the bilateral real exchange rate (RER) between any two IMF economies, or the Euro area, using monthly IMF CPI and exchange-rate data from January 1976 onward.

## Economics

Country 1 is the home country and Country 2 is the foreign country.

| Symbol | Definition |
|---|---|
| S(t) | Units of Country 2 currency per 1 unit of Country 1 currency |
| P1(t), P2(t) | Monthly CPI of Country 1 and Country 2 |
| RER(t) | S(t) × P1(t) / P2(t) |
| RER* | Average of RER(t) over valid months in the selected sample |
| Real Index(t) | 100 × RER(t) / RER* |

IMF exchange rates are quoted as local currency units per USD, so the app builds the cross rate as

S(t) = (Country 2 currency per USD) / (Country 1 currency per USD)

with the U.S. rate fixed at 1. Example: with the United Kingdom as Country 1 and the United States as Country 2, S is USD per GBP.

A rising Real Index means Country 1's currency is appreciating in real terms: Country 1 goods are becoming more expensive relative to Country 2 goods. The index averages exactly 100 over whatever sample is selected, and RER* is recalculated whenever the dates change. Nominal S is shown in actual currency units.

## Features

- **Currency pair:** pick a home country and a comparison country from 200 economies with both IMF CPI and exchange-rate series, including the Euro area (IMF code G163). A swap button flips the pair.
- **Sample period:** pick the start and end months from small calendars (year arrows on top, a grid of months below), or drag the slider. The two stay in sync, and a button resets to the full history.
- **Headline:** how over- or undervalued the home currency is right now (latest Real Index minus 100), alongside the latest Real Index, nominal rate, RER* and the number of months in the sample.
- **Chart:** the Real Index, nominal S, or both (separate axes), with the latest value labeled at the end of each line.
- **Display:** dark or light mode, and four line-color palettes.
- **Wine pairing:** a short wine curiosity for each country in the pair (about 40 wine-producing economies). When both countries make wine, a line notes whose wine is cheaper than usual in real terms.
- **CSV download:** every month in the sample, at full precision: both CPIs, both USD rates, S, RER, RER* and the Real Index.
- **About the numbers** (bottom of the page), in four tabs:
  - Method: the equations
  - How to read it: interpretation and caveats
  - Data notes: missing months, and one-month moves in S above 50%
  - Data & sources: data table and the exact IMF series used

## Data

Source: IMF SDMX 3.0 API, `https://api.imf.org/external/sdmx/3.0` (no API key required)

| Series | Dataflow | Key |
|---|---|---|
| Headline CPI, index, monthly | `IMF.STA/CPI` | `{ISO3}.CPI._T.IX.M` (falls back to `{ISO3}.HICP._T.IX.M` if no CPI series exists) |
| Exchange rate, local currency per USD, period average, monthly | `IMF.STA/ER` | `{ISO3}.XDC_USD.PA_RT.M` |

Coverage varies by country, and some series have gaps. Months missing any input are excluded from RER*. Downloads are cached for six hours. Live IMF requests can occasionally fail; reloading the page usually fixes it.

## Run it

Deployed on Streamlit Community Cloud with Python 3.12. To run locally:

```
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py`: the Streamlit app
- `requirements.txt`: Python dependencies
- `README.md`: this file
