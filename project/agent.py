"""Consultant agent: an LLM chats with the farmer and calls recommend.py as tools.

Gemini first; if it fails (no internet, quota), Qwen3-4B on this laptop via Ollama. Both speak the OpenAI chat format.
The ML models decide, the LLM explains: every crop, price, yield or weather number comes from a tool result.
Design: docs/agent.md. Settings in .env (GEMINI_API_KEY, GEMINI_MODEL, OLLAMA_URL, OLLAMA_MODEL, LLM_TIMEOUT).
"""
import datetime
import json
import os
import re
import sys
from functools import lru_cache

import pandas as pd
import requests
from dotenv import load_dotenv

import data
import recommend

load_dotenv(data.ROOT / ".env")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PROVIDERS = [  # (name, OpenAI-compatible base URL, API key, model), tried in order; no key = skipped
    *[("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", os.environ.get("GEMINI_API_KEY"), m.strip())
      for m in os.environ.get("GEMINI_MODEL", "gemini-3.5-flash,gemini-2.5-flash").split(",")],  # busy model -> next
    ("ollama", f"{OLLAMA_URL}/v1", "ollama",  # Qwen3-4B-Instruct-2507; plain qwen3:4b is thinking-only, too slow on CPU
     os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct")),
]
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", 600))  # laptop CPU: a long Ollama reply takes minutes
MAX_ROUNDS = 4  # tool-call rounds per message; then the model must answer
HISTORY = 10  # past messages sent with each request; the farm profile carries the rest
SESSIONS = data.ROOT / "data" / "sessions"
FARMER_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # used in a file name
FARM_KEYS = ("N", "P", "K", "ph", "district", "state", "month")

SYSTEM = """You are a crop advisor for Indian farmers.

Farm profile (saved from earlier tool calls): {profile}

Rules:
- Use the tools for every crop, price, yield or weather fact. Never guess a number.
- The tools decide which crops are best. Explain their result; do not change the ranking.
- Farm values already in the profile can be left out of tool calls; they are filled in for you.
- If soil values or district are missing, ask for them. A farmer without a Soil Health Card can use get_area_soil.
- If a crop has no price data, say so.
- Reply in the same language as the farmer's last message. Keep it short and simple.
- The app shows each tool result as a card under your reply. Don't list every number again: say in 2-4 short
  sentences what the result means for this farmer, quoting only the numbers that matter. Write money like ₹42,193.
- Talk in acres: quote net_rs_acre, net_rs_acre_month and yield_q_acre, never the per-hectare fields. A crop that
  takes fewer months (grow_months) frees the land sooner; no grow_months means a yearly crop.
- For pesticides, loans or disease, suggest the local Krishi Vigyan Kendra.
- If a question is not about farming, say you can only help with crops."""


def _run(N, P, K, ph, district, state=None, month=None, top=3) -> tuple[dict, pd.DataFrame]:
    sow = datetime.date(datetime.date.today().year, int(month or datetime.date.today().month), 1)
    return recommend.recommend(float(N), float(P), float(K), float(ph), district, state, sow=sow, top=top)


def recommend_crops(**farm) -> dict:
    inputs, table = _run(**farm)
    out = {k: inputs[k] for k in ("district", "state", "season", "temperature", "rainfall")}
    out["crops"] = table[["crop", "suitability", "yield_q_acre", "price_rs_q", "price_source", "price_mape",
                      "net_rs_acre", "grow_months", "net_rs_acre_month"]] \
        .to_dict("records")
    if inputs["season_share"] < recommend.QUIET_SEASON:
        out["warning"] = f"Little is sown in {inputs['district']} in the {inputs['season']} season; picks rest on other districts."
    asked = min(int(farm.get("top") or 3), recommend.MAX_TOP)
    if len(table) < asked:
        out["note"] = (f"Only {len(table)} of the {asked} crops asked for are shown: the others are below "
                       f"{recommend.MIN_SUITABILITY:.0%} suitability, too poor a fit to suggest.")
    return out


def check_crop(crop: str, **farm) -> dict:
    inputs, _ = _run(**farm)
    return recommend.check_crop(inputs, crop.strip().lower())


def get_weather(district: str, state: str | None = None, **_) -> dict:
    d = recommend.find_district(district, state)
    return {"district": d["district_name"], "state": d["state_name"], **recommend.weather(d["lat"], d["lon"])}


def get_price_forecast(crop: str, state: str | None = None, **_) -> dict:
    return recommend.price_outlook(crop.strip().lower(), state)


def get_area_soil(district: str, state: str | None = None, **_) -> dict:
    values, source = recommend.area_soil(district, state)
    return {**values, "source": source}


TOOL_FUNCS = {f.__name__: f for f in (recommend_crops, check_crop, get_weather, get_price_forecast, get_area_soil)}


@lru_cache
def tools() -> list[dict]:
    """Ollama tool schemas. Built on first use: the crop list comes from the model file."""
    crop = {"type": "string", "enum": recommend._model()["classes"]}
    place = {"district": {"type": "string"},
             "state": {"type": "string", "description": "Only needed when the district name is in two states"}}
    farm = {"N": {"type": "number", "description": "Nitrogen, kg/ha, from the Soil Health Card"},
            "P": {"type": "number", "description": "Phosphorus, kg/ha"},
            "K": {"type": "number", "description": "Potassium, kg/ha"},
            "ph": {"type": "number", "description": "Soil pH"}, **place,
            "month": {"type": "integer", "description": "Sowing month 1-12, default this month"}}

    def tool(name, description, props, required=()):
        return {"type": "function", "function": {"name": name, "description": description,
                "parameters": {"type": "object", "properties": props, "required": list(required)}}}

    return [
        tool("recommend_crops", "Top crops for the farm with suitability, yield, harvest price and net return. "
             "For 'what should I grow?'",
             {**farm, "top": {"type": "integer", "description": f"How many crops, 1-{recommend.MAX_TOP}. Default 3; "
                              "set it only when the farmer asks for more or fewer"}}),
        tool("check_crop", "One crop for the farm: suitability, rank, yield, price, net return and why. "
             "For 'why not X?' or 'can I grow X?'", {"crop": crop, **farm}, ["crop"]),
        tool("get_weather", "Average temperature, humidity and monthly rainfall for the district (year, kharif, rabi)",
             place, ["district"]),
        tool("get_price_forecast", "Mandi price forecast for the next 12 months, Rs/quintal",
             {"crop": crop, "state": place["state"]}, ["crop"]),
        tool("get_area_soil", "Typical N, P, K and pH for the district, for a farmer without a Soil Health Card",
             place, ["district"]),
    ]


def run_tool(name: str, args: dict, profile: dict) -> dict:
    """Call one tool with the profile's farm values filling in missing arguments; save what worked to the profile.
    Errors go back to the model as text, so it can fix the call or ask the farmer."""
    if name not in TOOL_FUNCS:
        return {"error": f"Unknown tool {name!r}. Tools: {', '.join(TOOL_FUNCS)}"}
    args = {**profile["farm"], **{k: v for k, v in args.items() if v not in (None, "")}}
    try:
        result = TOOL_FUNCS[name](**args)
    except (ValueError, TypeError, KeyError) as err:
        return {"error": str(err)}
    if name in ("recommend_crops", "check_crop"):
        profile["farm"] = {k: args[k] for k in FARM_KEYS if k in args}
    if name == "recommend_crops":
        profile["last_recommendation"] = [c["crop"] for c in result["crops"]]
    return json.loads(pd.Series(result).to_json())  # NaN -> null


def _profile_path(farmer_id: str):
    if not FARMER_ID.match(farmer_id):
        raise ValueError("farmer_id: 1-64 letters, digits, _ or -")
    return SESSIONS / f"{farmer_id}.json"


def load_profile(farmer_id: str) -> dict:
    p = _profile_path(farmer_id)
    return json.loads(p.read_text()) if p.exists() else {"farm": {}, "last_recommendation": [], "history": []}


def _llm(messages: list[dict], last_round: bool, providers: list[tuple]) -> tuple[dict, tuple]:
    """The first provider that answers: (assistant message, provider)."""
    err = requests.ConnectionError("No chat model configured: set GEMINI_API_KEY or run Ollama")
    for provider in providers:
        name, url, key, model = provider
        if not key:
            continue
        body = {"model": model, "messages": messages, "temperature": 0, "tools": tools()}
        if last_round:
            body["tool_choice"] = "none"
        try:
            r = requests.post(f"{url}/chat/completions", headers={"Authorization": f"Bearer {key}"}, json=body,
                              timeout=TIMEOUT if name == "ollama" else 30)  # Gemini: 4-15 s normally; hung -> next
            r.raise_for_status()
            return r.json()["choices"][0]["message"], provider
        except requests.RequestException as e:
            print(f"agent: {name} failed ({e.__class__.__name__}: {str(e)[:200]}), trying next", file=sys.stderr)
            err = e
    raise err


def chat(farmer_id: str, message: str, farm: dict | None = None) -> dict:
    """One farmer message -> reply, the tool calls made (for the UI and the grounding check) and the model used.
    `farm`: values the farmer filled in on the app's soil card; they update the saved profile before the model runs."""
    profile = load_profile(farmer_id)
    if farm:
        profile["farm"] |= {k: v for k, v in farm.items() if k in FARM_KEYS and v not in (None, "")}
    shown = {"farm": profile["farm"], "last_recommendation": profile["last_recommendation"]}
    messages = [{"role": "system", "content": SYSTEM.format(profile=json.dumps(shown))},
                *profile["history"][-HISTORY:], {"role": "user", "content": message}]
    calls, providers = [], PROVIDERS
    for round_ in range(MAX_ROUNDS + 1):
        reply, used = _llm(messages, round_ == MAX_ROUNDS, providers)
        # only move down the list: Gemini 3 (first) rejects tool calls made by another model (no thought signature)
        providers = providers[providers.index(used):]
        tool_calls = reply.get("tool_calls") or []
        # tool_calls go back unchanged: Gemini 3 needs the thought signature they carry
        messages.append({"role": "assistant", "content": reply.get("content") or "",
                         **({"tool_calls": tool_calls} if tool_calls else {})})
        if not tool_calls or round_ == MAX_ROUNDS:
            break
        for call in tool_calls:
            name, args = call["function"]["name"], call["function"].get("arguments") or "{}"
            try:
                args = json.loads(args) if isinstance(args, str) else args
                result = run_tool(name, args, profile)
            except json.JSONDecodeError:
                result = {"error": "Tool arguments were not valid JSON"}
            calls.append({"tool": name, "args": args, "farm": dict(profile["farm"]), "result": result})  # farm: for /explain
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "name": name,
                             "content": json.dumps(result, ensure_ascii=False)})
    answer = (reply.get("content") or "").strip()
    profile["history"] = (profile["history"] + [{"role": "user", "content": message},
                                                {"role": "assistant", "content": answer}])[-HISTORY:]
    SESSIONS.mkdir(parents=True, exist_ok=True)
    _profile_path(farmer_id).write_text(json.dumps(profile, ensure_ascii=False, indent=1))
    return {"reply": answer, "tool_calls": calls, "model": f"{used[0]}/{used[3]}"}


if __name__ == "__main__":  # scripted model, no Ollama needed: tool dispatch, profile fill-in, errors, memory
    import tempfile
    from pathlib import Path

    SESSIONS = Path(tempfile.mkdtemp())
    def call(name, **args):
        return {"id": name, "function": {"name": name, "arguments": json.dumps(args)}}

    script = iter([
        {"content": None, "tool_calls": [call("recommend_crops", N=250, P=40, K=210, ph=6.8, district="Raipur", month=11)]},
        {"content": "Grow the first crop."},
        {"content": None, "tool_calls": [call("check_crop", crop="wheat"),  # soil left out: comes from the profile
                                         call("get_weather", district="Atlantis")]},
        {"content": "Wheat is lower."},
        {"content": "Which month?"},
    ])
    PROVIDERS = [("script", "", "", "fake")]
    _llm = lambda messages, last_round, providers: (next(script), providers[0])  # noqa: E731
    r = chat("test", "What should I grow? N 250 P 40 K 210 pH 6.8, Raipur, November")
    assert r["tool_calls"][0]["result"]["crops"], r
    p = load_profile("test")
    assert p["farm"]["district"] == "Raipur" and p["last_recommendation"] and len(p["history"]) == 2, p
    r = chat("test", "Why not wheat?")
    assert r["tool_calls"][0]["result"]["crop"] == "wheat" and "error" in r["tool_calls"][1]["result"], r
    chat("card", "What should I grow?", {"district": "Vidisha", "N": None, "bad_key": 1})  # soil card from the web UI
    assert load_profile("card")["farm"] == {"district": "Vidisha"}
    assert len(tools()) == len(TOOL_FUNCS) == 5
    try:
        load_profile("../etc/passwd")
        raise AssertionError("bad farmer_id accepted")
    except ValueError:
        pass
    print(json.dumps(r["tool_calls"][0]["result"], indent=1))
    print("ok")
