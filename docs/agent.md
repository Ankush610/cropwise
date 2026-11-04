# Consultant Agent

Oct 29, 2026. A small LLM agent that talks to the farmer, calls our ML pipeline as tools,
remembers the farm, and explains results in the farmer's language.

**Core rule: the ML models decide, the LLM explains.** The agent never invents a crop, price or yield.
Every number it says must come from a tool result.

## How it works

```
Farmer message
   │
   ▼
┌────────────────────────────────────────────────┐
│ System prompt + farm profile (memory) + chat   │
│                    │                           │
│                    ▼                           │
│         Small LLM decides: answer or call tool │◄──┐
│                    │                           │   │
│          tool call ▼                           │   │ tool result
│   recommend_crops / check_crop /               │   │ (max 4 rounds)
│   get_weather / get_price_forecast  ───────────┼───┘
│                    │                           │
│        final answer ▼                          │
└────────────────────────────────────────────────┘
   │
   ▼
Reply in farmer's language + profile saved
```

## Tools

Each tool is a thin wrapper around `project/recommend.py`. No new ML logic lives in the agent.
Only four tools: small models choose tools more reliably from a short list.

| Tool | Inputs | Returns | Answers questions like |
| --- | --- | --- | --- |
| `recommend_crops` | N, P, K, pH, district, sowing date (sets the season) | Top 3: crop, suitability, expected revenue, whether price data exists | "What should I grow?" |
| `check_crop` | crop, N, P, K, pH, district, sowing date | Suitability, rank out of 27, yield, price, top SHAP reasons | "Why not cotton?" "Can I grow wheat?" |
| `get_weather` | district | Temperature, humidity, rainfall (year, kharif, rabi) | "How much rain does my area get?" |
| `get_price_forecast` | crop, state | Forecast price and trend | "Will onion prices go up?" |
| `get_area_soil` | district | Typical N, P, K, pH for the area and where they came from (`recommend.area_soil`) | "I don't have a soil card" |

Tool inputs are checked in code (crop is one of the 27, N/P/K/pH in valid ranges, district known).
A bad input returns an error message to the model so it can fix it or ask the farmer.

## Memory

| Layer | What | Where |
| --- | --- | --- |
| Conversation | Last 10 messages | In the request |
| Farm profile | District, N, P, K, pH, language, last recommendation | `data/sessions/<farmer_id>.json`, added to the system prompt every turn |

The profile is saved by code from tool inputs and results, not by the model.
A small model forgets things in a long chat. Putting the profile in the prompt every turn means it never has to remember.

Skipped: long-term semantic memory (vector store). Add it when farmers come back across many seasons.

## System prompt (draft)

```
You are a crop advisor for Indian farmers.

Farm profile: {profile_json}

Rules:
- Use the tools for every crop, price, yield or weather fact. Never guess a number.
- The tools decide which crops are best. Explain their result; do not change the ranking.
- If soil values or district are missing, ask for them.
- If a crop has no price data, say so.
- Reply in the farmer's language ({language}). Keep it short and simple.
- For pesticides, loans or disease, suggest the local Krishi Vigyan Kendra.
- If a question is not about farming, say you can only help with crops.
```

Kept short on purpose: small models follow short prompts better than long ones.

## Choosing the model

### What the task needs

1. **Reliable tool calling:** pick the right tool and fill in valid arguments.
2. **Stay grounded:** repeat tool numbers correctly, don't invent new ones.
3. **Hindi and Marathi** replies a farmer can read.
4. **Run on a normal laptop** (ours: Intel i5-1245U, 16 GB RAM, no GPU) and in free Colab for the workshop.

It does **not** need deep reasoning. The hard thinking (which crop suits the soil, what prices will do) is done by the ML models.
The LLM only routes questions and explains answers.

### Why not smaller, why not bigger

| Size | Example | Verdict |
| --- | --- | --- |
| ≤ 2B | Qwen3-1.7B, Llama 3.2 1B | **Too small.** Picks the wrong tool, breaks argument JSON, weak in Marathi, starts inventing numbers. |
| **~4B** | **Qwen3-4B** | **Sweet spot.** Native tool calling, ~2.5 GB at 4-bit, runs on our laptop CPU at usable speed. |
| 7–8B | Qwen3-8B | Better language and fewer mistakes, but ~5 GB at 4-bit; slow on a laptop CPU with no GPU. Good on Colab's T4. |
| 14B+ | Qwen3-14B, Llama 70B | **Overkill.** Needs a big GPU. Extra reasoning power is wasted, since the ML models already make the decision. |
| Hosted API | Claude Haiku 5.5 | Best quality and language support, very cheap per chat, but needs internet and an API key. Used as the **upper-bound reference**, not the main model. |

**Nov 4 change:** the live app uses Gemini first (`gemini-3.5-flash`, then `gemini-2.5-flash`) and falls back to
Qwen3-4B-Instruct on the laptop (no internet, quota). On the laptop CPU Qwen3-4B takes ~4 min per answer and added
facts the tools never gave (a pH "optimal range") in the first real test; Gemini answers in 3–15 s. The size test
below still compares the local models, with Gemini as the reference.

### Pick: Qwen3-4B, run locally with Ollama

- Trained for tool calling, with a built-in thinking mode we can switch on for "why not X" questions and off for quick replies.
- Lists Hindi and Marathi among its supported languages. (Llama 3.2 officially supports Hindi but not Marathi. Gemma 3 has no native tool-call format. Phi-4-mini is weaker in Indian languages.)
- Apache 2.0 license, free to use and share in the workshop.
- Runs offline, so the conclave demo doesn't depend on venue Wi-Fi, and farmer data stays on the device.

Check before building: confirm Qwen3-4B is still the best ~4B tool-calling model on Ollama and pin the exact version.

### Proving the choice (goes in the paper)

The size reasoning above is a claim. A small test turns it into a result.

- **Test set:** 40 questions (20 English, 10 Hindi, 10 Marathi) across four types: recommend, why-not, price, off-topic.
- **Models:** Qwen3-1.7B, Qwen3-4B, Qwen3-8B, plus Claude Haiku 5.5 as the reference.
- **Metrics:**
  - right tool chosen (%)
  - valid arguments (%)
  - grounded: every number in the answer appears in a tool result (%, checked by script)
  - replied in the right language (%)
  - seconds per answer and RAM used

Expected result: 1.7B fails on tools and grounding, 4B gets close to 8B at about half the memory, Haiku sets the ceiling.
Results go in `research/` as the model-size table.

## Code

`project/agent.py` (built Nov 4): tool schemas, the agent loop (max 4 tool rounds, then the model must answer),
profile load/save in `data/sessions/<farmer_id>.json`. Served by FastAPI as `POST /chat` (`project/api.py`), which
returns the reply plus every tool call and result, so the UI can show the numbers' source and the size test can check
grounding by script, and which model answered. If every model fails, `/chat` returns 503 and `/recommend` and
`/explain` still work.

- Providers, tried in order through their OpenAI-compatible chat endpoints (plain `requests`, no SDK): each model in
  `GEMINI_MODEL` (comma-separated, default `gemini-3.5-flash,gemini-2.5-flash`), then `OLLAMA_MODEL` (default
  `qwen3:4b-instruct`, Qwen3-4B-Instruct-2507). Settings and `GEMINI_API_KEY` live in `.env` (git-ignored).
- Within one message the agent only moves *down* the list: Gemini 3 rejects tool calls made by another model (they
  lack its thought signature), so after a fallback it never goes back up. Seen in testing: 503 on 3.8 Flash (high
  demand), 429 (free-tier rate limit) on 3.5 Flash mid-chat.
- Plain `qwen3:4b` on Ollama is now the thinking-only model: it reasons before every reply (~7 tokens/s on our CPU) and
  this Fedora Ollama build ignores `think: false`, so the first test timed out. The instruct tag answers directly.
- The web UI sends its soil card with every message (`/chat` `farm`); those values update the profile first, so the
  card is the source of truth and the advisor doesn't ask for a district the farmer already chose.
- The UI shows each tool result as a card under the reply, so the prompt asks for 2-4 sentences on what the result
  means instead of repeating every number.
- Farm values saved in the profile fill in missing tool arguments, so a follow-up like "why not wheat?" needs only the crop.
- Language: the model replies in the language of the farmer's last message (no language field in the profile).
- History keeps only the farmer's and the agent's text (last 10); tool results stay out, the profile carries the farm.
- New helpers in `recommend.py` for the tools: `check_crop()` (any crop, rank among the season's crops) and
  `price_outlook()` (12-month forecast, MSP in Punjab/Haryana).
- Self-check `python project/agent.py` runs a scripted model (no Ollama): dispatch, profile fill-in, errors, memory.
