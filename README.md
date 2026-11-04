# Crop Recommendation System

| Folder | What goes here |
| --- | --- |
| `project/` | The end product: all the code. |
| `docs/` | Progress docs: build logs, architecture plan, design choices. |
| `research/` | Draft paper, results tables and experiment records. |
| `notebooks/` | Jupyter notebooks. |
| `workshop/` | Workshop material. |

## Run

```bash
.venv/bin/uvicorn api:app --app-dir project --reload   # API, docs at http://127.0.0.1:8000/docs
.venv/bin/streamlit run project/app.py                # backup UI
```
