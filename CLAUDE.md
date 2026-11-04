# Crop Recommendation System

An AI/ML system that suggests crops to a farmer from soil values and location,
then ranks them by expected profit and explains why.

## Deliverables

1. **Working system** — suitability model + price forecast + explanations, with a simple demo app.
2. **Research paper** — draft lives in `research/`.
3. **Conclave** — a talk plus a hands-on workshop session, material lives in `workshop/`.

## Key dates

- **Nov 10, 2026:** project complete (code, models, demo, frozen results).
- **Nov 15, 2026:** paper and conclave.

Schedule and scope cuts: `docs/plan.md`.

## Folders

| Folder | What goes here |
| --- | --- |
| `project/` | Final code: data loading, models, app. Code used in more than one place lives here. |
| `docs/` | Build logs, architecture plan, design choices. |
| `research/` | Paper draft, results tables, experiment records. |
| `notebooks/` | Jupyter notebooks for exploration and experiments. |
| `workshop/` | Workshop slides, handouts and participant notebooks. |

## Datasets

See `docs/Crop Recommendation System Datasets.md`. In short:
Kaggle Crop Recommendation (training), Agmarknet / CEDA (prices),
NASA POWER (weather), DES district area-production-yield (district yield and real-world test; replaces ICRISAT, which is offline),
Soil Health Card (district soil for the real-world test).

## Pipeline

1. Farmer enters N, P, K, pH and location.
2. NASA POWER fills in temperature, humidity and rainfall.
3. Classifier returns the top 3 suitable crops.
4. Price model ranks them by expected profit.
5. SHAP explains the choice.
6. Consultant agent (Qwen3-4B via Ollama) chats with the farmer, calling steps 2–5 as tools. See `docs/agent.md`.

## Rules

- Python. Planned stack: pandas, scikit-learn, XGBoost/LightGBM, SHAP, Prophet, Streamlit, Ollama.
- The ML models decide, the agent only explains. Every number the agent says must come from a tool result.
- Fix random seeds and report cross-validated scores, not one lucky split.
- Every result that might go in the paper gets recorded in `research/` with the date, data and settings used.
- Log notable build steps and decisions in `docs/`.
- Be honest about limits in the paper: the Kaggle data is likely synthetic and has no location,
  and no single dataset links soil, crop and price for the same farm.
- Workshop notebooks must run in Google Colab with no local setup.
