# The-Opero-Plugins

> Community plugins for [**The Opero**](https://github.com/channallikrishnasai/The-Opero) — drop-in Python modules that extend your assistant without touching its core.

**34 plugins** · standard library first · cross-OS · no telemetry · MIT

---

## Install

1. Download the `.py` file(s) you want from [`plugins/`](plugins/).
2. Copy them into the `plugins/` folder of your Opero install.
3. Restart Opero.

**Helpers come too.** Files starting with `_` are not standalone plugins — they're imported by a sibling plugin and must sit in the same folder (e.g. `_telegram_ops.py` → `telegram_remote.py`).

**Optional extras.** Most plugins need nothing beyond Python. A few name their package in the module docstring and fail with a plain-English `pip install …` message if it's missing (e.g. `openpyxl` for Excel, `mss` for screenshots, OpenCV for the calorie counter).

**State files** some plugins keep live in your Opero profile's `memory/` folder (`habits.json`, `journal.jsonl`, …). They never leave your machine.

---

## The catalog

### 🔌 Remote & automation

| Plugin | What it does | Needs |
|---|---|---|
| [`telegram_remote.py`](plugins/telegram_remote.py) + [`_telegram_ops.py`](plugins/_telegram_ops.py) | Drive Opero from your phone over Telegram — long-poll only (no inbound port), allowlist, pairing window, rate limits, screen/camera/files gated at the desk | `requests` (ships with Opero) |
| [`chat_takeover.py`](plugins/chat_takeover.py) | Watches a chat on screen via vision + Gemini Live and replies in your texting style; stop by voice, failsafe corner, or timeout | Gemini key, `mss`, `pyautogui` |

### 📚 Learning & focus

| Plugin | What it does | Needs |
|---|---|---|
| [`quiz.py`](plugins/quiz.py) | Model-written quizzes on screen; results come back as `[QUIZ_DONE]` for marking. Keeps no store of its own | — |
| [`pomodoro.py`](plugins/pomodoro.py) | Focus/break timer that speaks phase changes and remembers today's totals | — |
| [`document_review.py`](plugins/document_review.py) | Lays out contracts, policies, letters: what signing commits you to, ordered by severity — zero legal knowledge baked in | — |
| [`habit_tracker.py`](plugins/habit_tracker.py) | Daily habits with streaks and best-run math (grace for the morning) | — |

### 💰 Money & lists

| Plugin | What it does | Needs |
|---|---|---|
| [`expense_tracker.py`](plugins/expense_tracker.py) | Spoken expense ledger — day/month totals, categories, undo, settable currency label | — |
| [`excel_writer.py`](plugins/excel_writer.py) | Spoken request → real `.xlsx` with headers, SUM rows, charts | `openpyxl` |
| [`shopping_list.py`](plugins/shopping_list.py) | Persistent shopping list: add, remove, list, clear — deduped case-insensitively | — |
| [`csv_analyzer.py`](plugins/csv_analyzer.py) | Read-only CSV report: shape, headers, numeric stats, samples; sniffs `;` CSVs | — |
| [`bookmark_manager.py`](plugins/bookmark_manager.py) | Save/search links with tags; `javascript:` and other non-http schemes refused | — |

### 🏃 Health & daily life

| Plugin | What it does | Needs |
|---|---|---|
| [`water_reminder.py`](plugins/water_reminder.py) | Spoken hydration nudges + daily ml tracking toward a goal | — |
| [`sleep_log.py`](plugins/sleep_log.py) | Hours per night, 7/30-day averages, unicode sparkline. No medical advice — numbers only | — |
| [`mood_tracker.py`](plugins/mood_tracker.py) | 1–5 mood + note, one entry per day, weekly/monthly averages. Records and reports; never diagnoses | — |
| [`workout_log.py`](plugins/workout_log.py) | Sets/reps/weight and cardio lines, 7-day totals, per-exercise bests | — |
| [`calorie_counter.py`](plugins/calorie_counter.py) | Food through the webcam — animated scan, Gemini nutrition breakdown, spoken summary | OpenCV, Gemini key |
| [`journal.py`](plugins/journal.py) | Spoken diary: write, read by day, full-text search | — |

### 🌍 Math, time & words

| Plugin | What it does | Needs |
|---|---|---|
| [`calculator.py`](plugins/calculator.py) | Exact arithmetic via AST — no `eval()`, only numbers/operators/allowlisted math funcs | — |
| [`unit_converter.py`](plugins/unit_converter.py) | Length, mass, temperature (real affine formulas), volume, speed, data… Model extracts; code computes | — |
| [`date_calculator.py`](plugins/date_calculator.py) | Days between / shift / age / weekday — leap years done by `datetime`, not by vibes | — |
| [`world_clock.py`](plugins/world_clock.py) | IANA zoneinfo clock for the cities you name; DST-correct, offline | `tzdata` on Windows if OS lacks it |
| [`text_stats.py`](plugins/text_stats.py) | Words, chars, sentences, lexical diversity, read/speak time estimates | — |
| [`password_generator.py`](plugins/password_generator.py) | `secrets`-based passwords & passphrases with entropy rating — panel only, never logged | — |

### 🛠 Dev toolbox

| Plugin | What it does | Needs |
|---|---|---|
| [`encoding_toolbox.py`](plugins/encoding_toolbox.py) | base64 / hex / URL / ROT13 encode-decode, SHA-256/1/MD5 hashes | — |
| [`regex_tester.py`](plugins/regex_tester.py) | Run Python `re` against sample text; matches with spans, compile errors explained | — |
| [`json_tool.py`](plugins/json_tool.py) | Validate (line/column errors), pretty, minify, path-get (`users[0].name`) | — |
| [`color_tool.py`](plugins/color_tool.py) | Hex↔RGB↔HSL, harmony palettes, real WCAG contrast ratios | — |
| [`random_picker.py`](plugins/random_picker.py) | Coin, RPG dice (`2d6+3`), fair number, winner pick, shuffle — all from `secrets` | — |

### 📁 Files on disk

| Plugin | What it does | Needs |
|---|---|---|
| [`disk_analyzer.py`](plugins/disk_analyzer.py) | Biggest folders/files + free space. **Measures only — never deletes** | — |
| [`duplicate_finder.py`](plugins/duplicate_finder.py) | Size-then-hash duplicate groups with reclaimable totals. **Read-only** | — |
| [`file_renamer.py`](plugins/file_renamer.py) | Batch rename with **preview-first** flow: plan shown, nothing changes until you say apply. System folders refused | — |
| [`lorem_ipsum.py`](plugins/lorem_ipsum.py) | Placeholder copy — paragraphs/sentences/words, `la`/`en`/`tr` word banks | — |

---

## How a plugin works

Every plugin exposes two things:

```python
PLUGIN = {
    "name": "widget",
    "description": "…what it does, trigger phrases, and what NOT to use it for…",
    "parameters": { "type": "OBJECT", "properties": { … }, "required": [] },
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    return "One sentence for the user."
```

- **`description`** is the tool schema the model reads. Write it in English, list trigger phrases (other languages help routing), and explicitly say what *not* to use it for when tools overlap.
- **`run`** returns one spoken-able sentence. Rich detail goes to the HUD via `player.show_content(title, body)` — always inside `try/except`, because an older UI may not have it.
- **Heavy imports go inside functions.** Plugin discovery imports every file on every launch; `cv2`/`numpy`/`requests` at module scope charges every boot for a feature nobody opened.
- **State** belongs in `memory/<name>.json(l)` — one rolling `remember()` note for long-term memory, never a private store that fragments the profile.
- **`_*.py` files** are skipped by the loader. Use them for helpers a plugin needs at import time without making them tools.

### House rules (the ones the existing plugins take seriously)

1. **No natural-language keywords in dispatch paths** — the model fills enum values; slash tokens are buttons, not words. Works in every language for free.
2. **Anything irreversible gets a preview or a second press.** Renames plan first; the remote's `/undo` must be sent twice.
3. **Destructive-by-default is a bug.** Measure, show, let the human decide.
4. **Never invent what you can't know** — no baked-in exchange rates, no per-country legal tables, no medical advice. Say what the data says; defer the judgement.
5. **Errors are sentences, not tracebacks** — the bridge sends your string to a chat that asked in plain English (or Turkish, or anything).

---

## Verifying an install

```bash
# every plugin should byte-compile
python -m py_compile plugins/*.py

# spot-check one
python -c "import sys; sys.path.insert(0,'plugins'); import calculator as c; print(c.run({'expression':'2+2'}))"
```

---

## Contributing

PRs welcome — one plugin per PR, with:

- the module docstring pattern above (*why this file exists*, not just what it does)
- `PLUGIN` + `run()` only (no startup hooks — plugins have no launch lifecycle)
- state under `memory/` if it needs any; nothing outside the profile
- a row added to the catalog table in this README
- stdlib preferred; third-party deps must fail with a friendly `pip install` message

---

## Security posture

Plugins run with full local privileges — treat them like any other code you install. The conventions here:

- pairing/allowlist patterns over "trust the network"
- tokens and codes scrubbed before any log line
- gated features default **off** (screenshot, camera, auto-start)
- read-only analysis tools stay read-only (`disk_analyzer`, `duplicate_finder`, `csv_analyzer`)

---

**[The Opero](https://github.com/channallikrishnasai/The-Opero)** · [Report a bug](https://github.com/channallikrishnasai/The-Opero-Plugins/issues) · [MIT](LICENSE)
