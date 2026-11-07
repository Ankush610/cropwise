# Project Plan

Started Oct 29, 2026. **Project done by Nov 10.** Conclave and paper on Nov 15.

## Schedule

| Dates | Work | Done when |
| --- | --- | --- |
| Oct 29–30 | **Data:** Kaggle, Agmarknet prices for the 22 crops (✅ Oct 30), NASA POWER, district yield (DES, replaces ICRISAT) (✅ Oct 30). Clean into `data/processed/`. | All four load in one notebook |
| Oct 31–Nov 1 | **Crop model:** LogReg, Random Forest, XGBoost, LightGBM, 5-fold CV. Train with vs without humidity. (✅ Nov 3, RF without humidity; Nov 3 update: + weather-noise augmentation + isotonic calibration) | Results table in `research/` |
| Nov 2–3 | **Price model:** seasonal-naive vs Prophet, scored by MAPE. (✅ Nov 3, seasonal-naive beats Prophet; Nov 3 update: median of ETS, ARIMA, Theta, seasonal-naive beats both) | Forecast for each crop |
| Nov 4 | **Ranking + SHAP:** expected revenue = district yield × forecast price; one SHAP plot per prediction. (✅ Nov 3, `project/recommend.py`; Nov 3 update: suitability order, net return over CACP cost breaks near-ties) | Top 3 ranked with explanations |
| Nov 5–6 | **Real-world check:** compare the model's picks with what each district grows (DES area data). (✅ Nov 3, Soil Health Card soil, 539 districts: no better than random; Kaggle N-P-K don't match real soil. Nov 4: replaced by a district model trained on SHC soil + DES area, 28 crops incl. wheat, soybean, sugarcane: main crop first 62% vs 50% for the most common crops, leave-state-out) | Match-rate table in `research/` |
| Nov 7–8 | **Demo + agent:** Streamlit app (✅ Nov 4, `project/app.py`), consultant agent (`docs/agent.md`). | Chat in Hindi gets a grounded answer |
| Nov 9 | **Model-size test:** Qwen3 1.7B / 4B / 8B + Haiku reference on 40 questions. (✅ Nov 7, changed: Qwen3.8-27B and gpt-oss-120b on Groq's free tier as references, Gemini partial (20 requests/day); Qwen3-1.7B stopped at 22 answers, 4B and 8B not run. `research/notes/2026-11-07_agent_size_test.md`) | Size table in `research/` |
| Nov 10 | **Buffer:** fixes, rerun everything, freeze results. | **Project complete** |
| Nov 11–12 | **Paper:** Results, Limitations, Abstract. Data and Method get written as each phase ends. | Full draft |
| Nov 11–13 | **Workshop:** Colab notebooks, slides. | Notebooks run clean in Colab |
| Nov 13–14 | Final paper review, talk and workshop dry run. | Ready |
| Nov 15 | **Conclave** | |

## Scope cuts to make the date

- **LSTM:** only if the price model finishes early. Prophet vs seasonal-naive is enough for the paper.
- **Cost of cultivation (CACP):** ✅ done Nov 3 for 9 field crops. Fruit cost stays a limitation.
- **Agent size test:** if behind, drop Qwen3-8B and Marathi from the test before touching the core models.

## Needed today

- Kaggle account (to download the dataset).
- ~~data.gov.in API key (for live mandi prices).~~ ✅ Nov 6, in `.env`.
