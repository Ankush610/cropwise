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
cp .env.example .env                       # then add your GEMINI_API_KEY
ollama pull qwen3:4b-instruct              # offline fallback chat model (once)
.venv/bin/python project/api.py            # web UI at http://HOST:PORT (from .env), API docs at /docs
.venv/bin/streamlit run project/app.py                # backup UI
```
