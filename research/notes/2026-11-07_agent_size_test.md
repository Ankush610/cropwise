# Agent model-size test · Nov 7, 2026

Does a small local model run the consultant agent as well as a bigger one? Planned in `docs/agent.md`
("Proving the choice"). Table: `results/2026-11-07_agent_size_test.csv` (includes the `#prompt2` re-runs); per question:
`size_test/2026-11-07_scored.csv`; raw answers and tool calls: `size_test/<model>.jsonl`.

## Data

`size_test/questions.json`: 40 questions, 20 English, 10 Hindi, 10 Marathi, 10 each of recommend, why-not, price and
off-topic (incl. pesticide, loan and vet questions that should go to the KVK without a tool). Half the farm questions
give soil values in the message, half send them on the app's farm card. Sowing month fixed (June or November).
Tools use the Nov 6 price forecast and the season crop model.

## Settings

- Run through the app's own `agent.chat()` (`project/size_test.py`): same system prompt, 5 tools, 4 tool rounds,
  temperature 0, a fresh farm profile per question. Qwen3 hybrid models get `/no_think` (local Ollama ignores
  `think: false`); `<think>`/`<thought>` blocks are stripped from replies.
- **Scored by script:** right tool (expected tool called; off-topic: no tool), valid arguments (that tool ran without
  error and its key arguments match the question), grounded (every number in the reply appears in a tool result or the
  question, 2% or 0.5 slack for rounding; counts 0–12 and the years 2026/27 are free), right language (script share
  plus Hindi/Marathi marker words), kept_top (recommend questions: the reply names the tool's top crop first), seconds
  per answer.
- Models: Qwen3-1.7B (Ollama, Q4, Intel i5-1245U CPU, 4096 context); Qwen3.8-27B and gpt-oss-120b on Groq's free tier;
  Gemini 2.5 Flash and 3.5 Flash on the AI Studio free tier.

## Results

| Model | Answers | Right tool | Valid args | Grounded | Right language | Kept top crop | Median s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.8-27B (Groq) | 40 | 97.5% | 96.7% | 100% | 100% | 70% | 1.4 |
| gpt-oss-120b (Groq) | 40 | 92.5% | 90.0% | 100% | 82.5% | 80% | 2.1 |
| Qwen3-1.7B (laptop CPU) | 22 * | 81.8% | 68.2% | 81.8% | 50.0% | 77.8% | 190 |
| Gemini 2.5 Flash | 9 * | 100% | 88.9% | 100% | 100% | 75% | 4.9 |
| Gemini 3.5 Flash | 5 * | 100% | 100% | 100% | 100% | 80% | 13.6 |

\* Partial. Qwen3-1.7B: all 10 recommend, all 10 why-not, 2 price, no off-topic; stopped by choice (190 s an answer,
the trend was clear). Gemini: free tier allows 20 requests a day per model; recommend questions only.
Qwen3-4B (the app's offline fallback) and Qwen3-8B were not run.

What the misses were:

- **Qwen3-1.7B:** answered every Hindi and Marathi question in English (0% right language in both); checked mango when
  asked "why not mustard?"; one empty reply; forgot pH and needed the tool's error to fix it; quoted per-hectare
  figures the prompt forbids. Matches the "too small" row in `docs/agent.md`.
- **gpt-oss-120b:** answered 6 of 20 English questions in Hindi or Marathi (and one Marathi question in Hindi),
  apparently assuming an Indian farmer wants an Indian language; on 3 price questions asked for the district instead of calling the price tool (the state was
  given or not needed).
- **Qwen3.8-27B:** one miss: asked for the district on a Hindi price question instead of calling the tool.
- **Grounding:** both large models quoted only tool numbers in all 40 answers.
- **Every model re-orders the ranking.** kept_top is 70–80% for every model: they put the crop with the
  highest net return first ("Mustard offers the highest net return", "Rice fits the soil best but is not profitable
  here, so I'd skip it"). This breaks "the ML models decide". It is a prompt problem, not a size problem; fixed and re-tested
  below ("Prompt fix").

## Prompt fix (same day)

Changes in `project/agent.py`: the prompt says `recommend_crops` lists crops best first and the first is the advice (a
lower crop that earns more may be mentioned, never called the best); the tool result names it in a new `recommended`
field; the language rule spells out English to English, Hindi to Hindi, Marathi to Marathi; the `district` argument
asks for English letters ("Vidisha, not विदिशा"). Re-run on the recommend and why-not questions, saved as
`size_test/<model>#prompt2.jsonl`. Scorer note: "छोले" (chickpea) was added to the crop names, which moved
gpt-oss-120b's first-run kept_top from 70% to 80%.

| Model, recommend + why-not | n | Right tool | Valid args | Grounded | Right language | Kept top crop |
| --- | --- | --- | --- | --- | --- | --- |
| gpt-oss-120b, before | 20 | 100% | 100% | 100% | 90% | 80% (of 10) |
| gpt-oss-120b, prompt fix | 20 | 95% | 95% | 100% | 100% | **100%** (of 10) |
| Qwen3.8-27B, before | 6 | 100% | 100% | 100% | 100% | 83% (of 6) |
| Qwen3.8-27B, prompt fix | 6 | 100% | 100% | 100% | 100% | **100%** (of 6) |

Qwen3.8-27B stopped at 6 of 20: Groq "over capacity", then its 200K tokens/day cap. The one new gpt-oss miss
(`why-en-1`) answered "why not mustard?" correctly but from `recommend_crops` instead of `check_crop`. Answers can
still add a caveat ("Maize is a safer bet" after naming rice first), which the new rule allows.

## Limits

- 40 questions, written by us; one run per model at temperature 0, so no variance estimate.
- Groq's Qwen3.8-27B sometimes returns `tool_use_failed` (it can't parse the model's tool call); the runner retries,
  so this test doesn't count those failures.
- The language check uses marker words; replies that mix scripts can be misread. Flagged answers were read by hand
  for gpt-oss-120b and Qwen3-1.7B and were correct.
- No RAM figure: the local run was stopped before it was recorded (Qwen3-1.7B showed 1.9 GB in `ollama ps`).
