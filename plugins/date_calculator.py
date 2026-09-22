"""
JARVIS plugin — Date & time arithmetic.

"how many days until my birthday", "what date is 90 days from now",
"12 March 2024 was what day of the week", "how old am I if I was born
2000-06-14" — calendar math, which language models get subtly wrong.

WHY HERE
--------
Leap years, month lengths and "inclusive or not" are exactly the kind of
detail a fluent model skips. datetime does not. This plugin parses the
dates the model extracted from the user's sentence, runs the real calendar
math, and hands back one line.

WHAT IT ANSWERS
---------------
• days between two dates (and weeks/months as a rough secondary)
• a date shifted forward or backward by N days
• age from a birthdate
• the weekday of any date
• the countdown to a future date

No timezone games: dates are civil dates, the ones people write on
paper. Instants and world clocks are world_clock's job.

FOR EVERYONE: standard library only, no keys, no setup. Same everywhere.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

PLUGIN = {
    "name": "date_calculator",
    "description": (
        "Calendar math between civil dates: days remaining until a date, days "
        "between two dates, a date plus or minus N days, age from a birthdate, "
        "and the weekday of any date. Use for: 'how many days until Christmas', "
        "'what is 90 days from today', '12 March 2024 was what day', 'how old "
        "am I, born 2000-06-14', 'days since 1 January 2024', 'kaç gün kaldı'. "
        "Pass ISO dates (YYYY-MM-DD) that you extracted from the request, "
        "defaulting missing ones to today. NOT for meeting scheduling or "
        "reminders (that is the reminder tool), NOT for world times "
        "(world_clock), NOT for duration arithmetic on hours (unit_converter "
        "time)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["diff", "add", "age", "weekday", "countdown"],
                "description": "'diff' = days between date1 and date2; 'add' "
                               "= date1 shifted by `days`; 'age' = age at "
                               "date1 as of today (pass the birthdate as "
                               "date1); 'weekday' = day of week of date1; "
                               "'countdown' = days from today until date1.",
            },
            "date1": {
                "type": "STRING",
                "description": "Primary date, ISO YYYY-MM-DD. Default today "
                               "where sensible.",
            },
            "date2": {
                "type": "STRING",
                "description": "Second date for 'diff', ISO YYYY-MM-DD. "
                               "Default today.",
            },
            "days": {
                "type": "INTEGER",
                "description": "For 'add': number of days to shift (may be "
                               "negative for backwards).",
            },
        },
        "required": ["action"],
    },
}

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday")


def _parse(raw, default: date | None = None) -> date:
    raw = str(raw or "").strip()
    if not raw:
        if default is not None:
            return default
        raise ValueError("a date is required")
    raw = raw.replace("/", "-")
    # The model sometimes echoes '12 March 2024'; accept a few loose forms
    # so a failed parse isn't the user's problem.
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        raise ValueError(f"I couldn't read '{raw}' as a date — use YYYY-MM-DD.")


def _fmt(d: date) -> str:
    return f"{d.strftime('%A')} {d.isoformat()}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        action = str(parameters.get("action") or "diff").strip().lower()
        today = date.today()

        try:
            d1 = _parse(parameters.get("date1"), today)
        except ValueError as e:
            return str(e)

        if action == "weekday":
            line = f"{d1.isoformat()} is a {d1.strftime('%A')}."
            return line

        if action == "age":
            if d1 > today:
                return "That birthdate is in the future — check the year."
            years = today.year - d1.year - ((today.month, today.day) < (d1.month, d1.day))
            days = (today - d1).days
            line = (f"Born {d1.isoformat()}: {years} years old "
                    f"({days:,} days — {days // 7:,} weeks).")
            return line

        if action == "add":
            try:
                n = int(parameters.get("days"))
            except (TypeError, ValueError):
                return "Give me the number of days to add or subtract."
            out = d1 + timedelta(days=n)
            direction = "after" if n >= 0 else "before"
            return f"{abs(n)} day(s) {direction} {d1.isoformat()} → {_fmt(out)}."

        if action in ("diff", "countdown"):
            d2 = _parse(parameters.get("date2"), today)
            if action == "countdown":
                d1, d2 = today, d1
            delta = d2 - d1
            n = abs(delta.days)
            sign = ("left until" if action == "countdown" else
                    ("from" if delta.days >= 0 else "before"))
            weeks, rem = divmod(n, 7)
            extra = f" ({weeks} weeks {rem} days)" if weeks else ""
            if action == "countdown":
                if n == 0:
                    return f"{d2.isoformat()} is today."
                return (f"{n} day(s) {sign} {d2.isoformat()}"
                        f" ({d2.strftime('%A')}){extra}.")
            rel = "→" if delta.days >= 0 else "←"
            return (f"{d1.isoformat()} {rel} {d2.isoformat()}: {n} day(s) "
                    f"apart{extra}. {'Weekdays align.' if d1.weekday() == d2.weekday() else ''}".strip())

        return f"I don't have a '{action}' for dates. Try diff, add, age, weekday or countdown."
    except Exception as e:
        return "Sir, the date calculator failed: " + str(e)
