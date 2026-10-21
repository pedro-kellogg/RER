# Real Exchange Rate App

A Streamlit app that computes the bilateral real exchange rate (RER) between any two IMF economies, or the Euro area, using monthly IMF CPI and exchange-rate data from January 1976 onward.

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

- Pick Country 1 and Country 2 from 200 economies with both IMF CPI and exchange-rate series, including the Euro area (IMF code G163)
- Choose the start and end months of the sample
- Chart the Real Index, nominal S, or both (separate axes)
- Download a CSV with every month in the sample: both CPIs, both USD rates, S, RER, RER* and the Real Index
- Notes on missing months and on large one-month moves in S (devaluations, redenominations or data breaks)

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
