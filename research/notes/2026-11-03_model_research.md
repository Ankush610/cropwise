# Model research and tests · Nov 3, 2026

Question: can we get better results from the three parts we built (crop model, price model, ranking)?
Method: read what the literature does, then test it on our data. Notebooks 05–07. Seeds fixed at 42.

## Summary

| Part | Current | Best found | Gain | Evidence |
| --- | --- | --- | --- | --- |
| Crop model | Random Forest | RF + weather-noise augmentation + isotonic calibration | Accuracy under real-sized weather error 74% → 89%; calibration error 0.059 → 0.013 | Notebook 05 |
| Price model | Seasonal-naive | Median of ETS, ARIMA, Theta, seasonal-naive | MAPE 17.4% → 16.5% at 4–12 months (p = 0.001) | Notebook 06 |
| Ranking | Suitability × gross revenue | Suitability order; net return breaks near-ties | Right crop first 94.5% → 98.5% | Notebook 07 |

**Applied to the app Nov 3** (user approved; see section 5). The Nov 5–6 real-world check should confirm them.

## 1. What the literature says

**Crop recommendation on Kaggle-style data**
- Papers report 97–99% accuracy with Random Forest or XGBoost: 99.3% RF ([Springer 2024](https://link.springer.com/article/10.1007/s44230-024-00081-3)),
  XGBoost 99.1% on a 2,100-row Indian set ([PMC 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10844259/)).
  Most use a single 70/30 split; none validate on real farms. One study found a chronological split cut accuracy a lot.
- A study that generated more rows with CTGAN found the new rows noisier and accuracy lower, i.e. the Kaggle rows are
  unusually clean ([arXiv 2505.21201](https://arxiv.org/pdf/2505.21201)).
- Comparing classifiers with repeated CV needs the corrected resampled t-test, because folds overlap
  (Nadeau & Bengio, 2003, *Machine Learning* 52:239–281).
- Probabilities: boosted trees push probabilities away from 0 and 1; after Platt or isotonic calibration, boosted trees,
  RF and SVMs give the best probabilities ([Niculescu-Mizil & Caruana, ICML 2005](https://mlanthology.org/icml/2005/niculescumizil2005icml-predicting)).
- Covariate shift (training inputs differ from deployment inputs) is the one shift you can detect without labels;
  model-aware tests work for random forests ([Detectron, arXiv 2212.02742](https://export.arxiv.org/pdf/2212.02742v4)).

**Price forecasting**
- M4: 12 of the 17 most accurate methods were combinations of mostly statistical methods; pure ML did poorly
  ([M4 results](https://pure.unic.ac.cy/en/publications/the-m4-competition-results-findings-conclusion-and-way-forward/)).
  Theta won M3 and sits in most good M4 combinations.
- M5 (Walmart daily sales): LightGBM models trained across many series won; 45 of the top 50 used LightGBM
  ([Makridakis et al. 2022](https://ideas.repec.org/a/eee/intfor/v38y2022i4p1346-1364.html)). Different data: 42,840 long daily series.
- Mandi prices: on Assam weekly Agmarknet prices, **naive (16.6% MAPE) beat** Chronos-2, global LightGBM and ETS
  ([arXiv 2610.39949](https://arxiv.org/html/2610.39949)). A Maharashtra monthly study reports a one-month naive
  benchmark with the lowest MAPE for some commodities ([Springer 2026](https://link.springer.com/article/10.1007/s44564-026-00015-0), abstract only).
- Prophet loses to ARIMA and naive baselines in more published comparisons than it wins.

**Ranking crops for a farmer**
- Farm-planning studies rank by **profit and risk**, not gross revenue: TOPSIS on profit, cost, yield and market
  ([Springer 2026](https://link.springer.com/article/10.1007/s43069-026-00679-2)); entropy-weight TOPSIS on profit and ROI
  ([ACM 2025](https://dl.acm.org/doi/10.1145/3718491.3718570)); mean/SD risk-adjusted return
  ([Springer 2026](https://link.springer.com/article/10.1007/s44279-026-00663-8)).
- Perennials must be annualised before comparing with annual crops (NPV / annual equivalent;
  [Seavert et al. 2006](https://www.emerald.com/insight/content/doi/10.1108/00214660680001184/full/html)).
  A mango orchard in Rewa (MP) had costs only in years 1–6 and first income in year 7
  ([Plant Archives](https://plantarchives.org/article/152%20EVALUATION-OF-NET-PRESENT-VALUE-AND-INTERNAL-RATE-OF-RETURN-UNDER-MANGO-ORCHARD-IN-REWA-DISTRICT,-MADHYA-PRADESH,-INDIA.pdf)).
- India's cost data: CACP cost of cultivation, state × crop × year, Rs/ha (A2+FL, C2). Downloaded from the
  [India Data Portal](https://ckandev.indiadataportal.com/dataset/cost-of-cultivation/resource/be22e37e-acfc-43a9-859c-d4a066489a69)
  to `data/raw/cost/`. 20 states, 1996-97 to 2021-22, 9 of our crops, **no fruit**.

## 2. Crop model tests (`notebooks/05_crop_model_tests.ipynb`)

Features without humidity. Table: `research/results/2026-11-03_crop_model_tests.csv`.
Figures: `research/figures/crop_reliability.png`, `crop_weather_shift.png`.

**Accuracy (5×5 repeated CV; p = corrected resampled t-test vs Random Forest)**

| Model | Accuracy | Brier | ECE | p (accuracy) |
| --- | --- | --- | --- | --- |
| Random Forest (current) | 98.5% | 0.037 | 0.059 | — |
| RF + isotonic calibration | 98.4% | **0.026** | **0.013** | 0.76 |
| RF + sigmoid calibration | 98.5% | 0.028 | 0.055 | 0.67 |
| LightGBM | 98.1% | 0.032 | 0.017 | 0.22 |
| XGBoost | 97.8% | 0.035 | 0.015 | 0.10 |
| ExtraTrees | 97.9% | 0.062 | 0.110 | 0.03 (worse) |
| LogReg | 90.6% | 0.176 | 0.153 | < 0.001 (worse) |

- **No model beats Random Forest on accuracy**, and nested-CV tuning adds nothing (tuned RF 98.4%, XGB 97.9%, LGBM 98.2%).
  At ~98.5% on clean data there is little left to gain.
- **RF probabilities are under-confident** (ECE 0.059): averaging 300 trees pulls them toward the middle.
  Isotonic calibration cuts ECE to 0.013 and Brier by 28% (p < 0.001) without changing accuracy. This matters because
  the ranker reads the probabilities. Small cost: top-3 accuracy 99.8% instead of 100%.

**Real-weather shift (test rows perturbed by the measured Kaggle-vs-NASA gap: temperature ±3.2 °C SD, rainfall ×/÷ 1.59)**

| Model | Accuracy, clean | Accuracy, shifted | Top-3, shifted |
| --- | --- | --- | --- |
| Random Forest (current) | 98.4% | 74.2% | 94.8% |
| LightGBM | 98.1% | 72.4% | 94.9% |
| XGBoost | 98.0% | 71.5% | 93.1% |
| ExtraTrees | 97.9% | 76.7% | 97.3% |
| **RF trained with noise augmentation** | 93.6% | **88.9%** | **99.8%** |
| LightGBM with noise augmentation | 86.7% | 85.5% | 99.5% |

- **This is the biggest finding.** Every model trained on clean Kaggle rows loses about 25 points of accuracy when the
  weather is as far off as real NASA weather is. The 98% headline won't survive contact with real districts.
- Training on noisy copies of the rows (5 copies with the same noise) trades 5 points on clean Kaggle rows for
  **+15 points under real-sized weather error**, and the right crop is in the top 3 99.8% of the time.
- Caveat: the noise size comes from only 8 crop–place pairs. The Nov 5–6 real-world check on DES districts is the test
  that should decide between the clean and augmented model.

**Recommendation:** Random Forest trained with weather-noise augmentation, then isotonic calibration. Re-check both
on the real-world test.

## 3. Price model tests (`notebooks/06_price_model_tests.ipynb`)

Same backtest as notebook 03 (3 origins × 12 months, 298 series, 6,884 forecast-months at 4–12 months ahead).
Table: `research/results/2026-11-03_price_model_tests.csv`.

| Method | Median MAPE 4–12 mo | Median MASE | Beats seasonal-naive on | Wilcoxon p vs s-naive |
| --- | --- | --- | --- | --- |
| **Median of ETS, ARIMA, Theta, seasonal-naive** | **16.5%** | **0.93** | **62% of series** | **0.001** |
| Mean of ETS, ARIMA, Theta | 16.7% | 0.96 | 58% | 0.15 |
| Seasonal-naive (current) | 17.4% | 1.02 | — | — |
| AutoARIMA | 17.6% | 0.98 | 47% | 0.25 |
| AutoETS | 17.7% | 0.97 | 55% | 0.44 |
| AutoTheta | 19.1% | 1.03 | 44% | 0.0007 (worse) |
| Global LightGBM | 19.2% | 1.03 | 41% | 0.0001 (worse) |
| Naive | 19.8% | 1.03 | 51% | 0.07 |

- **The combination wins**, as M4 predicts: about 1 point (5%) better than seasonal-naive, significant, and better at
  every horizon band (1–3 mo: 10.2 vs 16.8; 4–6: 14.7 vs 17.1; 7–12: 16.9 vs 17.8). All-India series: 15.1% vs 17.0%.
- **Global LightGBM loses**, as on the Assam mandi data. M5's win came from tens of thousands of long daily series;
  we have ~300 short monthly ones.
- Per crop the winner varies (naive for some pulses, LightGBM for mango/orange), but picking per crop on the same
  backtest would overfit; one method for all is the honest choice.
- **Recommendation: switch to the median combination.**

## 4. Ranking tests (`notebooks/07_ranking_tests.ipynb`)

**CACP cost shares** (cost ÷ gross value, median 2017-18 to 2021-22): A2+FL is 50% (lentil) to 76% (mungbean,
blackgram) of gross value; C2 is 82–110%. Costs are large and differ by crop.

**Revealed preference** (625 DES districts; does the score's ranking match the crops' area ranking?)
Table: `research/results/2026-11-03_ranking_revealed_preference.csv`.

| Score | Mean Spearman ρ with area | Top-1 match |
| --- | --- | --- |
| Gross revenue, all crops | 0.06 | 13.7% |
| Gross revenue, field crops | 0.14 | 17.3% |
| Net over A2+FL, field crops | 0.04 | 14.0% |
| Net over C2, field crops | 0.08 | 18.7% |
| Random score | −0.02 | 15.1% |

- **Gross revenue is no better than random at predicting what districts grow most.** Banana is #1 by gross revenue in
  41% of districts but #1 by area in 0.3%. Rice is #1 by area in 66% but #1 by revenue in 7.5%.
- Net return doesn't fix it. Real choices depend on irrigation, MSP procurement, food needs, market access and risk,
  none of which revenue captures. (Yield alone scores ρ 0.37, but that's partly reverse causation: districts that grow
  a crop a lot get good at it.)

**Ranking rules on Kaggle out-of-fold predictions** (true suitable crop known). Table: `research/results/2026-11-03_ranking_rules.csv`.

| Rule | #1 is the right crop | Mean net of #1 |
| --- | --- | --- |
| Suitability order | 98.4% | Rs 1.305 lakh/ha |
| p × gross revenue (notebook 04) | **94.5%** | Rs 1.303 lakh |
| p × net return | 94.2% | Rs 1.304 lakh |
| Net return among near-ties (τ = 0.5) | 98.2% | Rs 1.305 lakh |
| **Net return among near-ties (τ = 0.8)** | **98.5%** | **Rs 1.306 lakh** |

- Multiplying by revenue costs 4 points of agronomic correctness and gains nothing. On real farms the model is less
  sure (flatter probabilities, e.g. Raipur, Vidisha), so revenue overrides it far more often than in this test.
- Using money only to order crops the model rates about equally (suitability ≥ 80% of the top crop's) keeps the
  agronomy and still prefers the more profitable crop when it's a genuine toss-up.

**Recommendation:** order by suitability; re-order by net return only among near-ties (τ = 0.8). Show net return for
field crops (CACP cost share) and gross revenue for fruit, flagged "cost not known, orchards take years to bear".

**Re-run Nov 4 after the rice unit fix** (DES rice is milled rice; now converted to paddy, ×1/0.67, to match paddy
prices; see `2026-11-04_district_model.md`). Tables: `2026-11-04_ranking_revealed_preference.csv`,
`2026-11-04_ranking_rules.csv` (the Nov 3 files above are the buggy run, kept as they were).

| Score | Mean Spearman ρ with area | Top-1 match |
| --- | --- | --- |
| Gross revenue, all crops | 0.17 | 20.6% |
| Gross revenue, field crops | 0.28 | 32.0% |
| Net over A2+FL, field crops | 0.10 | 20.8% |
| Net over C2, field crops | 0.08 | 21.7% |
| Yield only, field crops | 0.40 | 53.4% |
| Random score | −0.02 | 15.1% |

Rice is now #1 by gross revenue in 16.8% of districts (was 7.5%; #1 by area in 66%). Revenue now beats random, but
still matches far less often than yield alone, and net return is still worse than gross. Ranking rules: suitability
98.4%, p × gross 93.1%, p × net 92.7%, near-ties τ = 0.5 98.2%, **τ = 0.8 98.5%** (mean net of #1 Rs 1.51 lakh/ha).
Same conclusion: keep τ = 0.8.

## 5. Applied to the app (Nov 3)

**Crop model** (`notebooks/05_crop_model_tests.ipynb`, section 5; table `research/results/2026-11-03_crop_app_model.csv`).
Augmentation and calibration had only been tested apart, so the combination was tested on the same 10 folds before saving.
Calibration folds keep each row with its 5 noisy copies (`StratifiedGroupKFold`), so the calibrator never sees a copy of a
training row. `CalibratedClassifierCV(ensemble=False)`: one forest on all rows, which SHAP explains.

| Model | Accuracy clean | Accuracy noise ×1.0 | Top-3 noise ×1.0 | ECE noise ×1.0 | Brier noise ×1.0 |
| --- | --- | --- | --- | --- | --- |
| Random Forest (old app model) | 98.4% | 74.2% | 94.8% | 0.078 | 0.388 |
| RF + noise augmentation | 93.6% | 88.9% | 99.7% | 0.063 | 0.169 |
| **RF + noise augmentation + isotonic (new app model)** | 93.1% | 88.3% | 99.6% | **0.038** | 0.164 |

Calibrated minus uncalibrated at noise ×1.0 (corrected t-test): accuracy −0.6 points (p = 0.19), Brier −0.006
(p = 0.07), ECE −0.026 (p = 0.04). So calibration makes the probabilities more honest at no clear cost in accuracy.

**Price forecast** (`notebooks/06_price_model_tests.ipynb`, section 4). Median of AutoETS, AutoARIMA, AutoTheta and
seasonal-naive, June 2026 – May 2027, written to `data/processed/price_forecast.csv` (method `combo_median_snaive`),
with each series' backtest MAPE at 4–12 months. Same 309 series as before; the median price moved 8.2% from the
seasonal-naive file. Series need a price in the last 12 months.

**Ranking** (`project/recommend.py`). Top 3 with suitability ≥ 5% in suitability order; crops ≥ 0.8 × the top crop's
suitability are ordered by net return = yield × 10 × price × (1 − CACP A2+FL share). Shares come from `data.cost_shares()`
(state, else All India); fruit and melons get the median field-crop share (0.70), flagged "assumed" in `cost_source`.

**Example farms** (`notebooks/04_ranking.ipynb`, re-run): known crop in the top 3 for 5 of 5 farms (was 4), ranked first
for 4 of 5 (was 3). Raipur still picks jute (0.92) over rice (0.08).

Note: notebook 07's tables were made with the seasonal-naive forecast and the uncalibrated forest; they were not re-run.
