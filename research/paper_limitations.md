# Limitations for the paper

Running list for the paper's limitations section. Each item says what goes wrong, the evidence and where it is
recorded. Started Nov 4, 2026.

## Coverage gaps found in the web check (Nov 4)

Source: `notes/2026-11-04_season_model.md`, "Web check by season" and "Fixes after the web check".

1. **Arid western Rajasthan.** Bikaner grows guar (~885k ha), moth bean (~275k), bajra (~257k) in kharif and gram
   (~315k) in rabi. The app offers rice, bajra, cotton and wheat, mustard, potato: main crop missed in both seasons.
   Why: no district with Soil Health Card data (≥ 100 tests) has this cropping system, so neither the crop model nor
   the nearest-district soil fill (Sirsa, Mahendragarh, Bathinda) has seen it. Guar is not one of the 27 crops. In
   the 84 filled districts, Rajasthan's main crop is in the list for 61% of districts against 92–100% in Punjab,
   Haryana and Kerala (`notes/2026-11-04_soil_fill_check.md`, section 3). Rajasthan has 28 districts without SHC data.
2. **District boundary changes (Guntur).** Andhra Pradesh split Guntur in 2022 (Bapatla, Palnadu). DES yields and
   areas are 5-year means that mix the old, paddy-heavy district with the new one (2021-22: kharif cotton 48%, paddy
   18%, chilli 18%; rabi paddy 40%, pulses 33%). The app puts rice first in kharif and maize first in rabi. Chilli is
   not one of the 27 crops. Any state that re-drew districts after ~2018 has the same problem (Telangana 2016,
   Andhra Pradesh 2022 and others).
3. **Neighbours from another cropping system (Karnal).** Karnal has no SHC average; its nearest SHC districts include
   western Uttar Pradesh's cane belt (Shamli, Saharanpur), and its weather is similar. The app ranks sugarcane first
   in kharif (0.45 vs rice 0.36) where rice covers ~20× more land. Ludhiana gets sugarcane second for the same reason.

Web check score after the fixes: main crop first 16 of 21 district-seasons, in the list 21 of 23 (9 of 12 districts
were in training, so optimistic).

## Data

- Kaggle Crop Recommendation is likely synthetic and has no location; its N, P, K are not on the Soil Health Card
  scale, so the Kaggle model put the main crop in its list for 8% of real districts (`notes/2026-11-03_real_world_check.md`).
- No dataset links soil, crop and price for the same farm. The model learns district averages: SHC soil, NASA POWER
  weather, DES area, mandi prices, CACP costs.
- SHC gives only class counts. District values are class midpoints; the card's "Normal" pH class spans 6.5–8.2 and
  holds 86% of samples, so district pH barely varies and the model has a step at 7.35
  (`notes/2026-11-04_district_model.md`, "Soil class fix").
- The nearest-district soil fill gets N in the right class in 4 of 4 published checks, K 3 of 5, pH 3 of 6, P 1 of 5
  (`notes/2026-11-04_soil_fill_check.md`).
- DES season labels differ by state (UP files sugarcane as Kharif; West Bengal's Winter/Summer rice). Our mapping is
  in `data.SEASON_OF`, `data.RICE_SEASON`; year-round crops are split equally across seasons.
- CACP cost exceeds the crop's value for some state-crop pairs (ragi, Maharashtra paddy), so net return is negative.

## Method

- Suitability is revealed preference: the share of a season's farmland that similar districts put under the crop.
  It includes irrigation, markets and habit, not agronomic fit.
- Yields and prices are year-round: rabi rice gets the district's annual rice yield.
- Summer is weak (main crop in list 67% vs kharif 84%) and many districts sow little then; the app warns below 10%.
- Validation is leave-one-state-out on district averages; a farm's own card can fall outside the district range.
