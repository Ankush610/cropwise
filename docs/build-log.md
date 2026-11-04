# Build Log

## Oct 29, 2026 · Phase 1 (data), day 1

**Setup**
- Python 3.12 env in `.venv/` (matches Colab). Packages in `requirements.txt`.
- Loaders in `project/data.py`. Downloads are cached in `data/raw/`.
- Check notebook: `notebooks/01_data_check.ipynb`.

**Sources**
| Source | Status |
| --- | --- |
| Kaggle | ✅ Downloaded with `kagglehub`, no account needed. 2,200 rows, 22 crops × 100. |
| NASA POWER | ✅ Monthly API, no key. `nasa_weather(lat, lon)` returns temperature, humidity, rainfall (mm/month). |
| CEDA prices | ⏳ Site only offers downloads through its web page. Needs a manual CSV export. |
| ICRISAT | ⏳ `data.icrisat.org` unreachable (terminal and browser). Backup: district-wise crop production on data.gov.in. |

**Finding: Kaggle's weather doesn't match real weather** (open question #1 in `architecture.md`)

For 8 crops we compared Kaggle's average weather with NASA POWER at a place known for growing that crop.
Table: `research/results/2026-10-29_weather_vs_kaggle.csv`.

| Feature | Avg gap, yearly mean | Avg gap, growing season |
| --- | --- | --- |
| Temperature | 2.7 °C | 2.5 °C |
| Humidity | 23 points | 19 points |
| Rainfall | 46 mm | 79 mm |

- Temperature matches well.
- Rainfall matches the **mean monthly total over the year** for cotton, maize and apple, but not for rice, grapes or mango.
- **Humidity doesn't match at all.** Kaggle's chickpea averages 17% humidity, while Vidisha (a chickpea area) averages 55%. Kaggle's apple is 92%, Shimla is 56%.
  No Indian growing region looks like Kaggle's chickpea or kidney-bean rows.

This is more evidence that the Kaggle weather columns are synthetic. A model trained on them and fed real weather
can't recommend crops whose Kaggle humidity never happens in reality.

**Decision**
- App weather input = **10-year mean** (2015–2024) of temperature and humidity, and **mean monthly rainfall**. It had the smallest overall gap.
- Phase 2 adds a test: train **with vs without humidity**, and compare cross-validation accuracy and the real-world district match.
  Either result goes in the paper.

## Oct 30, 2026 · Phase 1 (data), day 2

**Prices: CEDA offline, switched to the India Data Portal mirror of Agmarknet**
- CEDA stopped responding (browser and terminal). The India Data Portal has the same Agmarknet data as
  "APMC Arrivals and Prices", in two zips: Old Data (3.6 GB CSV, 2021-01-01 to 2025-10-26) and
  New Source (0.8 GB CSV, 2025-10-27 to 2026-05-31). Downloaded by hand into `data/raw/apmc/`.
  The portal page said 2019, but the files start in 2021. That gives 65 months with no gap or overlap.
- `mandi_prices()` in `project/data.py` streams both zips (~30 s) and writes `data/processed/prices_monthly.csv`:
  one row per crop × state × month, with the **median modal price** (Rs/quintal) over all market-days and the row count `n`.
- Kept only Rs/quintal rows (dropped Rs/number, Rs/bundle, Rs/unit) and prices > 0. Median, not mean, so bad entries don't skew it.
- The two files spell some state names differently ("Jammu and Kashmir" vs "Jammu And Kashmir"), so they're title-cased. 31 states.

**Crop mapping** (`APMC_NAMES`): 21 of 22 Kaggle crops have prices for all 65 months.
Coverage table: `research/results/2026-10-30_price_coverage.csv`.
- rice → **paddy** (what farmers sell). chickpea → Bengal gram, pigeonpeas → arhar/tur, mango → mango + mango (raw-ripe).
- mothbeans → **Moath Dal** proxy. Only the split dal is traded, priced above whole grain. Thin: 6 states.
- coffee is thin: 2 states, ~5k rows.
- **kidneybeans: no price data** (no rajma in the file). Ranked by suitability only, flagged in the app.

**District yield: ICRISAT still offline, switched to DES area-production-yield**
- `data.icrisat.org` still times out. The India Data Portal has the Ministry of Agriculture's (DES) district-wise
  "Crop Wise Area Production Yield", 1997-98 to 2022-23, 740 districts, 34 states. It downloads directly, with no sign-up.
  It's newer than ICRISAT (which stops at 2017) and uses LGD district codes, the same codes as the APMC price data.
- `district_yield()` writes `data/processed/district_yield.csv`: per crop and district, the mean yield (t/ha) and area (ha)
  over that district's **last 5 reported years**, plus `last_year` so stale values are visible.
- **Fixes in the raw data:**
  - Some district-years have a "Total" row as well as the seasonal rows (~107k seasonal rows affected), so a plain sum double-counts.
    We use Total when present, else the sum of seasons.
  - Everything is labelled "Tonnes", but cotton is bales of lint (170 kg), jute is bales (180 kg) and coconut is nuts.
    Converted to what the mandi prices: cotton → kapas (lint ÷ 34% ginning outturn), jute → tonnes,
    coconut → tonnes at **~0.6 kg/nut (an assumption, to check)**.
  - Zero production is treated as missing.
- **Coverage** (`research/results/2026-10-30_yield_coverage.csv`):
  - Good, 2022-23 data in 400–720 districts: rice, maize, chickpea, pigeonpeas, mungbean, blackgram, lentil, cotton.
  - Usable: banana, coconut, jute, mothbeans (80–290 districts).
  - Old: papaya, mango, orange and grapes are 70–150 districts, but the data stops between 2015 and 2019.
  - Almost none: kidneybeans (9 districts), pomegranate (9), coffee (3).
  - **None: watermelon, muskmelon, apple.**
  - Horticulture isn't really in DES data. If fruit yields matter, the National Horticulture Board publishes state-level yields.
- **District coordinates for free:** `district_coords()` takes the median lat/lon of each district's APMC markets.
  625 of 739 districts are covered. The 114 without a market are mostly in Arunachal Pradesh, Jharkhand and the Northeast.
  Spot-checked Nashik, Shimla, Vidisha, Raipur, Ludhiana and Thiruvananthapuram. No geocoding needed.
- `notebooks/01_data_check.ipynb` now loads all four sources and runs end to end. **Phase 1 exit criterion met.**

**Data overview doc**
- Shared doc "Crop Recommendation Data Overview" (https://claude.ai/artifact/7YR6Zk556snNTkmJt6tTvX).
  It has sample rows from all five tables, the file and loader for each, a data → pipeline-step diagram, and gaps per dataset.
  Private until shared from its Share menu.

## Nov 3, 2026 · Phase 2 (crop model)

Two days behind plan (was due Nov 1). Notebook: `notebooks/02_crop_model.ipynb`.

**Setup** (for the paper)
- Data: Kaggle Crop Recommendation, 2,200 rows, 22 crops × 100. No duplicates, no missing values.
- Stratified 5-fold CV, shuffled, seed 42. Metrics: accuracy, macro F1, top-3 accuracy (the app shows 3 crops).
- Models, near-default settings, no tuning: LogReg (scaled, max_iter 2000), Random Forest (300 trees),
  XGBoost (300 trees, lr 0.1), LightGBM (300 trees). Each run with all 7 features and without humidity.
- Added scikit-learn 1.9.1, XGBoost 3.4.1, LightGBM 4.7.0 to `.venv` and `requirements.txt`.

**Results** (`research/results/2026-11-03_crop_model_cv.csv`, figures in `research/figures/crop_*.png`)

| Model | Acc. with humidity | Acc. without | Top-3 without |
| --- | --- | --- | --- |
| LogReg | 0.971 ± 0.002 | 0.901 ± 0.006 | 0.992 |
| Random Forest | **0.995 ± 0.003** | **0.984 ± 0.005** | **1.000** |
| XGBoost | 0.993 ± 0.003 | 0.979 ± 0.009 | 0.999 |
| LightGBM | 0.993 ± 0.003 | 0.981 ± 0.004 | 0.998 |

- The three tree models are within one std of each other. LogReg falls 7 points without humidity.
- Dropping humidity costs RF 1.1 points of accuracy and nothing in top-3.
- Errors without humidity: rice → jute (8 of 100), pigeonpeas → kidneybeans (5), and mix-ups among the pulses.
  Feature importance: rainfall > K > P > N > temperature > pH.

**Decision: the app uses Random Forest without humidity.** NASA humidity doesn't match Kaggle's (19–23 points off),
so training on it would feed the app values the model never saw. Saved as `models/crop_model.joblib`
(model, feature list, class names). Answers open question #1's follow-up in `architecture.md`.

**Caveat:** ~98–99% mostly shows the Kaggle data is clean and well separated (likely synthetic). The Nov 5–6
real-world check is what tests whether it works on real districts.

## Nov 3, 2026 · Phase 3 (price model)

Notebook: `notebooks/03_price_model.ipynb` (~10 min to run, mostly Prophet backtest fits).

**Setup** (for the paper)
- Data: `prices_monthly.csv`, Jan 2021 – May 2026. Series = crop × state monthly median price, plus an all-India
  series per crop (market-day-weighted mean of state medians). 417 series; 296 have ≥ 24 months before a cutoff.
- Methods: naive (last value), seasonal-naive (same month last year), blend (average of the two),
  Prophet 1.5.0 (defaults, yearly seasonality, fit on log price).
- Rolling-origin backtest: cutoffs May 2024, Nov 2024, May 2025, each forecasting 12 months. 8,431 forecast-months.
  MAPE per series, then median across series. Only months where every method has a forecast.
- **Method chosen on 4–12 months ahead**, the gap between sowing and selling.

**Results** (`research/results/2026-11-03_price_backtest.csv`, figures `research/figures/price_*.png`)

| Method | 1–3 mo | 4–6 mo | 7–12 mo | 4–12 mo, median MAPE |
| --- | --- | --- | --- | --- |
| Naive | **9.9** | 16.7 | 18.4 | 19.4 |
| Seasonal-naive | 15.9 | 16.0 | 17.5 | **17.3** |
| Blend | 11.4 | 15.2 | 17.1 | 17.5 |
| Prophet | 16.4 | 18.5 | 23.7 | 22.9 |

- **Prophet loses at every horizon.** On short state series it extrapolates the trend: 21 of 296 series go above 100%
  error. Not tuned; the plan only asked for Prophet vs seasonal-naive, and it's clear.
- Naive wins short-term but can't show seasons (it says mango pays the same in June and September).
- **Decision: seasonal-naive** (ties with blend, simpler, it was the planned baseline).
- Field crops forecast well (rice, cotton, lentil 2–7% all-India); fruit, pigeonpeas and coconut are 17–44%.

**Output:** `data/processed/price_forecast.csv`: crop, state, month (Jun 2026 – May 2027), price (Rs/quintal),
method, mape (that series' 4–12-month backtest error). 309 series: 21 crops all-India + 288 crop × state.
The ranker uses the state series when it exists, else All India. kidneybeans has no price.
Added `prophet` to `requirements.txt`. LSTM stays cut (scope cut in `plan.md`).

## Nov 3, 2026 · Phase 4 (ranking + SHAP)

**`project/recommend.py`**: the one place the app, agent and notebooks get recommendations from.
- `recommend(N, P, K, ph, district, state=None, sow=None)` → (inputs, table). District name → LGD code → market
  coordinates → NASA POWER 10-year means (cached in `data/raw/nasa_power/`) → Random Forest suitability → top 3 with
  suitability ≥ 5% (`MIN_SUITABILITY`; the top crop always shows).
- Expected revenue (Rs/ha) = suitability × yield (t/ha) × 10 × price (Rs/quintal).
  - Yield: district → state median → India median; `yield_source` says which.
  - Price: state series → All India; `price_source` and `price_mape` say which and how good.
    Sold at sowing month + `GROW_MONTHS` (3–6 months for field crops); perennials use the 12-month mean.
  - Crops with no yield or price stay in the table, ranked last.
- `explain(inputs, crop)` → SHAP values (TreeExplainer) for that crop's suitability; plot with `shap.plots.waterfall`.
- Self-check: `python project/recommend.py` (checks the ranking order and that SHAP values add up to the probability).
- Added `shap` 0.54.1 to `requirements.txt`.

**Notebook `notebooks/04_ranking.ipynb`**: 5 example farms, each with the Kaggle mean soil of its district's best-known
crop, sown Nov 3. Table: `research/results/2026-11-03_ranking_examples.csv`, SHAP plots `research/figures/shap_*.png`.
Only a check that the pieces fit, not a paper result.

| District | Known for | Model's top pick | Ranked 1st by revenue |
| --- | --- | --- | --- |
| Raipur | rice | jute (rice 0%) | papaya |
| Yavatmal | cotton | cotton | cotton |
| Vidisha | chickpea | chickpea | papaya |
| Nashik | grapes | grapes | grapes |
| Ludhiana | maize | maize | maize |

**Problems found**
1. **Rice fails on real weather.** Raipur's mean rainfall is 116 mm/month; Kaggle rice rows average 236. SHAP: rainfall
   pushes rice down by 0.11. Irrigation isn't an input. Expect this in the real-world check.
2. **Revenue ranking favours fruit.** Papaya grosses ~Rs 9 lakh/ha vs chickpea's ~Rs 0.8 lakh, so a 24%-suitable papaya
   beats a 62%-suitable chickpea. Revenue ignores cost, orchard set-up years and risk. **Open decision** (see below).

## Nov 3, 2026 · Model research and tests

User asked for literature-backed testing of all three parts. Full write-up with sources:
`research/notes/2026-11-03_model_research.md`. Notebooks 05 (crop), 06 (price), 07 (ranking).

- **Crop model:** no model or tuning beats Random Forest on clean data (5×5 CV, corrected t-test). But under the measured
  Kaggle-vs-NASA weather gap every model falls to 72–77% accuracy. Training RF on 5 noisy copies of the rows keeps 89%
  (top-3 99.8%) at the cost of 98.4% → 93.6% on clean rows. Isotonic calibration fixes RF's under-confident probabilities
  (ECE 0.059 → 0.013).
- **Price model:** median of AutoETS, AutoARIMA, AutoTheta and seasonal-naive beats seasonal-naive at 4–12 months
  (16.5% vs 17.4% median MAPE, better on 62% of series, Wilcoxon p = 0.001). Global LightGBM is worse (19.2%).
  Added `statsforecast` 2.1.1 to `requirements.txt`.
- **Ranking:** downloaded CACP cost of cultivation (`data/raw/cost/cost-of-cultivation.csv`, India Data Portal, 20 states,
  1996-2022, 9 of our crops, no fruit). A2+FL is 50–76% of gross value. Gross revenue predicts what districts grow no better
  than random (Spearman 0.06; banana #1 by revenue in 41% of districts, by area in 0.3%). On Kaggle out-of-fold rows,
  multiplying by revenue drops "right crop first" from 98.4% to 94.5% for no gain; using net return only among near-ties
  (suitability ≥ 0.8 × top) keeps 98.5%.
- The three changes were applied the same day after the user approved (next entry).

## Nov 3, 2026 · Applied the three improvements

User approved all three. Details and tables: `research/notes/2026-11-03_model_research.md`, section 5.

- **Crop model:** Random Forest (no humidity) trained on the rows plus 5 weather-noised copies, then isotonic calibration
  (`CalibratedClassifierCV`, `ensemble=False`, calibration folds grouped by original row). Trained and saved by
  `notebooks/05_crop_model_tests.ipynb`, section 5. Before saving, tested the combination: 88.3% accuracy and ECE 0.038 under
  real-sized weather noise (uncalibrated augmented: 88.9%, ECE 0.063; old model: 74.2%, 0.078). Clean Kaggle accuracy
  drops to 93.1%; that's the price of robustness. `models/crop_model.joblib` now holds `model` (calibrated) and
  `forest` (for SHAP).
- **Price forecast:** `notebooks/06_price_model_tests.ipynb`, section 4, writes `data/processed/price_forecast.csv` with the
  median of ETS, ARIMA, Theta and seasonal-naive. Same 309 series; prices moved 8.2% (median) from seasonal-naive.
- **Ranking:** `project/recommend.py` now orders by suitability, and re-orders by net return only among crops ≥ 0.8 × the
  top crop's suitability. New columns `cost_share`, `cost_source`, `net_rs_ha`, `near_tie`; `expected_rs_ha` is gone.
  New loader `data.cost_shares()` (CACP A2+FL ÷ gross value, median 2017-18 to 2021-22, plus All-India rows).
- **SHAP** now explains the forest before calibration (SHAP can't see through the calibrator). Isotonic is monotone per crop,
  so the direction of each push holds, but the SHAP total is the forest score, not the shown suitability.
- Notebooks 02 and 03 no longer write the app files (that would undo this if re-run); re-run 02, 03, 04, 05, 06.
  Removed the stale `shap_raipur_papaya.png` and `shap_vidisha_papaya.png`.
- **Example farms (04):** known crop in top 3 for 5 of 5 farms, first for 4 of 5 (was 4 and 3). Raipur picks jute over
  rice (0.92 vs 0.08); rice was 0 before. CACP costs are large: net return for Maharashtra cotton and Punjab maize is
  only ~Rs 7,000/ha.
- `python project/recommend.py` self-check passes (near-ties first and sorted by net, the rest by suitability, SHAP adds up).

## Nov 3, 2026 · Phase 5 (real-world check)

User chose Soil Health Card district soil over Kaggle crop-mean soil (which would leak the answer).
Full write-up: `research/notes/2026-11-03_real_world_check.md`. Notebook `notebooks/08_real_world_check.ipynb`.

- **New data:** Soil Health Card "Soil Nutrient Analysis" (India Data Portal, 1.1 GB, 2023-24 and 2024-25,
  738 districts) in `data/raw/shc/`. It only has sample counts per class (N, P, K Low/Medium/High, pH Acidic/Neutral/Alkaline),
  not values. New loader `data.district_soil()`: count-weighted mean of class midpoints (ICAR limits), cached in
  `data/processed/district_soil.csv` (717 districts). Cached NASA POWER weather for all 625 districts with coordinates.
- **Result: no better than chance.** 539 districts with soil, coordinates and DES area. Main crop in the top 3:
  SHC raw 7.8%, SHC mapped to Kaggle scale 13.2%, random 3 crops 16.0%, always "rice, cotton, maize" 87.6%.
- **Why:** Kaggle N, P, K are not soil test values (SHC N is 210–650 kg/ha everywhere, Kaggle N is 0–140; Kaggle's
  per-crop means look like fertiliser doses). Season-matched rainfall doesn't help. Given the Kaggle soil of each
  district's own main crop, the model gets it in the top 3 for ~100% of districts. So the model reads the crop off
  Kaggle's N-P-K clusters, and real soil never falls in them.
- **App impact:** a farmer typing their Soil Health Card values gets chickpea in 89% of districts. **Open decision**
  before the demo: keep the Kaggle model and report the failure, or train a district-level model on real data.

## Nov 4, 2026 · District crop model replaces the Kaggle model

User decided: commit the real-world check (`58e221a`), then build a model on real data. Write-up:
`research/notes/2026-11-04_district_model.md`. Notebook `notebooks/09_district_model.ipynb` (~20 min to run).

- **Kaggle model kept, not deleted:** renamed to `models/kaggle_crop_model.joblib`. Notebook 05 now saves to that name;
  notebooks 04 and 08 set `recommend.MODEL_FILE` to it, so re-running them reproduces their Kaggle results.
- **District model** (`models/crop_model.joblib`): Random Forest on 539 districts, Soil Health Card soil + NASA weather,
  target = DES area share of 16 crops (one row per district × crop, weighted by share). No calibration step.
- **Leave-one-state-out:** main crop in the list 89.8% (Kaggle model 7.8%, "3 most common crops" 82.6%); first 68.3%
  (popularity 69.0%). Gain over popularity +7.2 pts (95% CI 3.9–10.4). Season weather +3.9 pts (CI 1.1–6.5), so adopted.
  RF and logistic regression are level; LightGBM worse.
- **App changes** (`project/recommend.py`): `weather()` also returns kharif (Jun–Sep) and rabi (Nov–Feb) rainfall and
  temperature; `recommend()` takes N, P, K in kg/ha as on a Soil Health Card; SHAP now adds up to the suitability shown.
  Self-check uses card-scale soil (Raipur → rice 0.97).
- **Known data quirk:** CACP A2+FL cost exceeds gross value for 9 crop × state pairs (e.g. Maharashtra paddy 1.47), so
  net return is negative there (Nashik rice). These are the survey's numbers, left as they are.
- **Open question:** the crop list is still Kaggle's. Wheat, sugarcane, soybean, groundnut, mustard and bajra are not
  covered, which limits both the app and the evaluation.

## Nov 4, 2026 · 12 more crops (28 in the district model)

User agreed the crop list needed the major crops Kaggle lacks. Committed the 16-crop stage first (`0d2b9d9`).

- **Added:** wheat, soybean, groundnut, bajra, jowar, mustard, sesamum, ragi, barley, potato, onion, sugarcane, in
  `APMC_NAMES`, `APY_NAMES`, `CACP_NAMES` (`project/data.py`, list in `NEW_CROPS`) and `GROW_MONTHS` (`recommend.py`).
  Sugarcane barely trades at mandis (737 rows, 2 forecast series), but its forecast (~Rs 356/quintal) sits at the FRP.
- **Rebuilt** `prices_monthly.csv` and `district_yield.csv`, re-ran notebook 06 (469 forecast series, was 309;
  the old 309 are unchanged). Backtest table now `research/results/2026-11-04_price_model_tests.csv`.
- **Notebooks 07 and 08** now drop `NEW_CROPS`, so re-running them reproduces their Nov 3 results.
- **District model (notebook 09), 28 crops, leave-one-state-out:** main crop first 62.0% (popularity 50.1%),
  in list 79.8% (76.3%). Logistic regression is 2.8 pts better on "in list" (CI 0.6–5.0); RF kept for SHAP.
  Write-up: `research/notes/2026-11-04_district_model.md`, "Update" section.
- CACP: ragi's surveyed cost exceeds its value (share 1.12), so its net return is negative everywhere.

## Nov 4, 2026 · Phase 6a (Streamlit demo)

**`project/app.py`**, run from the repo root with `.venv/bin/streamlit run project/app.py` (or the `demo` entry in
`.claude/launch.json`). Added `streamlit` 1.66.1 to `requirements.txt`.
- Sidebar: state → district (the 625 districts with coordinates), Soil Health Card N, P, K (kg/ha) and pH, sowing date.
  Soil boxes start at the district's SHC average (districts with ≥ 100 tests); otherwise 250 / 20 / 230 / 7.0 with a
  note to type the card's values.
- Main: weather (year, kharif, rabi), ranked table (suitability bar, net return, yield, price at harvest, price forecast
  error, cost and yield source), plain-language notes (near-ties ordered by net return, negative net = CACP cost above
  value, price error > 30% = uncertain), and one tab per crop with a SHAP waterfall and a one-line reason.
- Tested in the browser: Vidisha → wheat, soybean, chickpea (real top 3: soybean, wheat, chickpea); Ludhiana (no SHC
  average, not in training) → wheat, sugarcane, rice; Thanjavur → rice, coconut, potato. SHAP total matched the
  suitability shown (Vidisha wheat 0.337).
- Borderline third picks can flip with small input changes: Thanjavur's third crop is potato with the rounded soil
  values in the app, blackgram with unrounded values in notebook 09 (both ~8%).
- Not yet: the consultant agent chat box (Phase 6b, `docs/agent.md`).

## Nov 4, 2026 · Spot check against public sources

User asked to verify the demo's results with web search. Details and sources: `research/notes/2026-11-04_district_model.md`,
"Spot check" section. Vidisha matches; Ludhiana gets wheat and rice right but ranks sugarcane 2nd (it grows ~2,500 ha);
Thanjavur's potato is a stale DES row. Wheat, soybean and sugarcane prices match MSP/FRP/mandi reports; Ludhiana wheat
and sugarcane yields match.
**Bugs:** (1) DES rice is milled rice but prices are paddy, so rice revenue is ~1/3 low; (2) `district_yield()` keeps
series that stopped before 2010 (1,105 of them). **Gap:** procurement states lack mandi paddy prices (MSP would fit).
Not fixed yet.

## Nov 4, 2026 · Fixes from the spot check

User chose: fix both bugs and use MSP.
- `data.py`: rice converted from milled rice to paddy (`APY_TO_TONNES["rice"] = 1/0.67`); `district_yield()` drops
  series last reported before 2010-11 (`STALE_BEFORE`, 1,105 series). Rebuilt `district_yield.csv` (old copy in the
  session scratchpad).
- `recommend.py`: MSP 2026-27 for paddy (2,441) and wheat (2,585) in Punjab and Haryana (`MSP`, `PROCUREMENT_STATES`);
  self-check asserts it. App shows a "Price source" column, "–" for the error of an MSP price, and a one-line MSP note.
- Notebook 09 re-run: 27 crops (grapes dropped, < 20 districts once stale rows went). App model: main crop first
  62.2%, in list 80.3% (popularity 50.1%, 76.3%); +4.1 pts over popularity, CI 0.7–7.6.
- Notebook 07 re-run with paddy yields, outputs now dated `2026-11-04_ranking_*.csv` (Nov 3 files kept). Revenue
  scores agree better with what districts grow but still trail yield alone; τ = 0.8 rule unchanged.
- Re-check: Thanjavur's third crop is now blackgram (was a stale potato row); Vidisha unchanged; Ludhiana rice now at
  MSP with paddy yield. Still wrong: sugarcane ranked high in Ludhiana and Karnal.
- Not re-run: notebook 04 (old Kaggle model, superseded) still shows the pre-fix rice numbers.
- Docs: `architecture.md` (yield and price rows, 27 crops), `agent.md` (rank out of 27).

## Nov 4, 2026 · Soil values for farmers without a card

Discussed with the user: an ML model predicting soil from location would only learn district averages (we have no
field-level SHC data), would help pH but hardly N, P, K, and would add nothing the crop model doesn't already get from
weather. Chosen instead: nearest districts.
- `recommend.area_soil(district)`: the district's SHC average if it has ≥ 100 tests (as in training), else the mean of
  the 3 nearest such districts (flat-earth distance between market-centroid coordinates). Self-check covers both.
- App: "Do you have a Soil Health Card?" Yes → soil boxes prefilled with the area values, editable. No → the same values,
  locked, captioned as an estimate for the area with their source. The results caption says which soil was used.
  The old fixed default (250 / 20 / 230 / 7.0) is gone.
- Ludhiana (1 SHC test) now gets SBS Nagar, Una and Bathinda's mean → wheat 44%, rice 33%, sugarcane 15% (was wheat,
  sugarcane, rice with the fixed default): closer to what it grows. Amritsar: wheat, rice, sugarcane. Karnal still puts
  sugarcane first (neighbours Kurukshetra, Shamli, Saharanpur; the last two are UP cane districts).

## Nov 4, 2026 · How good is the soil fill?

Notebook 10 (`10_soil_fill_check.ipynb`), write-up `research/notes/2026-11-04_soil_fill_check.md`.
- Leave one district out over 539 districts: 3 nearest districts cut the error of a single India-wide value by 41% (N),
  27% (P), 32% (K), 56% (pH); same card class 74–93%. State mean or same-state neighbours are level; kept 3 nearest.
- Filled districts are farther from data (median 87 vs 56 km) and sit in Rajasthan, Punjab, Haryana, Kerala.
- Web check: Ludhiana pH matches a 2020 study; Karnal N and K in the right class, P borderline, pH too low (8.1–8.4
  reported); Thiruvananthapuram pH 6.9 vs 5.48 reported.
- Open question: SHC labels 86% of India's pH samples "Neutral" (Sirsa 91%), so our pH values may be compressed;
  class limits in `data.SHC_LEVELS` need checking. Nothing changed in code.

## Nov 4, 2026 · Soil Health Card class limits fixed

User asked to check the pH classes. The card template in the SHC Operational Guidelines (2015) and District Manual
(2017) rates pH Acidic < 6.5, Normal 6.5–8.2, Alkaline > 8.2, and prints P 28/56, K 140/280 kg/ha. The code had assumed
pH 6.5/7.5, P 10/25, K 120/280 (the SHC dashboard and dataset pages give no limits; the portal assigns classes on its server).
- `data.SHC_LEVELS`: pH 5.75 / 7.35 / 8.95, P 14 / 42 / 70, K 105 / 210 / 350. Rebuilt `district_soil.csv`.
- Notebook 09 re-run: within 1 point everywhere (app model first 62.5%, in list 80.5%). Notebook 10 re-run: same skill.
- `area_soil` keeps pH to 2 decimals: rounding 7.35 → 7.3 flipped Vidisha's third crop (the forest has a step at the
  7.35 "all Normal" value). Self-check and app placeholder soil moved to the card scale (P 40, K 210).
- Notebook 08 (Kaggle check) not re-run; its Nov 3 results stay on the old scale.
- Docs: Datasets doc (SHC class limits), research notes (district model "Soil class fix", soil fill check).

## Nov 4, 2026 · Re-check of the soil fill after the class fix

Notebook 10, section 2 (new): crop picks in the 84 filled districts (none in training) vs DES main crop. Fill: main
crop in list 84.5%, first 48.8%; one fixed soil 85.7% / 39.3%; popularity 60.7% / 19.0%. Punjab 100%, Haryana 94%,
Kerala 92%, Rajasthan 61% (arid pulse districts: moth bean, mung bean; no SHC district like them in training).
Web check of soil in 4 more districts. Tally of all class checks on filled districts: N 4/4, K 3/5, pH 3/6, P 1/5.
Write-up: `research/notes/2026-11-04_soil_fill_check.md`, section 3.
