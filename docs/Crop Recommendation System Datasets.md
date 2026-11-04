# Crop Recommendation System: Datasets

Oct 29, 2026 · @Ankush Sunil Sonawane

All four datasets we need are free and available. One trains the crop model, one gives prices, one gives weather, and one tests the model on real Indian data.

| Dataset | What it gives | Use in our project | Access |
| --- | --- | --- | --- |
| Kaggle Crop Recommendation | Soil + weather inputs, 22 crops | Train the suitability model, baseline | Free download |
| Agmarknet (India Data Portal mirror) | Daily mandi prices | Train the price forecast | Manual download, free |
| NASA POWER | Temperature, humidity, rainfall | Live weather for any location | Free, no key |
| DES district area-production-yield (replaces ICRISAT) | Real district crop data | District yield + real-world test | Direct download, free |

## 1. Main training data: Kaggle Crop Recommendation

- 2,200 rows, 22 crops, 100 rows per crop.
- 7 inputs: Nitrogen (N), Phosphorus (P), Potassium (K), pH, temperature, humidity, rainfall.
- Link: [kaggle.com/datasets/atharvaingle/crop-recommendation-dataset](https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset)
- Use: train the "which crop grows well" model. Also our baseline, since most papers use it.

## 2. Market prices: Agmarknet (Government of India)

- data.gov.in publishes daily mandi prices, generated from the Agmarknet portal.
- Each record has the daily wholesale minimum, maximum and modal price.
- Needs a free API key from data.gov.in.
- Better for history: Ashoka University's CEDA portal has mandi prices and arrivals since 2001, for 344 commodities across 650+ districts.
- Use: train the price forecast model (LSTM or Prophet).
- **What we used (Oct 30):** CEDA went offline, so we used the India Data Portal copy of Agmarknet,
  "APMC Arrivals and Prices" (Old Data + New Source zips), downloaded by hand into `data/raw/apmc/`.
  Covers 2021-01-01 to 2026-05-31, daily, by market. Loader: `mandi_prices()` in `project/data.py`.
  21 of 22 Kaggle crops are covered. Kidney beans have no price data. Moth beans only trade as split dal (proxy).

## 3. Weather: NASA POWER

- Free, open data from 1981 to now, at hourly, daily, monthly and annual levels.
- No login or API key needed.
- Has an agroclimatology section made for crop models.
- Python: `pip install pynasapower`
- Use: get live temperature, humidity and rainfall for any location.

## 4. Real-world test data: ICRISAT District-Level Database

- 74 datasets, 1,030 variables, over 11 million data points, free and open.
- Covers 571 districts in 20 states, 1966–2017.
- Includes crop area, production, irrigation, land use, and more.
- Get it at [data.icrisat.org/dld](http://data.icrisat.org/dld/src/crops.html) and export as CSV.
- Use: check if our model works on real Indian data, not just Kaggle.
- **What we used (Oct 30):** ICRISAT stayed offline, so we used the Ministry of Agriculture's (DES) district-wise
  area, production and yield data, from the India Data Portal ("Crop Wise Area Production Yield").
  1997-98 to 2022-23, 740 districts, 34 states. It's newer than ICRISAT (which stops at 2017).
  Downloaded by `district_yield()` in `project/data.py` into `data/raw/apy/`.
- Field crops are covered well up to 2022-23. Fruits are thin and old (most stop by 2015), muskmelon is missing,
  and watermelon and apple have no usable rows. See `build-log.md`.

**Nov 4:** prices, district yields and CACP costs now also cover wheat, soybean, groundnut, bajra, jowar, mustard,
sesamum, ragi, barley, potato, onion and sugarcane (`NEW_CROPS` in `project/data.py`).

## 5. Soil: Soil Health Card (added Nov 3)

- "Soil Nutrient Analysis" from the Soil Health Card scheme, India Data Portal (1.1 GB CSV, updated Feb 2026).
- 2023-24 and 2024-25, 738 districts, down to village level.
- Only counts of samples per class: N, P, K, organic carbon Low/Medium/High, pH Acidic/Neutral/Alkaline, EC, micronutrients.
  No measured values, so district values are estimated from class midpoints (`district_soil()` in `project/data.py`).
- Class limits (card template, SHC Operational Guidelines 2015 and District Manual 2017): pH Acidic < 6.5, Normal
  6.5–8.2, Alkaline > 8.2 (the file calls Normal "Neutral"); P 28/56 and K 140/280 kg/ha; N 280/560 kg/ha (ICAR).
  86% of India's pH samples are Normal, so district pH varies little. Until Nov 4 the code assumed pH 6.5/7.5,
  P 10/25, K 120/280 (`research/notes/2026-11-04_soil_fill_check.md`).
- Use: district soil for the real-world check (notebook 08), the district crop model (notebook 09) and the app's
  "no card" soil fill (`recommend.area_soil`, notebook 10).
- Finding: these soil test values are on a different scale from Kaggle's N, P, K (see `build-log.md`, Nov 3).

## One honest gap

No single dataset has soil, crop and price for the same farm. The Kaggle data also has no location column. So we join datasets by crop name and district, and state this as a limitation in the paper.

## How the datasets fit together

1. Farmer enters soil values and location.
2. NASA POWER fills in the weather.
3. ML model gives the top 3 suitable crops.
4. Price model ranks them by expected profit.
5. SHAP explains the choice.

## Sources

- [Kaggle Crop Recommendation dataset](https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset)
- [data.gov.in: Current daily mandi prices](https://data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi)
- [data.gov.in: Variety-wise daily market prices](https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity)
- [CEDA Agri Market Data](https://agmarknet.ceda.ashoka.edu.in)
- [CEDA README](https://agmarknet.ceda.ashoka.edu.in/README.html)
- [NASA POWER](https://power.larc.nasa.gov/)
- [pynasapower on PyPI](https://pypi.org/project/pynasapower/)
- [TCI–ICRISAT District-Level Database](https://tci.cornell.edu/data)
- [TCI and ICRISAT database announcement](https://tci.cornell.edu/?p=796)
