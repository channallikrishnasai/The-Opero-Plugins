"""
JARVIS plugin — Workout log.

"bench 80 for 3 sets of 5", "log 5km run in 25 minutes", "spor kaydı:
squats 100kg x 5" — sets, reps and cardio entries in memory/workouts.json,
so progressive overload has a paper trail.

WHY NOT A SPREADSHEET
---------------------
You don't open Excel between sets. The log has to accept one spoken line
and get out of the way; the weekly read ("what did I bench two weeks ago")
comes from the same file. excel_export remains available when the user
actually wants a workbook of months of data.

WHAT IT TRACKS
--------------
Strength: exercise, weight, sets × reps. Cardio: exercise, distance
and/or duration. Both dated; one entry per line, append-only (undo pops
the last). Stats show totals for the last 7 days and per-exercise bests —
the two numbers that tell you whether the work is compounding.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "workouts.json"

PLUGIN = {
    "name": "workout_log",
    "description": (
        "Logs gym/cardio sessions and reports totals and personal bests. "
        "Use for: 'bench press 80 kg for 3 sets of 5', 'log squats 100 by "
        "5', 'I ran 5 km in 25 minutes', 'spor kaydı', 'what did I lift "
        "last week', 'stats for my workouts', 'undo my last set'. Pass "
        "exercise name, optional weight_kg, optional sets/reps, optional "
        "distance_km and duration_min. NOT for calories or body metrics "
        "(journal them), NOT for timers during the session (pomodoro / "
        "reminder), NOT for coaching advice — this records what the user "
        "says and reads it back."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["log", "stats", "recent", "undo"],
                "description": "'log' (default) adds an entry; 'stats' = "
                               "7-day totals + bests; 'recent' = last 15 "
                               "entries; 'undo' removes the most recent.",
            },
            "exercise": {
                "type": "STRING",
                "description": "Exercise name — 'bench press', 'koşu', 'squats'.",
            },
            "weight_kg": {"type": "NUMBER", "description": "Load in kg (strength)."},
            "sets": {"type": "INTEGER", "description": "Number of sets."},
            "reps": {"type": "INTEGER", "description": "Reps per set (or total, "
                                                        "whichever the user said)."},
            "distance_km": {"type": "NUMBER", "description": "Distance in km (cardio)."},
            "duration_min": {"type": "NUMBER", "description": "Duration in minutes."},
            "note": {"type": "STRING", "description": "Optional short note."},
        },
        "required": [],
    },
}

_MAX = 3000


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


def _fmt_entry(e: dict) -> str:
    bits = [str(e.get("exercise") or "?")]
    if e.get("weight_kg") is not None:
        bits.append(f"{e['weight_kg']:g} kg")
    if e.get("sets") and e.get("reps"):
        bits.append(f"{e['sets']}×{e['reps']}")
    elif e.get("reps"):
        bits.append(f"{e['reps']} reps")
    if e.get("distance_km"):
        bits.append(f"{e['distance_km']:g} km")
    if e.get("duration_min"):
        bits.append(f"{e['duration_min']:g} min")
    if e.get("note"):
        bits.append(f"({e['note']})")
    return " · ".join(bits)


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "").strip().lower()
        rows = _load()

        if not action:
            action = "log" if parameters.get("exercise") else "stats"

        if action == "undo":
            if not rows:
                return "Nothing to undo — the workout log is empty."
            last = rows.pop()
            _save(rows)
            return f"Removed the last entry: {_fmt_entry(last)}."

        if action in ("recent", "list"):
            if not rows:
                return "No workouts logged yet."
            show = rows[-15:]
            body = "\n".join(f"{e.get('date', '?')}  {_fmt_entry(e)}"
                             for e in reversed(show))
            _show("🏋️ WORKOUTS", body)
            return f"Last {len(show)} entries on screen. Most recent: {_fmt_entry(show[-1])}."

        if action in ("stats", "status"):
            if not rows:
                return "No workouts logged yet — tell me a lift or a run."
            since = (date.today() - timedelta(days=6)).isoformat()
            week = [e for e in rows if e.get("date", "") >= since]

            # Personal bests: heaviest load per exercise among logged lifts.
            bests: dict[str, float] = {}
            for e in rows:
                w = e.get("weight_kg")
                ex = str(e.get("exercise") or "").casefold()
                if w is not None and (ex not in bests or w > bests[ex]):
                    bests[ex] = float(w)

            km = sum(float(e.get("distance_km") or 0) for e in week)
            mins = sum(float(e.get("duration_min") or 0) for e in week)
            lines = [f"Last 7 days: {len(week)} entries",
                     f"Distance {km:g} km · Time {mins:g} min", ""]
            if bests:
                lines.append("BEST LOADS")
                for ex, w in sorted(bests.items(), key=lambda kv: -kv[1])[:8]:
                    lines.append(f"  {ex:<20} {w:g} kg")
            _show("🏋️ WORKOUT STATS", "\n".join(lines))
            top = (sorted(bests.items(), key=lambda kv: -kv[1])[:3]
                   if bests else [])
            top_s = "; ".join(f"{ex} {w:g}kg" for ex, w in top) or "no lifts yet"
            return (f"{len(week)} entries in the last 7 days"
                    + (f", {km:g} km and {mins:g} min of cardio" if (km or mins) else "")
                    + f". Best lifts: {top_s}. Full stats on screen.")

        # -------- LOG --------
        exercise = str(parameters.get("exercise") or "").strip()[:80]
        if not exercise:
            return "Which exercise? Give me the name and the numbers."

        entry: dict = {"date": date.today().isoformat(),
                       "ts": datetime.now().isoformat(timespec="seconds"),
                       "exercise": exercise}
        for field in ("weight_kg", "sets", "reps", "distance_km", "duration_min"):
            raw = parameters.get(field)
            if raw is not None and str(raw).strip() != "":
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    continue
                entry[field] = int(val) if field in ("sets", "reps") else val
        note = str(parameters.get("note") or "").strip()[:200]
        if note:
            entry["note"] = note

        if len(entry) == 2:      # only date/ts/exercise — nothing measured
            return (f"Logged '{exercise}' with no numbers — next time add "
                    f"weight, sets/reps or distance so stats can work.")

        rows.append(entry)
        _save(rows)
        return f"Logged: {_fmt_entry(entry)}. {len(rows)} total entries."
    except Exception as e:
        return "Sir, the workout log failed: " + str(e)
