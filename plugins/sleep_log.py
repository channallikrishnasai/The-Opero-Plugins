"""
JARVIS plugin — Sleep log.

"I slept about 6 hours", "dün gece 5 saat uyudum", "how's my sleep been
this week" — a running tally of hours slept, in memory/sleep.json.

WHY SLEEP AND NOT JUST MOOD
---------------------------
Sleep is the input most correlated with how a day goes, and the one people
misremember worst ("I get enough sleep" said after a 5-hour week). A
number written down the morning after beats a feeling about the month.

WHAT IT REPORTS
---------------
Last night, 7-day and 30-day averages, and a tiny bar strip so a bad week
is shapeable at a glance. One entry per date — logging again the same
morning overwrites, because the corrected number is the true one.

IT OFFERS NO MEDICAL OPINION
-----------------------------
Averages and counts only. Whether six hours is a problem is between the
user and someone qualified to say; this file is a notebook.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "sleep.json"

PLUGIN = {
    "name": "sleep_log",
    "description": (
        "Logs hours slept per night and reports averages (last night, 7 and "
        "30 days). Use for: 'I got 7 hours of sleep', 'I only slept 5 hours', "
        "'dün kaç saat uyudum', 'how has my sleep been this week', 'log "
        "sleep 6.5'. The date defaults to the night that just passed (if "
        "it's morning, count last night; pass `day` as YYYY-MM-DD to "
        "override). NOT for alarms or bedtime reminders (reminder tool), "
        "NOT for mood (mood_tracker), and this gives NO medical advice — "
        "only numbers."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["log", "status", "recent"],
                "description": "'log' (default) records hours; 'status' = "
                               "averages; 'recent' = last 14 nights.",
            },
            "hours": {
                "type": "NUMBER",
                "description": "Hours slept (e.g. 6.5). For 'log' only.",
            },
            "day": {
                "type": "STRING",
                "description": "Optional night's date YYYY-MM-DD (the morning "
                               "you woke). Default: today.",
            },
        },
        "required": [],
    },
}

_MAX = 800


def _load() -> dict[str, float]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: float(v) for k, v in data.items()
                    if isinstance(v, (int, float))}
    except (OSError, ValueError):
        pass
    return {}


def _save(data: dict[str, float]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        keys = sorted(data)[-_MAX:]
        STATE_FILE.write_text(
            json.dumps({k: data[k] for k in keys}, ensure_ascii=False, indent=1),
            encoding="utf-8")
    except OSError:
        pass


def _avg(data: dict[str, float], days: int) -> tuple[float | None, int]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    vals = [v for k, v in data.items() if k >= since]
    if not vals:
        return None, 0
    return sum(vals) / len(vals), len(vals)


def _strip(data: dict[str, float], n: int = 14) -> str:
    """A language-neutral sparkline of the last n nights."""
    keys = sorted(data)[-n:]
    blocks = "▁▂▃▄▅▆▇█"
    out = []
    for k in keys:
        h = max(0.0, min(12.0, data[k]))
        out.append(blocks[int(h / 12 * (len(blocks) - 1))])
    return "".join(out)


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "log").strip().lower()
        data = _load()
        today = date.today().isoformat()

        if action in ("status", "stats"):
            if not data:
                return "No sleep logged yet — say 'I got 7 hours' and I'll start."
            last_key = max(data)
            a7, n7 = _avg(data, 7)
            a30, n30 = _avg(data, 30)
            body = (f"Last: {data[last_key]:g} h ({last_key})\n"
                    f"7-day avg   {a7:.1f} h  ({n7} nights)\n"
                    f"30-day avg  {a30:.1f} h  ({n30} nights)\n"
                    f"14 nights   {_strip(data)}")
            _show("😴 SLEEP", body)
            return (f"Last logged {data[last_key]:g} hours on {last_key}. "
                    f"7-day average {a7:.1f} h, 30-day {a30:.1f} h — on screen.")

        if action in ("recent", "list"):
            if not data:
                return "No sleep logged yet."
            keys = sorted(data)[-14:]
            body = "\n".join(f"{k}  {data[k]:>4g} h  {_strip({k: data[k]}, 1)}".rstrip()
                             for k in reversed(keys))
            _show("😴 RECENT SLEEP", body)
            return (f"{len(keys)} nights on screen, newest first. "
                    f"Most recent: {keys[-1]}, {data[keys[-1]]:g} hours.")

        # -------- LOG (default) --------
        try:
            hours = float(parameters.get("hours"))
        except (TypeError, ValueError):
            return "How many hours did you sleep? Give me the number."
        if hours <= 0 or hours > 24:
            return "Hours should be between 0 and 24 — check the number."
        hours = round(hours, 1)
        day = str(parameters.get("day") or "").strip() or today
        try:
            day = date.fromisoformat(day[:10]).isoformat()
        except ValueError:
            return "Give the night's date as YYYY-MM-DD, or leave it empty."

        data[day] = hours
        _save(data)
        a7, n7 = _avg(data, 7)
        msg = f"Logged {hours:g} hours for {day}."
        if n7:
            msg += f" 7-day average: {a7:.1f} h across {n7} night(s)."
        return msg
    except Exception as e:
        return "Sir, the sleep log failed: " + str(e)
