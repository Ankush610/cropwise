# Soil fill for farmers without a card · Nov 4, 2026

Question: how good is `recommend.area_soil` (the district's Soil Health Card average if ≥ 100 tests, else the mean of
the 3 nearest such districts)? Notebook: `notebooks/10_soil_fill_check.ipynb`. Table:
`research/results/2026-11-04_soil_fill_check.csv`.

**Update (same day):** the first run found SHC labels 86% of pH samples "Neutral", which the assumed 6.5–7.5 class could not explain. The card template in the SHC Operational
Guidelines (2015) and District Manual (2017) rates pH Acidic < 6.5, Normal 6.5–8.2, Alkaline > 8.2, and prints P with
limits 28/56 and K 140/280 kg/ha. `data.SHC_LEVELS` now uses these (see `2026-11-04_district_model.md`, "Soil class
fix"), and the tables below are re-run on that scale. The first run used pH 6.5/7.5, P 10/25, K 120/280.

## 1. Leave one district out (539 districts with an SHC average)

Each district's N, P, K, pH predicted from its nearest *other* districts (great-circle distance between market-centroid
coordinates), compared with its own SHC average. Skill = 1 − MAE / MAE of the India mean. Class = card class
(N 280/560, P 28/56, K 140/280 kg/ha; pH 6.5/8.2).

| Method | MAE N | MAE P | MAE K | MAE pH | Skill N / P / K / pH | Class match N / P / K / pH |
| --- | --- | --- | --- | --- | --- | --- |
| **3 nearest (app)** | 40.8 | 7.9 | 28.6 | 0.12 | 0.41 / 0.25 / 0.32 / 0.56 | 74 / 76 / 79 / 96% |
| 1 nearest | 45.4 | 9.1 | 33.5 | 0.14 | 0.35 / 0.14 / 0.20 / 0.49 | 73 / 70 / 76 / 94% |
| 5 nearest | 41.7 | 8.1 | 27.9 | 0.12 | 0.40 / 0.23 / 0.33 / 0.55 | 75 / 76 / 80 / 96% |
| 3 nearest, same state | 39.2 | 7.6 | 29.0 | 0.12 | 0.44 / 0.28 / 0.31 / 0.55 | 75 / 77 / 80 / 95% |
| State mean | 41.1 | 7.0 | 31.0 | 0.12 | 0.41 / 0.34 / 0.26 / 0.53 | 76 / 79 / 78 / 94% |
| India mean | 69.5 | 10.6 | 41.9 | 0.27 | 0 | 36 / 62 / 72 / 92% |

Scale: real district values have sd N 89, P 12.6, K 50, pH 0.4. Most districts sit in one class (N low 63%, P medium
62%, K medium 72%, pH normal 92%), so class match is easy for P, K and pH.

The 84 districts the app fills are farther from districts with data (median 87 km to the 3 nearest vs 56 km in the
test) and concentrated in Rajasthan (28), Punjab (19), Haryana (18) and Kerala (12), so expect larger errors there.

## 2. Filled districts vs published soil studies (web, Nov 4)

Studies use different years, sites and sometimes units (P as P or P2O5); this is a class-level spot check only.
App values are on the card scale after the fix.

| District | App fill | Published | Verdict |
| --- | --- | --- | --- |
| Ludhiana (PB) | pH 7.4 (N 276, P 35, K 133) | Rice fields, 40 samples, kharif 2020: mean pH 7.04 and 7.11 (Kanojia & Sreekesh 2022; NPK reported in ppm, not comparable) | pH same class (normal), 0.3 high |
| Karnal (HR) | N 223, P 48, K 212, pH 7.4 | 230 samples, all blocks: every sample low in N, block means 147–169 kg/ha; P block means 21–33 kg/ha, mostly rated high; K block means 208–338 (Karnal block 262). CSSRI long-term plots: pH 8.1–8.4 | N ✓ (low), K ✓ (medium), P borderline (medium vs mostly high), pH too low (normal vs normal/alkaline border) |
| Jaipur (RJ) | N 228, P 58, K 242, pH 7.4 | Jhotwara block: N low, P low–medium, K medium–high (150–350 kg/ha), pH 7.2–8.5 | N ✓, K ✓, pH ✓ (mostly normal), P ✗ (high vs low–medium) |
| Thiruvananthapuram (KL) | pH 7.2 | district mean pH 5.48 | ✗: neighbours are across the Western Ghats in Tamil Nadu |
| Palakkad (KL) | pH 7.0 | district mean pH 6.99 | ✓ |

## Conclusions

1. Nearest districts are a fair "typical for your area" guess for N and K (right class in most checks), weaker for P.
2. pH: the fill misses acidic south Kerala (neighbours across the Ghats) and still reads low for alkaline Haryana.
3. **Source limit:** the card's "Normal" pH class spans 6.5–8.2 and holds 86% of India's samples (Sirsa 91%), so
   district pH from class counts stays compressed (district sd 0.4) even with the right limits.
4. For the paper: the fill is an area estimate; farmers should use their card.

Sources: Kanojia & Sreekesh 2022, Int. J. Health Sciences (sciencescholar.us/journal/index.php/ijhs/article/download/7284/3625);
Karnal district fertility assessment (krishikosh.egranth.ac.in/handle/1/5810197643, core.ac.uk/download/158353053.pdf);
Jaipur Jhotwara fertility study (core.ac.uk/works/129645716); Kerala nine-district pH study (arccjournals.com/journal/agricultural-science-digest/D-5509);
SHC card template: Operational Guidelines for implementation of the Soil Health Card scheme (2015,
sameti.org/Guidelines/CS%20on%20Soil%20Health%20Card.pdf) and District Manual – Soil Health Card (2017,
nitiforstates.gov.in/public-assets/Policy/policy-repo/agriculture-and-allied-services/SNC511A000049.pdf).

## 3. Re-check after the class fix (Nov 4): crops and more soil studies

**Crops in the filled districts** (`notebooks/10_soil_fill_check.ipynb`, section 2;
`research/results/2026-11-04_soil_fill_crop_picks.csv`). The 84 filled districts have no SHC average, so none was in
the crop model's training. App top 3 (sown Nov 4) vs the district's main crop by DES area among the 27 model crops:

| Soil used | Main crop 1st | Main crop in list | Picks grown |
| --- | --- | --- | --- |
| **Fill (3 nearest districts)** | **48.8%** | 84.5% | 99.6% |
| One fixed soil (250 / 40 / 210 / 7.35) | 39.3% | 85.7% | 99.2% |
| Popularity (rice, wheat, maize) | 19.0% | 60.7% | 89.7% |

By state (fill, in list): Punjab 19 districts 100%, Haryana 18 94%, Kerala 12 92%, Rajasthan 28 61%. The 13 misses are
11 Rajasthan districts whose main crop is moth bean, mung bean, jowar, maize, soybean or mustard (the app offers wheat,
bajra, mustard), Charkhi Dadri (mustard) and Wayanad (banana). Not comparable with notebook 09's 80.5% (different
districts; here the neighbours were in training).

**More soil studies** (filled districts; class on the card scale; published P is sometimes P and sometimes P2O5, a
factor of 2.3, so P checks are the least reliable):

| District | App fill | Published | Verdict |
| --- | --- | --- | --- |
| Bikaner (RJ) | N 229, P 39, K 177, pH 7.51 | Groundnut tracts 2015-16: alkaline, N low, P2O5 and K2O medium | N ✓, P ✓, K ✓; pH reported alkaline, fill is mid "Normal" |
| Jaisalmer (RJ) | N 213, P 65, K 291 | N 132, P2O5 26, K2O 258 kg/ha (N low, P and K medium) | N ✓, P ✗ (high vs low), K borderline ✗ (just above 280) |
| Ernakulam (KL) | N 211, P 48, K 300, pH 6.96 | 583 samples, 17 vegetable panchayats: pH 4.2–5.8; Kerala cassava soils: P high to very high, K low to medium | pH ✗, P ✗, K ✗ |
| Sirsa (HR, *has* SHC data: checks the source, not the fill) | N 230, P 38, K 254, pH 7.48 | 2022 survey: N 119–150 (low), P 22.6–33.4 kg/ha (high), K medium 58% / high 33% | N ✓, K ✓, P lower class than the study |

**Tally over all published checks of filled districts** (sections 2 and 3, class level): N 4 of 4, K 3 of 5,
pH 3 of 6, P 1 of 5 (Karnal counted as a miss). Hits are in Punjab, Haryana and east Rajasthan; misses are acidic
Kerala and the arid west.

**Verdict:** the fill is good enough to pick crops (84.5% in list, better first pick than a fixed soil), and its N and
K are usually in the right class. Its P and pH should not be shown to a farmer as "your soil": they are only right where
the neighbours share terrain. The app already says so; the paper should report the tally.

Sources (section 3): Bikaner groundnut-area soils (i-scholar.in/index.php/Ajss/article/view/152704); Jaisalmer nutrient
index study (epubs.icar.org.in/index.php/AAZ/article/view/103051/40369); Ernakulam vegetable panchayats
(jtropag.kau.in/index.php/ojs2/article/download/1129/628/5253); Kerala cassava soils
(krishi.icar.gov.in/ohs-2.3.1/index.php/record/view/760031); Sirsa 2022 survey (krishikosh.egranth.ac.in/handle/1/5810197567).
