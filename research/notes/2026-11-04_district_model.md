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

- Only 16 crops. Wheat, sugarcane, soybean, groundnut, mustard and bajra are missing because the crop list came from
  Kaggle. Adding them needs price forecasts, DES names and CACP costs.
- Suitability is revealed preference (what similar districts grow, which includes irrigation, markets and habit),
  not agronomic fit.
- Trained on district means; the app gets one farm's card, which can fall outside the district range.
- Fruit areas are old (most DES fruit series stop 2003–2019).
- SHC values are class-midpoint estimates; Ludhiana and other districts with < 100 tests are not in training.
