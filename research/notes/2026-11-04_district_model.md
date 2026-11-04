# District crop model · Nov 4, 2026

Question: after the Kaggle model failed the real-world check (`2026-11-03_real_world_check.md`), can a model trained on
real public data recommend what districts actually grow? Notebook: `notebooks/09_district_model.ipynb`. Seed 42.

## Data and settings

| Piece | Source | Settings |
| --- | --- | --- |
| Soil | Soil Health Card 2023-25, `data.district_soil()` | Districts with ≥ 100 tests; N, P, K in kg/ha (card scale), pH |
| Weather | NASA POWER 2015-2024 via `recommend.weather()` (same code as the app) | Year means of temperature, humidity, rainfall; kharif (Jun–Sep) and rabi (Nov–Feb) rainfall and temperature |
| Target | DES district APY, `data.district_yield()` | Area share per crop (each crop's last 5 reported years). Crops in ≥ 20 districts: 16 of the 22 Kaggle crops |
| Districts | Soil + coordinates + DES area | 539 in 28 states |

Training: one row per district × crop with area > 0, weighted by area share, so the predicted probability estimates the
share of farmland that similar districts put under each crop. Validation: leave one state out (28 folds).
Metrics: list = top 3 with probability ≥ 5% (as in the app). Baseline: the 3 crops with the highest mean share in the
training states, refit per fold.

Models: Random Forest (500 trees, min_samples_leaf 3), LightGBM (300 rounds, lr 0.05, 15 leaves, min_child_samples 10),
logistic regression (standardised, C 1). Feature sets: app inputs (N, P, K, pH, temperature, rainfall), + humidity,
+ season weather, weather only, soil only.

## Results (`research/results/2026-11-04_district_model_cv.csv`)

| Method | Main crop 1st | Main crop in list | Picks grown | Area covered | List length |
| --- | --- | --- | --- | --- | --- |
| Kaggle model, SHC raw soil (notebook 08) | 6.3% | 7.8% | 29.7% | – | 3.0 |
| Popularity (training states) | 69.0% | 82.6% | 89.4% | 71.5% | 3.0 |
| RF, app inputs | 67.3% | 85.9% | 93.5% | 74.0% | 2.8 |
| RF, + humidity | 67.3% | 87.0% | 94.3% | 75.3% | 2.7 |
| **RF, + season weather (app model)** | **68.3%** | **89.8%** | **96.6%** | **77.5%** | 2.7 |
| RF, weather only | 60.1% | 82.9% | 93.4% | 72.8% | 2.7 |
| RF, soil only | 67.3% | 83.3% | 91.2% | 71.9% | 2.8 |
| LightGBM, + season weather | 65.9% | 85.7% | 98.9% | 72.8% | 2.2 |
| Logistic regression, + season weather | 70.3% | 87.9% | 97.2% | 75.8% | 2.6 |
| RF, app inputs, random district folds | 73.5% | 90.9% | 96.9% | 79.4% | 2.6 |

Kaggle row: main crop among Kaggle crops with DES data since 2018-19 (notebook 08), so not exactly the same crop set.

Paired bootstrap over districts (2,000 resamples), difference in "main crop in list":

| Comparison | Difference | 95% CI |
| --- | --- | --- |
| RF app inputs vs popularity | +3.3 pts | 0.4 to 6.5 |
| RF + season weather vs popularity | +7.2 pts | 3.9 to 10.4 |
| RF + season weather vs RF app inputs | +3.9 pts | 1.1 to 6.5 |
| Logistic regression vs RF (both + season weather) | −1.9 pts | −4.5 to 1.1 |

By state (main crop in list, app model vs popularity): Gujarat 88% vs 41%, Madhya Pradesh 67% vs 56%,
Karnataka 65% vs 61%; Tamil Nadu 67% vs 72%, Maharashtra 82% vs 85%. Rice states (Odisha, Chhattisgarh, Assam,
West Bengal, Bihar) are 92–100% for both.

## Conclusions

1. Training on real data fixes the transfer failure: main crop in the list for 90% of held-out-state districts vs 8%.
2. The model beats "the most common crops" by 7 points but not at putting the main crop first. Much of the task is easy
   because rice is the main crop in 69% of districts among these 16 crops.
3. Season weather is a real gain; humidity a small one. RF and logistic regression are level; RF kept for SHAP.
4. Ignoring geography in CV inflates the score by 5 points.

## Limits (for the paper)

- Only 16 crops in this first version; wheat, sugarcane, soybean, groundnut, mustard and bajra were missing because the
  crop list came from Kaggle. Fixed the same day (see the update below).
- Suitability is revealed preference (what similar districts grow, which includes irrigation, markets and habit),
  not agronomic fit.
- Trained on district means; the app gets one farm's card, which can fall outside the district range.
- Fruit areas are old (most DES fruit series stop 2003–2019).
- SHC values are class-midpoint estimates; Ludhiana and other districts with < 100 tests are not in training.

## Update, Nov 4: 12 more crops (28 in total)

The 16-crop results above are from commit `0d2b9d9`. The crop list then gained wheat, soybean, groundnut, bajra, jowar,
mustard, sesamum, ragi, barley, potato, onion and sugarcane (DES area, APMC prices and CACP costs exist for all 12).
Same 539 districts, same settings; LightGBM run on the season-weather set only (weakest everywhere with 16 crops).
`research/results/2026-11-04_district_model_cv.csv` now holds the 28-crop table.

Main crop by area: rice 50%, wheat 22%, cotton 6%, maize 5%, soybean 4%, sugarcane 3%, groundnut 2%.

| Method | Main crop 1st | Main crop in list | Picks grown | Area covered | List length |
| --- | --- | --- | --- | --- | --- |
| Popularity (training states) | 50.1% | 76.3% | 95.2% | 61.1% | 3.0 |
| RF, app inputs | 57.7% | 77.9% | 91.7% | 61.6% | 2.8 |
| RF, + humidity | 62.2% | 82.4% | 93.6% | 63.6% | 2.8 |
| **RF, + season weather (app model)** | **62.0%** | **79.8%** | **96.3%** | **64.1%** | 2.7 |
| RF, weather only | 57.9% | 77.0% | 92.8% | 60.1% | 2.8 |
| RF, soil only | 46.0% | 72.0% | 88.8% | 55.8% | 2.8 |
| LightGBM, + season weather | 61.2% | 80.9% | 98.7% | 62.8% | 2.4 |
| Logistic regression, + season weather | 61.2% | 82.6% | 97.3% | 64.8% | 2.8 |
| RF, app inputs, random district folds | 63.8% | 87.0% | 97.3% | 69.0% | 2.7 |

Paired bootstrap, main crop in list: RF + season vs popularity +3.5 pts (CI 0.0 to 6.9); RF + season vs RF app inputs
+1.9 (CI −1.3 to 5.0); logistic regression vs RF (both + season) +2.8 (CI 0.6 to 5.0).

By state (main crop in list, app model vs popularity): Maharashtra 47% vs 26%, Gujarat 53% vs 41%, Karnataka 55% vs
48%, Andhra Pradesh 78% vs 70%; Bihar 86% vs 97%, Tamil Nadu 53% vs 61%.

**Conclusions.** More crops make the task real (popularity drops from 83% to 76% in list, from 69% to 50% first).
The model's clearest gain is putting the main crop first (+12 pts over popularity). Weather carries most of the
signal; soil alone is below the baseline. Logistic regression is slightly better at "in list"; RF is kept for SHAP.

**Prices for the new crops** (`notebooks/06_price_model_tests.ipynb`, re-run Nov 4, `2026-11-04_price_model_tests.csv`):
452 backtest series (was 309). The median of ETS, ARIMA, Theta and seasonal-naive still wins: 16.4% vs 17.9% median MAPE
at 4–12 months, better on 67% of series (Wilcoxon p < 0.0001). New-crop backtest MAPE: wheat 8.6%, soybean 9.2%,
mustard 8.7%, sugarcane 8.9%, groundnut 13.2%, bajra 12.6%; forecast-file MAPE onion 62%, potato 41% (volatile).

## Spot check against public sources (Nov 4)

App output (district SHC soil, sown Nov 4) compared with what web sources report. Not a paper result on its own:
three districts, mixed source years. Use as case studies.

| District | App top 3 | Reported main crops | Verdict |
| --- | --- | --- | --- |
| Vidisha (MP) | wheat, soybean, chickpea | wheat ~3.5 lakh ha (2024-25), soybean, gram; "wheat, soybean and gram" named as main crops | Match |
| Ludhiana (PB), not in training | wheat, sugarcane, rice | wheat 2.45 lakh ha, paddy ~2.57 lakh ha; sugarcane ~2,500 ha (2024-25), down from 94k ha in 2008-09 | Wheat and rice right; sugarcane far too high (similar districts are western UP, which grows cane) |
| Thanjavur (TN) | rice, coconut, potato | paddy (principal, 3 seasons), pulses incl. black gram, coconut, gingelly, groundnut, sugarcane | Rice and coconut right; potato wrong (stale DES row, see below) |

| Number | App | Source | Verdict |
| --- | --- | --- | --- |
| Ludhiana wheat yield | 4.81 t/ha | ~5.0 t/ha 2023-24, 4.59 in 2022-23 | Match |
| Ludhiana rice yield | 4.72 t/ha | paddy 7.0 t/ha (2024) | Same crop, but DES reports **milled rice**; 4.72 / 7.0 = 0.67, the paddy-to-rice ratio. Prices are for paddy, so rice revenue is ~1/3 too low |
| Ludhiana sugarcane yield | 84.4 t/ha | 87.5 t/ha (2024-25) | Match |
| Wheat price, Punjab | Rs 2,585/q | MSP 2026-27 Rs 2,585 | Match |
| Wheat price, MP | Rs 2,370/q | MSP Rs 2,585; MP mandis traded Rs 2,250–2,530 Oct 2025–May 2026 | Below MSP, as MP mandi prices were |
| Soybean price, MP | Rs 6,684/q | Indore-district mandis ~Rs 6,500 (early May 2026); MSP 2026-27 Rs 5,708 | Match |
| Chickpea price, MP | Rs 5,438/q | MSP 2026-27 Rs 5,875 | Plausible (below MSP) |
| Sugarcane price | Rs 373/q | FRP 2026-27 Rs 365 | Match |
| Rice price, Punjab | Rs 2,255/q (All-India fallback) | MSP 2026-27 Rs 2,441; Punjab paddy is procured at MSP | Too low: Punjab has only 20 months of mandi paddy prices, so no state forecast |

**Bugs found**
1. DES rice production is milled rice; the price is for paddy. Fix: convert with ×1.5 (paddy = rice ÷ 0.67) in `APY_TO_TONNES`.
   Affects every rice yield and revenue so far, including notebooks 04 and 07 (rice under-valued by a third).
2. `district_yield()` keeps each crop's last 5 *reported* years, however old. 1,105 crop-district series end before
   2010-11 (mango, papaya, ragi, moth beans, grapes, banana, jute, jowar…), e.g. Thanjavur potato: 12,878–39,613 ha in
   1997-99 at 0.3 t/ha, never reported again. These also enter the district model's target shares.
3. Gap: in procurement states (Punjab, Haryana) mandi paddy and wheat prices are thin; MSP would be the better price.

Sources: ICAR-CRIDA Vidisha contingency plan; vidisha.nic.in; Dataful (Vidisha 2024-25, Ludhiana sugarcane 2024-25);
The Tribune (Ludhiana wheat 2023-24, paddy 2024); ICAR-CRIDA Ludhiana and Thanjavur profiles; TNAU Thanjavur DAP
2017-18; MSP: The Tribune (wheat, Oct 2025), Rural Voice / Daily Excelsior (kharif 2026-27, May 2026); FRP: Rural Voice
(May 2026); NaPanta (Mhow APMC soybean, 6 May 2026).

## Fixes after the spot check (Nov 4)

1. `data.APY_TO_TONNES["rice"] = 1 / 0.67`: DES milled rice → paddy, matching paddy prices. Ludhiana rice 4.72 → 7.05 t/ha
   (Tribune: 7.0).
2. `data.district_yield()` drops series last reported before 2010-11 (`STALE_BEFORE`): 13,150 → 12,045 crop-district
   series. Grapes falls below 20 districts, so the model has **27 crops** (was 28).
3. `recommend._price()` uses MSP 2026-27 for paddy (Rs 2,441) and wheat (Rs 2,585) in Punjab and Haryana, where the
   government buys most of the crop and mandi data is thin. Shown as "MSP 2026-27" with no forecast error.

Notebook 09 re-run (same settings, seed 42, 539 districts, leave-one-state-out). `2026-11-04_district_model_cv.csv`
now holds these numbers; the pre-fix table is the "Update" table above.

| Method | Main crop 1st | Main crop in list | Picks grown | Area covered | List length |
| --- | --- | --- | --- | --- | --- |
| Popularity (training states) | 50.1% | 76.3% | 94.4% | 61.9% | 3.0 |
| RF, app inputs | 57.3% | 77.7% | 90.2% | 62.3% | 2.8 |
| RF, + humidity | 63.1% | 82.0% | 92.3% | 64.2% | 2.8 |
| **RF, + season weather (app model)** | **62.2%** | **80.3%** | **95.7%** | **64.7%** | 2.7 |
| RF, soil only | 46.4% | 72.4% | 87.3% | 56.9% | 2.9 |
| LightGBM, + season weather | 60.1% | 80.9% | 99.0% | 64.1% | 2.4 |
| Logistic regression, + season weather | 61.4% | 82.6% | 96.2% | 65.6% | 2.8 |
| RF, app inputs, random district folds | 64.9% | 85.3% | 95.8% | 69.1% | 2.7 |

Paired bootstrap, main crop in list: RF + season vs popularity +4.1 pts (CI 0.7 to 7.6); RF + season vs RF app inputs
+2.6 (CI −0.6 to 5.6); logistic regression vs RF +2.2 (CI 0.0 to 4.5). Conclusions unchanged; the gain over popularity
is now clear of zero.

Ranking tests (notebook 07) re-run with paddy yields: see `2026-11-03_model_research.md`, "Re-run Nov 4". τ = 0.8 still best.

**Re-check of the spot-check districts** (district SHC soil, or 250/20/230/7.0 without it; sown Nov 4):

| District | Before | After | Reported |
| --- | --- | --- | --- |
| Vidisha | wheat, soybean, chickpea | same | wheat, soybean, gram ✓ |
| Ludhiana | wheat, sugarcane, rice | same; rice now 7.05 t/ha × MSP 2,441 = net Rs 1.02 lakh/ha | sugarcane still wrong |
| Thanjavur | rice, coconut, potato | rice, coconut, **blackgram** | paddy, pulses (black gram), coconut ✓ |
| Karnal (HR, new) | – | sugarcane, wheat, rice | rice and wheat dominate; sugarcane is minor |

Still open: sugarcane is over-ranked in Punjab and Haryana (their nearest districts in weather are western UP cane
belts; neither has ≥ 100 SHC tests, so the default soil is used). Tamil Nadu paddy is priced from mandis (Rs 1,962),
below MSP, though TN also procures; only Punjab and Haryana use MSP.
