# Crop Recommendation System

| Folder | What goes here |
| --- | --- |
| `project/` | The end product: all the code. |
| `docs/` | Progress docs: build logs, architecture plan, design choices. |
| `research/` | Draft paper, results tables and experiment records. |
| `notebooks/` | Jupyter notebooks. |
| `workshop/` | Workshop material. |

## Run

The trained models (`models/`) and the small tables the app reads (`data/processed/`, `data/raw/cost/`) are in git,
so a clone runs as is. The 1.7 GB of raw data is not: it is only needed to rebuild those tables or retrain, see
`docs/Crop Recommendation System Datasets.md`.

```bash
git clone https://github.com/Ankush610/cropwise.git && cd cropwise
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                       # then add your GEMINI_API_KEY
ollama pull qwen3:4b-instruct              # offline fallback chat model (once)
.venv/bin/python project/api.py            # web UI at http://HOST:PORT (from .env), API docs at /docs
.venv/bin/streamlit run project/app.py                # backup UI
```
