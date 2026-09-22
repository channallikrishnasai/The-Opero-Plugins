"""
JARVIS plugin — Mood tracker.

"I'm feeling anxious today", "bugün modum iyi", "how have I been feeling
this week" — one number and an optional line, kept in memory/moods.json,
rolled up into a short trend the assistant can refer to later.

WHY A NUMBER AND A NOTE
-----------------------
A 1–5 scale is coarse enough to log in two seconds — which is the only
reason logs get kept — and fine enough that a week of 2s after a week of 4s
is visible without charting software. The note is the user's own words;
this file never interprets them, never diagnoses, and never offers
advice. It records and reports.

A LINE THE PLUGIN WILL NOT CROSS
--------------------------------
Mood data touches the fragile part of a person's day. Nothing here leaves
the machine, nothing is pushed anywhere, and the plugin's replies stay
descriptive: averages, counts, the last entries. If a note ever reads like
crisis language, that is for the human in the conversation — not a
detector bolted onto a JSON file — to notice.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "moods.json"

PLUGIN = {
    "name": "mood_tracker",
    "description": (
        "Logs a daily mood score (1–5) with an optional short note, and "
        "reports recent trends. Use for: 'I feel great today', 'modum "
        "berbat', 'log mood 2 with a headache', 'how have I been this "
        "week', 'what was my mood yesterday'. You decide the 1–5 number "
        "from what they said (1 = very low, 5 = very well) and pass it as "
        "`score`; put their own words in `note`. This only records and "
        "reports — it gives NO psychological advice and makes no "
        "diagnoses; a real professional is the answer to anything beyond "
        "plain logging. NOT for medical symptoms tracking (journal them "
        "instead) or sleep (sleep_log)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["log", "status", "recent"],
                "description": "'log' (default) records today's mood; "
                               "'status' = averages for 7/30 days; "
                               "'recent' = last 14 entries.",
            },
            "score": {
                "type": "INTEGER",
                "description": "Mood 1 (very low) to 5 (very well), as you "
                               "judged from what the user said.",
            },
            "note": {
                "type": "STRING",
                "description": "Optional short note in the user's own words, "
                               "max a sentence.",
            },
        },
        "required": [],
    },
}

_MAX = 800


def _load() -> list[dict]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict)]
    except (OSError, ValueError):
        pass
    return []


def _save(rows: list[dict]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(rows[-_MAX:], ensure_ascii=False, indent=1),
                              encoding="utf-8")
    except OSError:
        pass


def _bar(score: int) -> str:
    s = max(1, min(5, int(score)))
    return ("😞", "😕", "😐", "🙂", "😄")[s - 1] + " " + "●" * s + "○" * (5 - s)


def _avg(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return sum(int(r.get("score") or 0) for r in rows) / len(rows)


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "log").strip().lower()
        rows = _load()
        today = date.today().isoformat()

        if action in ("status", "stats"):
            d7 = [r for r in rows if r.get("date", "") >=
                  (date.today() - timedelta(days=6)).isoformat()]
            d30 = [r for r in rows if r.get("date", "") >=
                   (date.today() - timedelta(days=29)).isoformat()]
            a7, a30 = _avg(d7), _avg(d30)
            if not rows:
                return "No moods logged yet — say how you feel and I'll start the log."
            line = (f"Last 7 days: {a7:.1f}/5 across {len(d7)} log(s). "
                    f"Last 30 days: {a30:.1f}/5 across {len(d30)} log(s).")
            body = f"7-day avg   {a7:.1f}/5  {_bar(round(a7))}\n" \
                   f"30-day avg  {a30:.1f}/5  {_bar(round(a30))}\n" \
                   f"total logs  {len(rows)}"
            _show("🧠 MOOD TREND", body)
            return line

        if action in ("recent", "list"):
            if not rows:
                return "No moods logged yet."
            show = rows[-14:]
            body = "\n".join(
                f"{r.get('date', '?')}  {_bar(int(r.get('score') or 0))}  "
                f"{r.get('note') or ''}".rstrip() for r in reversed(show))
            _show("🧠 RECENT MOODS", body)
            last = show[-1]
            return (f"{len(show)} recent on screen. Last: {last.get('date')} — "
                    f"{last.get('score')}/5"
                    + (f", “{last['note']}”" if last.get("note") else "") + ".")

        # -------- LOG (default) --------
        try:
            score = int(parameters.get("score"))
        except (TypeError, ValueError):
            return "Rate it 1 to 5 and I'll log it (1 very low, 5 very well)."
        if score < 1 or score > 5:
            return "Keep the mood between 1 and 5."
        note = str(parameters.get("note") or "").strip()[:300]

        # One entry per day: a second log the same day replaces the first,
        # so an evening verdict can correct the morning one.
        rows = [r for r in rows if r.get("date") != today]
        rows.append({"date": today, "score": score, "note": note})
        rows.sort(key=lambda r: r.get("date", ""))
        _save(rows)

        week = [r for r in rows if r.get("date", "") >=
                (date.today() - timedelta(days=6)).isoformat()]
        a = _avg(week)
        return (f"Mood {score}/5 logged for today."
                + (f" “{note}”" if note else "")
                + (f" 7-day average is now {a:.1f}." if a else ""))
    except Exception as e:
        return "Sir, the mood tracker failed: " + str(e)
