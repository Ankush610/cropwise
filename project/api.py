"""FastAPI backend: the recommend.py functions over HTTP, for the web UI and the agent.

Run from the repo root: .venv/bin/python project/api.py (HOST and PORT from .env; self-check: add --check)
Interactive docs: http://127.0.0.1:8000/docs
"""
import datetime
import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import agent
import recommend

app = FastAPI(title="Crop recommendation")


@app.exception_handler(ValueError)
def bad_input(request: Request, err: ValueError) -> JSONResponse:
    """recommend.py raises ValueError for an unknown district or crop, or soil out of range."""
    return JSONResponse({"detail": str(err)}, status_code=400)


@app.exception_handler(requests.RequestException)
def llm_down(request: Request, err: requests.RequestException) -> JSONResponse:
    return JSONResponse({"detail": f"No chat model reachable: Gemini and Ollama both failed ({err.__class__.__name__}). "
                                   "/recommend and /explain still work."}, status_code=503)


class Farm(BaseModel):
    N: float = Field(ge=0, description="Nitrogen, kg/ha (Soil Health Card)")
    P: float = Field(ge=0, description="Phosphorus, kg/ha")
    K: float = Field(ge=0, description="Potassium, kg/ha")
    ph: float = Field(ge=3, le=10)
    district: str
    state: str | None = Field(None, description="Needed only when the district name is in two states")
    month: int = Field(default_factory=lambda: datetime.date.today().month, ge=1, le=12, description="Sowing month")


class CropQuery(Farm):
    crop: str


def _run(f: Farm) -> tuple[dict, pd.DataFrame]:
    sow = datetime.date(datetime.date.today().year, f.month, 1)  # only the month matters: season and harvest-month price
    return recommend.recommend(f.N, f.P, f.K, f.ph, f.district, f.state, sow=sow)


@app.get("/districts")
def districts() -> list[dict]:
    d = recommend._tables()[2].sort_values(["state_name", "district_name"])
    return [{"state": s, "district": n} for s, n in zip(d["state_name"], d["district_name"])]


@app.get("/soil")
def soil(district: str, state: str | None = None) -> dict:
    """Typical N, P, K, pH for a farmer without a Soil Health Card."""
    values, source = recommend.area_soil(district, state)
    return {**values, "source": source}


@app.get("/weather")
def weather(district: str, state: str | None = None) -> dict:
    d = recommend.find_district(district, state)
    return {"district": d["district_name"], "state": d["state_name"], **recommend.weather(d["lat"], d["lon"])}


@app.post("/recommend")
def recommend_crops(f: Farm) -> dict:
    """Top 3 crops with suitability, yield, price, net return and their sources."""
    inputs, table = _run(f)
    # to_json turns NaN (no price, no yield) into null; FastAPI's encoder rejects NaN
    return {"inputs": json.loads(pd.Series(inputs).to_json()), "crops": json.loads(table.to_json(orient="records"))}


@app.post("/explain")
def explain(q: CropQuery) -> dict:
    """SHAP for any crop the model knows, not only the top 3: how much each input pushed its suitability up or down."""
    inputs, _ = _run(q)
    e = recommend.explain(inputs, q.crop)
    pushes = sorted(zip(e.feature_names, e.data, e.values), key=lambda t: -abs(t[2]))
    return {"crop": q.crop, "average": round(float(e.base_values), 3),
            "suitability": round(float(e.base_values + e.values.sum()), 3), "reason": recommend.reasons(e),
            "pushes": [{"feature": recommend.FEATURE_NAMES[f], "value": float(v), "push": round(float(p), 3)}
                       for f, v, p in pushes]}


class Message(BaseModel):
    farmer_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="Keeps the farm profile between chats")
    message: str = Field(min_length=1, max_length=2000)
    farm: dict[str, str | float | int | None] | None = Field(None, description="Soil card values from the web UI")


@app.post("/chat")
def chat(m: Message) -> dict:
    """Consultant agent: reply in the farmer's language, plus the tool calls behind every number in it."""
    return agent.chat(m.farmer_id, m.message, m.farm)


@app.get("/profile/{farmer_id}")
def profile(farmer_id: str) -> dict:
    """Saved farm values and chat text, so the web UI can restore a conversation after a reload."""
    return agent.load_profile(farmer_id)


# Web UI (project/web). Mounted last so the API routes above match first.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")


if __name__ == "__main__" and "--check" not in sys.argv:
    import uvicorn

    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8000)))  # .env loaded by agent

elif __name__ == "__main__":
    from fastapi.testclient import TestClient

    c = TestClient(app)
    farm = {"N": 250, "P": 40, "K": 210, "ph": 6.8, "district": "Raipur", "month": 11}
    r = c.post("/recommend", json=farm).json()
    assert 1 <= len(r["crops"]) <= 3, r
    top = r["crops"][0]
    e = c.post("/explain", json={**farm, "crop": top["crop"]}).json()
    assert abs(e["suitability"] - top["suitability"]) < 2e-3, (e, top)  # SHAP adds up to the suitability shown
    assert c.post("/recommend", json={**farm, "district": "Atlantis"}).status_code == 400
    assert c.post("/recommend", json={**farm, "ph": 14}).status_code == 422
    assert c.post("/explain", json={**farm, "crop": "tomato"}).status_code == 400
    assert c.get("/soil", params={"district": "Ludhiana", "state": "Punjab"}).json()["source"].startswith("Mean of nearest")
    assert len(c.get("/districts").json()) > 500
    agent.PROVIDERS = [("down", "http://127.0.0.1:9", "key", "m")] * 2  # nothing listens there
    assert c.post("/chat", json={"farmer_id": "selfcheck", "message": "hi"}).status_code == 503
    assert c.post("/chat", json={"farmer_id": "../x", "message": "hi"}).status_code == 422
    assert c.get("/profile/nobody-yet").json()["history"] == [] and c.get("/profile/a.b").status_code == 400
    assert "<html" in c.get("/").text and c.get("/css/tokens.css").status_code == 200
    print(top, e["reason"], sep="\n")
    print("ok")
