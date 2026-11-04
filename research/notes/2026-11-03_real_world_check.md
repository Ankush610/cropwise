# Real-world check · Nov 3, 2026

Question: given a district's real soil and weather, does the system recommend the crops that district actually grows?
Notebook: `notebooks/08_real_world_check.ipynb`. Seed 42. Model: the app model of Nov 3 (`models/crop_model.joblib`,
RF without humidity, weather-noise augmented, isotonic-calibrated), called through `recommend.recommend()`, sown Nov 3.

## Data and settings

| Piece | Source | Settings |
| --- | --- | --- |
| Soil | Soil Health Card, "Soil Nutrient Analysis" (India Data Portal, updated Feb 24 2026), 2023-24 + 2024-25 | File gives sample counts per class only. District value = count-weighted mean of class values: N Low/Med/High 210/420/700, P 5/17.5/32.5, K 90/200/360 kg/ha, pH Acidic/Neutral/Alkaline 5.75/7.0/8.25 (ICAR Harit Dhara limits N 280/560, P 10/25, K 120/280; midpoints, open classes as wide as the middle one). Districts with ≥ 100 tests. `data.district_soil()` |
| Weather | NASA POWER 2015-2024 at the district's market coordinates | Annual mean temperature, mean monthly rainfall (as in the app) |
| What districts grow | DES district APY | Kaggle crops reported 2018-19 or later, mean area of last 5 years. Main crop = most area |
| Districts | Soil + coordinates + DES area | 539 |

Three soil inputs: **SHC raw** (kg/ha as on the card), **SHC mapped** (district's percentile among districts → same
percentile of Kaggle's values; pH raw), **Kaggle mean soil** (same soil everywhere, only weather differs).

## Results (`research/results/2026-11-03_real_world_check.csv`)

| Method | Main crop 1st | Main crop in list | Picks the district grows | List length |
| --- | --- | --- | --- | --- |
| SHC raw | 6.3% | 7.8% | 29.7% | 3.0 |
| SHC mapped | 3.5% | 13.2% | 37.4% | 2.0 |
| Kaggle mean soil | 0.0% | 1.7% | 1.6% | 1.0 |
| Random 3 crops | 5.0% | 16.0% | 35.1% | 3.0 |
| Always rice, cotton, maize | 69.6% | 87.6% | 83.9% | 3.0 |

Main crop by area: rice 70% of districts, cotton 9%, maize 9%, chickpea 6%. SHC raw picks chickpea first in 89% of
districts; Kaggle mean soil picks papaya in 100%.

## Diagnostics (`research/results/2026-11-03_real_world_diagnostics.csv`)

Crop model alone, top 3 by suitability.

| Setting | Main crop 1st | Main crop in top 3 | Rice 1st in rice districts | Median rainfall (mm/month) |
| --- | --- | --- | --- | --- |
| SHC mapped, annual weather | 3.5% | 15.0% | 1.1% | 96 |
| SHC mapped, kharif Jun–Sep | 4.5% | 16.5% | 2.9% | 225 |
| SHC mapped, rabi Nov–Feb | 4.8% | 14.3% | 2.7% | 11 |
| Oracle soil (Kaggle mean soil of the district's own main crop), annual | 30.4% | 99.6% | 2.4% | 96 |
| Oracle soil, kharif | 33.0% | 100.0% | 5.9% | 225 |

With oracle soil, rice districts get jute first and rice second: in Kaggle the two share soil and weather.

## Conclusions

1. **The Kaggle-trained model does not transfer to real districts.** With real soil it does no better than random
   crops, and far worse than a "most common crops" rule.
2. **Kaggle N, P, K are on a different scale from soil tests.** Every district's SHC N (210–650 kg/ha) is above
   Kaggle's maximum (140); median SHC K (234) is above Kaggle's maximum (205); SHC P (5–33) is below Kaggle's median (51).
   Kaggle's per-crop means look like fertiliser doses (rice 80:48:40). A farmer typing their card into the app gets
   chickpea almost everywhere.
3. **Weather is not the cause; soil is.** Season-matched rainfall changes nothing. Oracle soil puts the main crop in
   the top 3 almost always. The model identifies the crop from Kaggle's tight per-crop N-P-K clusters, which real soil
   never falls into. Strong evidence that the Kaggle data is synthetic.
4. For the paper: this belongs in Results, not only Limitations. Most published Kaggle-based recommenders report 97–99%
   accuracy with no real-world test (see `2026-11-03_model_research.md`, section 1).

## Caveats

- District means hide farm-to-farm variation; a farm's own card could look different.
- SHC publishes class counts, not values, so district values are class-midpoint estimates (pH spread is squashed:
  district pH is 5.8–8.1, mostly 6.8–7.0).
- Main crop is limited to the 22 Kaggle crops: wheat, sugarcane, soybean, groundnut, mustard and bajra are not in it.
- Popularity baseline sees the answers (it is built from the same districts).
