# Price forecast refresh · Nov 6, 2026

**Why:** the app's forecast covered Jun 2026 – May 2027 (data ended May 2026), so harvests before November got prices
for months already past, and Maharashtra onion was forecast at ₹888–1,369/q while mandis traded at ₹2,700–4,750 (Nov 6).

## Data

- APMC zips (India Data Portal mirror of Agmarknet), Jan 2021 – May 2026, as before.
- **New:** data.gov.in "Variety-wise daily market prices" (resource `35985678-0d79-46b4-9ed6-6f13308a1d24`), every day
  May 1 – Nov 5, 2026: 189 daily files, ~22k rows a day (`data.daily_prices`, cached monthly in
  `data/processed/prices_monthly_live.csv`). Used for months after May 2026; Nov 2026 holds 5 days.
- **Overlap check (May 2026, both sources):** 387 crop × state series; API/zip price ratio median 1.000, 97.9% within
  ±10%, 99.2% within ±25%; series with ≥ 100 market-days: median difference 0. Same underlying Agmarknet feed.
- **Unit-slip filter (new in `data.mandi_prices`):** monthly values more than 5× above or below their series median are
  dropped: 54 of 26,003 zip rows (coconut Goa at ₹14 = one nut, Rajasthan, Andaman; a few small-market fruit months).

## Settings

`notebooks/06_price_model_tests.ipynb`, re-run in full Nov 6. Unchanged: backtest cutoffs May 2024, Nov 2024, May 2025;
12 months ahead, scored at 4–12; ≥ 24 observed months; seed 42. App forecast = median of AutoETS, AutoARIMA,
AutoTheta and seasonal-naive from the last month of data.

## Results

- **Backtest** (`results/2026-11-06_price_model_tests.csv`; Nov 4 file kept): median MAPE combo_median_snaive 16.40%
  (Nov 4: 16.40%), combo_mean 16.66, ets 17.46, arima 17.62, seasonal-naive 17.87, naive 18.11, theta 18.51,
  LightGBM 19.02. Winner unchanged; the backtest windows end before the new months, so only the filter moved scores.
- **App forecast:** Dec 2026 – Nov 2027, 467 series (469 before). Median change vs the old file 11.8% of price.
  97 series have backtest MAPE > 30%, 31 have no backtest.
- **High-error crops:** onion (All India 57.8%, 25 state series > 30%) and potato (40.5%, 23 states) dominate, then
  mango, watermelon, orange, coconut, pigeonpeas. Cause is volatility, not data: Maharashtra onion went ₹4,100 (Nov 2024)
  → ₹900 (Mar–May 2026) → ₹3,775 (Nov 2026).
- **Series choice (new in `recommend._series`):** each crop uses the state or All-India forecast, whichever has the lower
  backtest MAPE. Maharashtra onion → All India (57.8% vs 98.6%): ₹4,325 for Dec 2026.
- Examples (sown Nov 6): Vidisha wheat ₹2,860 (All India, 8.3%), chickpea ₹6,844, mustard ₹8,033; Nashik chickpea
  ₹6,850 (Maharashtra, 9.5%).
