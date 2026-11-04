# Season model · Nov 4, 2026

Question: the year-round district model (notebook 09) ignored the sowing date. User test: Jangoan (Telangana) got
rice 0.585 and cotton 0.327 for a Jan, Mar, Jun, Aug or Oct sowing alike; cotton is a June crop there. Does a model
trained on DES area by season do better? Notebook: `notebooks/11_season_model.ipynb`. Seed 42.

## Data and settings

| Piece | Source | Settings |
| --- | --- | --- |
| Target | DES area by season, `data.district_season_area()` | Kharif, Autumn, aman rice ("Winter") → kharif; Rabi, other Winter crops, boro rice ("Summer") → rabi; other Summer crops → summer; "Whole Year" area in every season for crops reported mostly that way (sugarcane, coconut, fruit), else the crop's main season. Last 5 reported years per series; series ending before 2010-11 dropped. District-seasons < 1,000 ha left out |
| Inputs | as notebook 09 + season | card N, P, K, pH; year, kharif and rabi weather (NASA POWER 2015-2024); season 0/1/2 |
| Units | 539 districts (SHC ≥ 100 tests) | 1,426 district-seasons: kharif 538, rabi 523, summer 365; 27 crops |
| Model | Random Forest, 500 trees, min_samples_leaf 3 | one row per district-season × crop, weighted by the crop's share of that season's area |
| Season filter | training data | crop offered in a season only if ≥ 5% of that season's training district-seasons grow it |
| App | `recommend.SEASON_MONTHS` | sowing Jun–Sep kharif, Oct–Jan rabi, Feb–May summer |

Validation: leave one state out (28 folds); filter refit per fold. Scored per district-season against the main crop of
that season. Paired bootstrap resampling districts (seasons of a district stay together), 2,000 draws.

## Results (`research/results/2026-11-04_season_model_cv.csv`, `_by_season.csv`)

| Method | Main crop 1st | Main crop in list | Picks grown that season | Area covered |
| --- | --- | --- | --- | --- |
| **Season model + filter (app)** | **46.8%** | **72.4%** | **83.5%** | **64.8%** |
| Season model, no filter | 46.8% | 72.4% | 83.2% | 64.6% |
| Year-round model (notebook 09, refit per fold) | 33.2% | 55.5% | 57.9% | 47.0% |
| Popularity per season | 44.0% | 60.1% | 75.6% | 53.5% |

| Main crop in list | Kharif | Rabi | Summer |
| --- | --- | --- | --- |
| Season model + filter | 82.7% | 72.8% | 56.7% |
| Year-round model | 75.8% | 63.1% | 14.8% |
| Popularity per season | 71.6% | 65.0% | 36.2% |

Bootstrap (app model minus comparison): vs year-round, in list +16.9 pts (CI 14.5–19.4), first +13.6 (11.7–15.6);
vs per-season popularity, in list +12.3 (9.7–15.1), first +2.8 (0.4–5.0); filter vs no filter +0.1 in list.

Feature importance: season 0.32, rabi temperature 0.10, humidity 0.10, rabi rain 0.08; soil 0.04–0.05 each.

## Examples through the app (`2026-11-04_season_model_examples.csv`)

| District | Kharif (1 Jul) | Rabi (1 Nov) | Summer (1 Mar) | DES top crops by season |
| --- | --- | --- | --- | --- |
| Jangoan | rice 0.47, cotton 0.45 | rice 0.87, maize 0.07 | sugarcane, groundnut (0% sown: warning) | kharif cotton, rice, pigeon pea; rabi rice, maize, groundnut; summer none |
| Vidisha | soybean, blackgram, rice | wheat, chickpea, lentil | mungbean, potato, maize | identical in all three seasons |
| Ludhiana (not in training) | rice, sugarcane | wheat | sugarcane, wheat, maize (1% sown: warning) | kharif rice, sugarcane, maize; rabi wheat, mungbean, sugarcane |
| Thanjavur | rice, coconut | coconut, blackgram, rice | coconut, sugarcane, banana | identical in all three seasons |

The examples' districts (except Ludhiana) were in training, so their match is no evidence on its own.

## Conclusions

1. The season input fixes the user's bug and is the biggest single gain so far: +17 pts "in list" over the year-round
   model on the same districts.
2. Kharif is easy (82.7%), rabi harder, summer weak (56.7%) and often nearly empty; the app warns when a district sows
   less than 10% of its main-season area in the chosen season.
3. Notebook 09's numbers are scored on year-round main crops and are not comparable with these.

## Limits (for the paper)

- Season assignment depends on how states report to DES (e.g. West Bengal's Winter/Summer rice); the mapping is
  ours (`data.SEASON_OF`, `data.RICE_SEASON`).
- "Whole Year" sugarcane and coconut counted in every season, so they dominated summer picks (fixed the same day:
  year-round crops are now split across seasons, see "Fixes after the web check").
- Yields and prices are not seasonal: rabi rice gets the district's annual rice yield.
- Still revealed preference: what similar districts sow that season, not agronomic fit.

## Web check by season (Nov 4)

App picks (district SHC soil, or the nearest-district fill where marked; sown 1 Jul = kharif, 1 Nov = rabi) vs what
web sources report for the same district and season. Sources differ in year (2008 profiles to 2026 news); a crop
counts as "main" when the source shows it with the largest area. Case study, not a paper result on its own: 9 of the 12
districts were in training.

| District | Season | App top 3 | Reported | Main 1st | Main in list |
| --- | --- | --- | --- | --- | --- |
| Jangoan (TG) | kharif | rice 0.47, cotton 0.45 | 2026 vanakalam: paddy 1.54 lakh ac, cotton 1.38, red gram 0.20 | ✓ | ✓ |
| Jangoan | rabi | rice 0.87, maize 0.07 | no web figures found (DES: rice, maize, groundnut) | – | – |
| Ludhiana (PB, fill) | kharif | rice 0.61, sugarcane 0.21 | paddy 2.57 lakh ha (2024-25), kharif maize ~320 ha, sugarcane ~2,500 ha | ✓ | ✓ (sugarcane too high) |
| Ludhiana | rabi | wheat 0.84 | wheat 2.43 lakh ha | ✓ | ✓ |
| Karnal (HR, fill) | kharif | sugarcane 0.53, rice 0.30, bajra 0.06 | rice ~168k ha (2011 profile), sugarcane 8,570 ha (2024-25) | ✗ | ✓ |
| Karnal | rabi | wheat 0.82, mustard 0.05 | wheat ~169k ha; crop-cutting for wheat and mustard | ✓ | ✓ |
| Vidisha (MP) | kharif | soybean 0.66, blackgram 0.19, rice 0.08 | soybean 163k, black gram 32k (2013 profile) | ✓ | ✓ |
| Vidisha | rabi | wheat 0.63, chickpea 0.23, lentil 0.08 | wheat ~3.5 lakh ha (2024-25); 2013: chickpea 214k, wheat 186k, lentil 76k | ✓ | ✓ |
| Nashik (MH) | kharif | maize 0.31, bajra 0.15, soybean 0.15 | soybean, maize, bajra, tur, moong, urad; cotton and onion also hit by 2025 rain | ? | ✓ |
| Nashik | rabi | wheat 0.44, chickpea 0.33, sugarcane 0.15 | wheat 75.8k, onion 65.8k (both seasons), chickpea 43.2k (2008-09) | ✓ | ✓ (onion missed) |
| Thanjavur (TN) | kharif | rice 0.76, coconut 0.14 | kuruvai and samba paddy | ✓ | ✓ |
| Thanjavur | rabi | coconut 0.37, blackgram 0.20, rice 0.18 | thaladi paddy (samba + thaladi 1.31 lakh ha), then rice-fallow black gram | ✗ | ✓ |
| Belagavi (KA) | kharif | sugarcane 0.33, maize 0.20, soybean 0.14 | sugarcane 3 lakh ha (2025-26), maize 1.3 lakh, soybean 1.0 lakh, green gram 50k | ✓ | ✓ |
| Belagavi | rabi | sugarcane 0.41, jowar 0.21, chickpea 0.18 | rabi maize 35k (old); rabi jowar and gram common, no split found | ? | ✓ |
| Bikaner (RJ, fill) | kharif | bajra 0.29, rice 0.28, cotton 0.18 | guar 885k (not a model crop), moth bean 275k, bajra 257k, groundnut 63k | ✗ | ✗ |
| Bikaner | rabi | wheat 0.47, mustard 0.26, potato 0.10 | gram 315k, wheat 59k, mustard 42k | ✗ | ✗ |
| Guntur (AP) | kharif | rice 0.53, cotton 0.33 | 2021-22: cotton 48%, paddy 18%, chillies 18% (not a model crop) | ✗ | ✓ |
| Guntur | rabi | maize 0.23, jowar 0.17, rice 0.16 | 2021-22: paddy 40%, pulses 33%, maize 11% | ✗ | ✓ |
| Muzaffarpur (BR) | kharif | rice 0.84, maize 0.10 | rice 119k, maize 13k | ✓ | ✓ |
| Muzaffarpur | rabi | wheat 0.71, maize 0.11 | wheat 96k, maize 15k | ✓ | ✓ |
| Purba Bardhaman (WB) | kharif | rice 0.93 | aman rice 422k ha | ✓ | ✓ |
| Purba Bardhaman | rabi | rice 0.56, potato 0.24, mustard 0.11 | boro rice 216k, mustard 46k, potato 46k | ✓ | ✓ |
| Yavatmal (MH) | kharif | cotton 0.50, soybean 0.28, pigeonpeas 0.14 | cotton, soybean, tur (9.05 lakh ha kharif) | ✓ | ✓ |
| Yavatmal | rabi | chickpea 0.61, wheat 0.25 | gram and wheat after soybean (87k ha rabi) | ✓ | ✓ |

**Score** (where the source names a main crop): main crop first 15 of 21, main crop in list 21 of 23. Kharif 8 of 11
first and 11 of 12 in list; rabi 7 of 10 and 10 of 11.

**Why the misses happen**
1. Year-round crops counted in every season: sugarcane first in Karnal kharif, coconut first in Thanjavur rabi,
   sugarcane second in Ludhiana kharif. `district_season_area()` puts the full "Whole Year" area in each season.
2. Arid Rajasthan: no district with SHC data grows guar, moth bean and gram like Bikaner, so the fill's neighbours
   (Sirsa, Bathinda) give canal-irrigated crops (rice, cotton, wheat). Guar is not one of the 27 crops.
3. Guntur was split in 2022 (Bapatla and Palnadu); DES's 5-year mean mixes the old, paddy-heavy district with the new
   cotton and chilli one. Chilli is not a model crop.

Possible fix for 1: split "Whole Year" area across the three seasons (one third each) instead of counting it in full.

Sources: Telangana Today (Jangaon, Oct 2026); Agri Times / Tribune (Ludhiana paddy 2025, 2024-25); ICAR-CRIDA district
profiles (Karnal, Vidisha, Nashik, Belagavi, Bikaner, Muzaffarpur, Guntur); Dataful (Karnal sugarcane 2024-25); Free
Press Journal (Nashik kharif 2025); The News Minute / Lokmat Times (Thanjavur samba, thaladi); CropGPT and Deccan
Herald (Belagavi 2025-26); CGWB NAQUIM report (Guntur 2021-22); purbabardhaman.nic.in; KVK Yavatmal.

## Fixes after the web check (Nov 4)

Year-round crops were counted in full in every season ("Whole Year" area) and Uttar Pradesh files its sugarcane (49%
of India's) as Kharif, so sugarcane and coconut topped seasons they barely fill. Now `data.YEAR_ROUND` (sugarcane,
coconut, banana, papaya, mango, orange, grapes, coffee, pomegranate) is split equally across the three seasons
whatever the DES season. Notebook 11 re-run (same settings; 1,399 district-seasons; the target changed with the fix, so
the tables above are the first run):

| Method | Main crop 1st | Main crop in list | Picks grown that season | Area covered |
| --- | --- | --- | --- | --- |
| **Season model + filter (app)** | **52.1%** | **76.5%** | **87.7%** | **68.4%** |
| Year-round model (notebook 09) | 35.0% | 58.0% | 59.1% | 49.5% |
| Popularity per season | 47.4% | 67.1% | 79.2% | 59.3% |

In list by season: kharif 83.8%, rabi 75.1%, summer 67.1% (was 82.7 / 72.8 / 56.7). Bootstrap: vs year-round +18.5 pts
in list (CI 16.2–20.8), +17.2 first (15.0–19.4); vs popularity +9.4 in list (7.0–11.7), +4.7 first (2.3–7.0).

Web-check districts again (sown 1 Jul / 1 Nov):
- Thanjavur rabi: rice 0.25, blackgram 0.28, coconut 0.20 (rice first by net return among near-ties): ✓, was coconut first.
- Belagavi kharif: maize 0.27, soybean 0.17, sugarcane 0.14 (kharif-sown maize 1.3 lakh ha vs a third of 3 lakh ha cane): ✓.
- Karnal kharif: sugarcane 0.45, rice 0.36: still ✗, closer. Karnal has no SHC average; its neighbours are UP cane districts.
- Unchanged: Jangoan, Vidisha, Muzaffarpur, Purba Bardhaman, Yavatmal, Ludhiana first picks ✓; Bikaner and Guntur ✗.

Web check score now: main crop first 16 of 21, in list 21 of 23. The remaining gaps (arid Rajasthan, Guntur's 2022
split, neighbours from another cropping system) are written up for the paper in `research/paper_limitations.md`.
