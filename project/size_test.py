"""Model-size test for the consultant agent (docs/agent.md, "Proving the choice").

Runs the 40 questions in research/size_test/questions.json through agent.chat(), one model at a time, each question
with a fresh farm profile, and scores by script: right tool, valid arguments, grounded (every number in the reply is
in a tool result or the question), right language, seconds per answer, RAM. Answers go to
research/size_test/<model>.jsonl as they come, so a stopped run resumes where it left off.

    python project/size_test.py run qwen3:1.7b qwen3:4b-instruct qwen3:8b groq:openai/gpt-oss-120b
    python project/size_test.py run groq:qwen/qwen3.8-27b#prompt2 --only recommend   # re-run after a change
    python project/size_test.py score
    python project/size_test.py --check   # scorer self-check, no model
"""
import datetime
import json
import os
import re
import sys
import time

import pandas as pd
import requests

import agent
import data

DIR = data.ROOT / "research" / "size_test"
QUESTIONS = DIR / "questions.json"
HYBRID = {"qwen3:1.7b", "qwen3:8b", "groq:qwen/qwen3.8-27b"}  # think by default; "/no_think" is Qwen3's switch (this Ollama ignores think: false)

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(lakh|लाख|thousand|हज़ार|हजार)?", re.I)
SCALE = {"lakh": 1e5, "लाख": 1e5, "thousand": 1e3, "हज़ार": 1e3, "हजार": 1e3}
FREE = {*range(13), 2026, 2027}  # counts, months, years: not facts that need a tool
MR_WORDS = {"आहे", "आहेत", "आणि", "तुम्ही", "तुमच्या", "तुमचे", "तुमची", "करा", "नाही", "साठी", "मध्ये", "पीक", "किंवा",
            "होईल", "शकता", "म्हणून", "जास्त", "हे", "ही", "आपल्या", "आपण", "असेल", "सध्या", "मिळेल", "घ्या", "तुमचा"}
HI_WORDS = {"है", "हैं", "और", "आप", "आपके", "आपकी", "आपका", "के", "की", "का", "में", "नहीं", "लिए", "फसल", "होगा",
            "सकते", "इसलिए", "ज़्यादा", "ज्यादा", "यह", "से", "पर", "को", "रहा", "रही", "मिलेगा", "करें"}


def slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9.-]", "_", model)


def numbers(text: str) -> list[float]:
    """Every number in the text, with lakh/thousand applied. Commas are Indian or Western grouping."""
    out = []
    for digits, unit in NUMBER.findall(str(text).translate(DEVANAGARI_DIGITS)):
        digits = digits.rstrip(",").replace(",", "")
        if digits:
            out.append(float(digits) * SCALE.get(unit.lower(), 1))
    return out


def sources(obj) -> set[float]:
    """Numbers a reply may quote: every number in the tool results or the question; shares also as percents."""
    found = set()
    if isinstance(obj, dict):
        for v in obj.values():
            found |= sources(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= sources(v)
    elif isinstance(obj, bool) or obj is None:
        pass
    elif isinstance(obj, (int, float)):
        found |= {abs(obj), abs(obj) * 100} if abs(obj) <= 1 else {abs(obj)}
    else:
        found |= set(numbers(obj))
    return found


def ungrounded(reply: str, allowed: set[float]) -> list[float]:
    """Numbers in the reply that no tool gave (2% or 0.5 slack for rounding)."""
    return [x for x in numbers(reply)
            if x not in FREE and not any(abs(x - s) <= max(0.02 * s, 0.51) for s in allowed)]


def language(text: str) -> str:
    deva, latin = len(re.findall(r"[ऀ-ॿ]", text)), len(re.findall(r"[A-Za-z]", text))
    if latin >= deva:
        return "en"
    words = set(re.findall(r"[ऀ-ॿ]+", text))
    return "mr" if len(words & MR_WORDS) > len(words & HI_WORDS) else "hi"


# Crop names a reply may use (English, Hindi, Marathi), to find which crop it names first. ponytail: base forms only;
# a Marathi oblique form ("गव्हाला") is missed and the reply counts as naming no crop (kept_top = None).
CROP_NAMES = {
    "wheat": "wheat गेहूँ गेहूं गेंहू गहू", "chickpea": "chickpea gram चना छोले हरभरा", "mustard": "mustard सरसों मोहरी",
    "rice": "rice paddy धान चावल भात तांदूळ", "maize": "maize corn मक्का मका", "soybean": "soybean soyabean सोयाबीन",
    "cotton": "cotton कपास कापूस", "onion": "onion प्याज़ प्याज कांदा", "potato": "potato आलू बटाटा",
    "sugarcane": "sugarcane गन्ना ऊस", "coconut": "coconut नारियल नारळ", "pigeonpeas": "pigeon arhar tur अरहर तुअर तूर",
    "jowar": "jowar sorghum ज्वार ज्वारी", "bajra": "bajra millet बाजरा बाजरी", "groundnut": "groundnut peanut मूंगफली मूँगफली भुईमूग",
    "lentil": "lentil masoor मसूर", "barley": "barley जौ जव", "mungbean": "moong mung मूंग मूँग मूग",
    "blackgram": "urad blackgram उड़द उडद उडीद", "sesamum": "sesame sesamum तिल तीळ", "ragi": "ragi रागी नाचणी",
    "banana": "banana केला केळी", "mango": "mango आम आंबा", "orange": "orange संतरा संत्री संत्रा", "papaya": "papaya पपीता पपई",
    "jute": "jute जूट ताग", "mothbeans": "moth मोठ मटकी",
}


def first_crop(reply: str) -> str | None:
    """The crop the reply names first: whole words, or a word starting with a name of 4+ letters (plurals, suffixes)."""
    for word in re.findall(r"[A-Za-zऀ-ॿ]+", reply.lower()):
        for crop, names in CROP_NAMES.items():
            if any(word == n or (len(n) >= 4 and word.startswith(n)) for n in names.split()):
                return crop
    return None


def kept_top(q: dict, calls: list[dict], reply: str) -> bool | None:
    """Recommend questions: does the reply name the tool's top crop first? None when no crop name is found."""
    ok = [c for c in calls if c["tool"] == "recommend_crops" and "error" not in c["result"]]
    if q["type"] != "recommend" or not ok or not reply:
        return None
    named = first_crop(reply)
    return None if named is None else named == ok[-1]["result"]["crops"][0]["crop"]


def args_ok(call: dict, expect: dict) -> bool:
    if "error" in call["result"]:
        return False
    for k, v in expect.items():
        a = call["args"].get(k)
        if isinstance(v, (int, float)):
            try:
                if abs(float(a) - v) > 1e-6:
                    return False
            except (TypeError, ValueError):
                return False
        elif v.casefold() not in str(a).casefold():
            return False
    return True


def score_one(q: dict, a: dict) -> dict:
    calls, exp = a.get("tool_calls") or [], q["expect"]
    tools = [c["tool"] for c in calls]
    reply = a.get("reply") or ""
    allowed = sources([c["result"] for c in calls]) | sources(q["message"]) | sources(q.get("farm", {}))
    bad = ungrounded(reply, allowed)
    return {"id": q["id"], "lang": q["lang"], "type": q["type"],
            "right_tool": (not tools) if exp["tool"] is None else exp["tool"] in tools,
            "valid_args": None if exp["tool"] is None else any(args_ok(c, exp["args"]) for c in calls if c["tool"] == exp["tool"]),
            "grounded": bool(reply) and not bad, "ungrounded": bad,
            "right_language": bool(reply) and language(reply) == q["lang"], "kept_top": kept_top(q, calls, reply),
            "tool_errors": sum("error" in c["result"] for c in calls), "seconds": a["seconds"],
            "failed": bool(a.get("error")), "tools": tools}


def _ollama(path: str, **body) -> dict:
    r = requests.post(f"{agent.OLLAMA_URL}/api/{path}", json=body, timeout=60) if body else \
        requests.get(f"{agent.OLLAMA_URL}/api/{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def run(model: str, types: set[str] | None = None) -> None:
    """`model` may carry a #tag (a re-run after a change, saved to its own file); `types` limits the question types."""
    model, _, tag = model.partition("#")
    hosted = model.startswith(("gemini", "gemma", "groq:"))  # Gemini API (GEMINI_API_KEY) or Groq (GROQ_API_KEY)
    if model.startswith("groq:"):
        agent.PROVIDERS = [("groq", "https://api.groq.com/openai/v1", os.environ.get("GROQ_API_KEY"), model[5:])]
    elif hosted:
        agent.PROVIDERS = [("gemini", agent.PROVIDERS[0][1], agent.PROVIDERS[0][2], model)]
    else:
        for m in _ollama("ps")["models"]:  # one model in RAM at a time
            _ollama("generate", model=m["name"], keep_alive=0)
        agent.PROVIDERS = [("ollama", f"{agent.OLLAMA_URL}/v1", "ollama", model)]
    agent.SYSTEM = BASE_SYSTEM + ("\n/no_think" if model in HYBRID else "")
    agent.TIMEOUT = 1200
    agent.SESSIONS = DIR / "sessions"
    out = DIR / f"{slug(model)}{'#' + tag if tag else ''}.jsonl"
    done = {json.loads(line)["id"] for line in out.open()} if out.exists() else set()
    for q in json.loads(QUESTIONS.read_text()):
        if q["id"] in done or (types and q["type"] not in types):
            continue
        farmer = re.sub(r"[^A-Za-z0-9_-]", "_", f"{model}-{q['id']}")  # own profile per model: runs can overlap
        for attempt in range(6):
            (agent.SESSIONS / f"{farmer}.json").unlink(missing_ok=True)  # fresh profile every question and retry
            start = time.time()
            try:
                r = agent.chat(farmer, q["message"], q.get("farm"))
                break
            except requests.RequestException as e:  # hosted: 429/503 come and go; Ollama: a timeout is a result
                r = {"reply": "", "tool_calls": [], "model": model, "error": f"{e.__class__.__name__}: {str(e)[:200]}"}
                if not hosted:
                    break
                if attempt == 5:  # daily quota gone: stop without recording, the next run resumes here
                    raise
                time.sleep(30 * (attempt + 1))
        r |= {"id": q["id"], "seconds": round(time.time() - start, 1)}
        with out.open("a") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{model} {q['id']}: {r['seconds']} s, tools {[c['tool'] for c in r['tool_calls']]}", flush=True)
    if not hosted:
        size = next((m["size"] for m in _ollama("ps")["models"] if m["name"].startswith(model)), None)
        (DIR / f"{slug(model)}.meta.json").write_text(json.dumps({"model": model, "ram_bytes": size}))
        _ollama("generate", model=model, keep_alive=0)


def score() -> pd.DataFrame:
    qs = {q["id"]: q for q in json.loads(QUESTIONS.read_text())}
    rows = []
    for f in sorted(DIR.glob("*.jsonl")):
        model = f.stem
        meta = DIR / f"{model}.meta.json"
        ram = json.loads(meta.read_text())["ram_bytes"] if meta.exists() else None
        for line in f.open():
            a = json.loads(line)
            rows.append({"model": model, "ram_gb": ram and round(ram / 1e9, 1), **score_one(qs[a["id"]], a)})
    df = pd.DataFrame(rows)
    pct = lambda s: round(100 * s.dropna().astype(bool).mean(), 1)  # noqa: E731
    table = df.groupby("model").agg(
        answers=("id", "size"), right_tool=("right_tool", pct), valid_args=("valid_args", pct),
        grounded=("grounded", pct), right_language=("right_language", pct), kept_top=("kept_top", pct),
        kept_top_unknown=("kept_top", lambda s: int(((df.loc[s.index, "type"] == "recommend") & s.isna()).sum())),
        failed=("failed", "sum"),
        median_s=("seconds", "median"), mean_s=("seconds", "mean"), ram_gb=("ram_gb", "first")).round(1)
    by = df.melt(id_vars=["model", "lang", "type"], value_vars=["right_tool", "grounded", "right_language"])
    print(table.to_string(), "\n")
    print(by.groupby(["model", "variable", "lang"])["value"].apply(pct).unstack().to_string(), "\n")
    print(by.groupby(["model", "variable", "type"])["value"].apply(pct).unstack().to_string(), "\n")
    today = datetime.date.today()
    table.to_csv(data.ROOT / "research" / "results" / f"{today}_agent_size_test.csv")
    df.to_csv(DIR / f"{today}_scored.csv", index=False)
    return table


BASE_SYSTEM = agent.SYSTEM

if __name__ == "__main__":
    if sys.argv[1:2] == ["run"]:  # run MODEL[#tag]... [--only recommend,why-not]
        args, only = sys.argv[2:], None
        if "--only" in args:
            i = args.index("--only")
            only = set(args[i + 1].split(","))
            del args[i:i + 2]
        for m in args:
            run(m, only)
    elif sys.argv[1:2] == ["score"]:
        score()
    else:  # --check
        assert numbers("₹42,193 net, ≈ ₹4,269 a month; १२३ and 1,23,456") == [42193, 4269, 123, 123456]
        assert numbers("about 49 हज़ार or 1.5 lakh") == [49000, 150000]
        result = {"crops": [{"crop": "wheat", "suitability": 0.495, "net_rs_acre": 20665.0, "month": "Dec 2026"}]}
        allowed = sources(result) | sources("N 250, P 40")
        assert ungrounded("Wheat fits 49.5% of farms like yours, about ₹20,700 an acre, by Dec 2026.", allowed) == []
        assert ungrounded("Keep pH between 5.5 and 7.5; N 250 is fine.", allowed) == [5.5, 7.5]
        assert language("Wheat is best for you.") == "en"
        assert language("आपके खेत के लिए गेहूँ सबसे अच्छी फसल है।") == "hi"
        assert language("तुमच्या शेतासाठी गहू हे पीक चांगले आहे.") == "mr"
        call = {"tool": "check_crop", "args": {"crop": "Mustard", "N": "250"}, "result": {"crop": "mustard"}}
        assert args_ok(call, {"crop": "mustard", "N": 250}) and not args_ok({**call, "result": {"error": "x"}}, {})
        q = {"id": "x", "lang": "en", "type": "off-topic", "message": "Who won?", "expect": {"tool": None}}
        s = score_one(q, {"reply": "India won in 2023.", "tool_calls": [], "seconds": 1})
        assert s["right_tool"] and not s["grounded"] and s["valid_args"] is None, s
        assert first_crop("सबसे अच्छा गेहूं है, फिर चना") == "wheat" and first_crop("Chickpeas, then wheat") == "chickpea"
        assert first_crop("सूचना: कोई फसल नहीं") is None and first_crop("तुमच्यासाठी कांदा चांगला") == "onion"
        rec = [{"tool": "recommend_crops", "result": {"crops": [{"crop": "wheat"}, {"crop": "chickpea"}]}}]
        assert kept_top({"type": "recommend"}, rec, "Chickpea earns most, wheat fits best.") is False
        print("ok")
