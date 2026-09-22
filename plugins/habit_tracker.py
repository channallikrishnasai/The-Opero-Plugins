"""
JARVIS plugin — Habit tracker.

"mark today's workout done", "how's my reading streak", "start a habit
called meditate" — streaks and checkmarks for the small things a person
is trying to do daily, remembered across sessions in memory/habits.json.

WHY STREAKS LIVE IN A FILE
--------------------------
Motivation is a number: the chain of days matters more than any single
one, and a chain you can't see is a chain you break. Dates are stored as
ISO strings per habit; streak math walks backwards from today (or
yesterday, if today isn't marked yet — so an evening check doesn't read
as "chain broken" at 9am).

WHAT COUNTS AS DONE IS THE USER'S WORD
--------------------------------------
No minimums, no verification, no guilt beyond the number itself. A
personal assistant that audits whether you "really" meditated has
overstepped; it records what it's told and shows the math.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "habits.json"

PLUGIN = {
    "name": "habit_tracker",
    "description": (
        "Tracks daily habits with streaks: create a habit, mark it done for "
        "today, list all habits with current and best streaks, or remove "
        "one. Use for: 'I meditated today', 'mark workout done', 'start a "
        "reading habit', 'what's my streak on flossing', 'list my habits', "
        "'delete the smoking habit'. Pass habit names in the user's own "
        "language. NOT for one-off reminders, NOT for water intake "
        "(water_reminder), NOT for focus sessions (pomodoro), NOT for "
        "generic todos (shopping_list is goods; journal is events)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["add", "done", "list", "delete", "undo"],
                "description": "'done' (default when habit given) marks today; "
                               "'add' creates an empty habit; 'list' shows "
                               "everything; 'delete' removes a habit; 'undo' "
                               "unmarks today if marked by mistake.",
            },
            "habit": {
                "type": "STRING",
                "description": "Habit name in the user's own words — "
                               "'meditate', 'spor', 'read 20 pages'.",
            },
        },
        "required": [],
    },
}

_MAX_HABITS = 60
_MAX_DATES = 400        # per habit — a year plus slack, trimmed oldest-first


def _load() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def _save(data: dict) -> None:
    try:
        for h in data.values():
            if isinstance(h, dict) and isinstance(h.get("dates"), list):
                h["dates"] = sorted(set(h["dates"]))[-_MAX_DATES:]
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    except OSError:
        pass


def _key(name: str) -> str:
    return " ".join(str(name).strip().casefold().split())


def _find(data: dict, name: str):
    k = _key(name)
    if k in data:
        return k, data[k]
    for key in data:
        if key.startswith(k) or k.startswith(key):
            return key, data[key]
    return None, None


def _streak(dates: list[str]) -> int:
    """Consecutive days ending today, or ending yesterday (grace for the
    morning before today is marked)."""
    if not dates:
        return 0
    have = set(dates)
    day = date.today()
    if day.isoformat() not in have:
        day -= timedelta(days=1)
        if day.isoformat() not in have:
            return 0
    n = 0
    while day.isoformat() in have:
        n += 1
        day -= timedelta(days=1)
    return n


def _best(dates: list[str]) -> int:
    if not dates:
        return 0
    days = sorted(date.fromisoformat(d) for d in set(dates))
    best = run = 1
    for a, b in zip(days, days[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        best = max(best, run)
    return best


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(body: str) -> None:
        if player:
            try:
                player.show_content("✅ HABITS", body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "").strip().lower()
        habit = str(parameters.get("habit") or "").strip()
        data = _load()
        today = date.today().isoformat()

        if not action:
            action = "done" if habit else "list"

        if action == "list":
            if not data:
                return ("No habits yet. Say 'start a habit called …' and I'll "
                        "keep the streak.")
            lines = []
            for name, h in sorted(data.items(),
                                  key=lambda kv: -_streak(kv[1].get("dates", []))):
                dates = h.get("dates", [])
                st, bs = _streak(dates), _best(dates)
                mark = "🟢" if today in dates else ("🟡" if st else "⚪")
                lines.append(f"{mark} {name}  ·  streak {st}d (best {bs}d)")
            _show("\n".join(lines))
            top = max(data.items(), key=lambda kv: _streak(kv[1].get("dates", [])))
            return (f"{len(data)} habit(s). Strongest: '{top[0]}' at "
                    f"{_streak(top[1].get('dates', []))} day(s). Full list on screen.")

        if not habit:
            return "Which habit?"

        key, row = _find(data, habit)

        if action == "add":
            if key:
                return f"'{key}' already exists — say 'done' when you've done it."
            if len(data) >= _MAX_HABITS:
                return f"That's {_MAX_HABITS} habits — delete one first."
            data[_key(habit)] = {"created": today, "dates": []}
            _save(data)
            return (f"Habit '{habit.strip()}' started. Say 'I did {habit.strip()}' "
                    f"or action=done each day to build the streak.")

        if action == "delete":
            if not key:
                return f"No habit called '{habit}'."
            del data[key]
            _save(data)
            return f"Habit '{key}' deleted."

        if not row:
            return (f"No habit called '{habit}' yet — say 'start a habit "
                    f"called {habit}' first.")

        dates = row.setdefault("dates", [])

        if action == "undo":
            if today not in dates:
                return f"'{key}' isn't marked for today."
            dates.remove(today)
            _save(data)
            return f"Unmarked '{key}' for today. Streak is now {_streak(dates)}."

        # done / mark / log
        if today in dates:
            st = _streak(dates)
            return f"'{key}' is already marked for today — streak {st} day(s)."
        dates.append(today)
        _save(data)
        st, bs = _streak(dates), _best(dates)
        if st >= 2 and st >= bs:
            return f"'{key}' done. New best streak: {st} days! 🎉"
        return f"'{key}' done for today. Streak: {st} day(s) (best {bs})."
    except Exception as e:
        return "Sir, the habit tracker failed: " + str(e)
