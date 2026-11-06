# Ongoing issues

Open problems in the system, newest first within each area. Started Nov 4, 2026.
When an issue is fixed, move it to the build log (`build-log.md`) with the fix and delete it here.
Gaps that are limits of the data rather than bugs go in `research/paper_limitations.md` (linked at the end).

Priority is against the Nov 10 freeze: **High** = wrong advice or a broken demo, **Medium** = confusing or slow,
**Low** = polish.

## Prices and money

### Onion forecast for Maharashtra looks wrong · High
- **Seen:** web UI, Nov 4. `get_price_forecast(onion, Maharashtra)` gives ₹888–1,369 a quintal for Jun 2026 – May 2027,
  with a backtest error (MAPE) of 98.6%.
- **Why it matters:** onion in Maharashtra mandis usually trades well above this, and a 99% error means the forecast
  carries no information. The advisor quotes it anyway.
- **Check:** the Maharashtra onion series in `mandi_prices()` (units, outlier months, missing data) and notebook 06.
  Other crops with MAPE > 30% likely have the same problem; list them.
- **Done so far:** the web UI warns on any forecast with past error > 30%.

### Price forecast window starts in the past · High
- **Seen:** Nov 4. `price_forecast.csv` covers Jun 2026 – May 2027. Today is Nov 2026, so a June sowing (or any
  harvest before November) gets a price for a month that has already happened, and "next 12 months" is really 7.
- **Fix:** re-run the price forecast (notebook 06, section 4) from the latest mandi data, so it starts next month.
  Needs the data.gov.in API key for live prices (still open in `plan.md`).

### Soybean net return in Vidisha looks too low · Medium
- **Seen:** Hindi chat, Nov 4. Soybean: yield 0.83 t/ha × ₹6,733/q = ₹55,884 gross, but net ₹5,281/ha, so the cost
  share is ~0.91. Rice in the same district: cost share ~0.56.
- **Check:** CACP soybean A2+FL share for Madhya Pradesh in `cost_shares()`, and the DES soybean yield for Vidisha
  (0.83 t/ha is low for MP). If the share is right, the advice is right but needs explaining.
- **Also seen (Nov 6):** Pune, N 90 P 42 K 43 pH 6.5, kharif sowing: top crop rice has cost share 1.47 (CACP
  Maharashtra), so net is −₹40,678/ha while it still ranks first. A share above 1 likely means CACP's Maharashtra rice
  value doesn't match our price × DES yield; worth capping or flagging shares > 1.

## Ranking shown to the farmer

### A lower-ranked crop can earn far more · Medium
- **Seen:** Vidisha, June. Soybean is first (suitability 67%, ₹5,281/ha) and rice third (9%, ₹22,324/ha). Raipur,
  November: rice is first while wheat is more suitable (24% vs 20%), a near-tie broken by net return.
- **Why it matters:** a farmer reads the money column first. The UI says "close calls go to the crop that earns
  more", but not why a crop that earns 4× less is ranked first.
- **Option:** one line on the crop card when a lower crop earns more ("Rice earns more, but few farms like yours grow
  it in kharif"), from the numbers already in the tool result.

### Season warning is vague · Low
- **Seen:** Raipur, rabi. "Little is sown in Raipur in the rabi season; picks rest on other districts." Gemini turned
  it into "little rice is sown", and Qwen into "rice is not commonly grown here".
- **Fix:** say it with the share: "Raipur sows 8% of its kharif area in rabi, so these picks lean on other districts."

## Advisor (agent)

### Gemini 3.5 Flash often unavailable · Medium
- **Seen:** Nov 4. 3.5 Flash answers 503 "high demand" on most calls, so 2.5 Flash answers most messages. 3.8 Flash
  gave 503 twice and was dropped. Free-tier 429 rate limits also happen mid-chat.
- **Impact:** replies take 10–35 s instead of 4–15 s. The model in the paper and the demo may differ from the one
  planned.
- **Options:** paid tier for the conclave, or put 2.5 Flash first. Record which model answered in every test result
  (the `/chat` response has `model`).

### Offline fallback is slow and adds facts · Medium
- **Seen:** first real test, Nov 4. Qwen3-4B-Instruct on the i5 CPU takes ~4 min per answer. In "why not wheat?" it
  added a pH "optimal range" (5.5–7.5) that no tool returned, and said wheat and chickpea are "better suited",
  contradicting the ranking.
- **Impact:** breaks the rule that every number comes from a tool, when Gemini is down. Fine as a last resort, not for
  the demo.
- **Next:** this is what the Nov 9 model-size test measures; run it with the grounding check by script.

### Ollama context is 4,096 tokens · Low
- **Seen:** `ollama ps` shows CONTEXT 4096. The OpenAI-compatible endpoint can't set `num_ctx`, and 5 tool schemas plus
  10 history messages plus tool results can pass 4k in a long chat; Ollama then drops the start, which is the system
  prompt.
- **Fix:** `OLLAMA_CONTEXT_LENGTH=8192` in the Ollama service environment (`sudo systemctl edit ollama`).

### Plain `qwen3:4b` can't be used on this Ollama · Low (worked around)
- The `qwen3:4b` tag is now the thinking-only model, and Fedora's Ollama 0.12.11 ignores `think: false`. We use
  `qwen3:4b-instruct`. Anyone setting up the workshop must pull the instruct tag (README says so).

### Farmer messages go to Google · Low (paper and consent)
- With Gemini first, chat text and farm values leave the device. The paper and the demo should say so; the offline
  model keeps data local.

## Web UI

### Reload shows text only, not the evidence cards · Medium
- **Seen:** Nov 4. The profile saves the chat text, not tool results, so after a reload the crop cards, charts and
  "Why?" buttons are gone.
- **Fix:** save each reply's `tool_calls` (or just the last few) in the profile and render them on restore. Watch file
  size: keep only the last `HISTORY` turns.

### Farm card isn't kept across "New chat" · Low
- "New chat" makes a new farmer id with an empty profile. The card keeps its values on screen, but after a reload in
  the new chat it's empty until the farmer asks something.
- **Fix:** keep the card values in `localStorage` (per device) as well as in the profile.

### Fonts load from Google · Low (conclave)
- Mukta comes from Google Fonts. Offline at the venue the page falls back to system fonts; Devanagari still renders but
  looks different. **Fix if needed:** serve the font files from `project/web/fonts/`.

## Not yet checked

- **Streamlit backup app** after `FEATURE_NAMES` and `reasons()` moved to `recommend.py`: compiles, not opened in a
  browser.
- **Marathi:** planned for the size test; not tried in the app.
- **Notebooks not re-run** after model and data changes: 08 (Kaggle check, old SHC scale), 09 and 10 (now load
  `annual_crop_model.joblib` by name), 04 (old Kaggle model, pre-fix rice numbers). Re-run before the Nov 10 freeze.
- **Two farmers at once:** profiles are plain JSON files with no locking. Fine for the demo; not for real use.

## Data limits (for the paper)

Kept in `research/paper_limitations.md`: arid western Rajasthan (Bikaner), Guntur's 2022 district split, Karnal's
neighbours from the UP cane belt, synthetic Kaggle data, no farm-level link between soil, crop and price, compressed
SHC pH classes, nearest-district soil fill accuracy, DES season labels.
