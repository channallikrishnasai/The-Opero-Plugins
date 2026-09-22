"""
JARVIS plugin — Expense tracker.

"250 rs lunch today", "kaç harcadım bu ay", "log 40 for the taxi, food
category" — a spoken expense diary that adds up the day and the month and
answers "how much have I spent" without opening an app.

WHY ITS OWN FILE AND NOT A SPREADSHEET
---------------------------------------
excel_writer builds a beautiful .xlsx and throws the data away afterwards —
it is a one-shot renderer. This is the running ledger underneath: cheap to
append to from speech, always current, and exportable to that plugin later
when the user actually wants a workbook. Two tools, one job each.

WHERE THE MONEY LIVES
---------------------
memory/expenses.json, same folder as the water and pomodoro state, because
it is profile data that must survive updates. Entries are dated on write;
the month view is derived from the dates rather than stored separately, so
a bug in one cannot disagree with the other.

NO CURRENCY ASSUMPTION
----------------------
Amounts are plain numbers with an optional currency label the user can set
once. The plugin never guesses a symbol — "250" in one country and another
are different lives, and printing the wrong one is worse than printing none.

WHAT IT DELIBERATELY SKIPS
--------------------------
Budgets, forecasts, investment tracking — each is a financial opinion this
file is not in a position to hold. It records what was said and adds it up.

FOR EVERYONE: standard library only, no keys, no setup. Same on Windows,
macOS and Linux.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "expenses.json"

PLUGIN = {
    "name": "expense_tracker",
    "description": (
        "Logs expenses spoken by the user and totals them by day and month. "
        "Use for: 'log 250 for lunch', 'I spent 40 on taxi', 'bugün ne "
        "harcadım', 'how much have I spent this month', 'show my recent "
        "expenses', 'set my currency to euros', 'undo my last expense'. "
        "Pass the amount as a number, an optional category and a short note. "
        "Do NOT use it for budgeting advice, investment or bank balances "
        "(no account access — this is a notepad, not a bank), and do NOT "
        "use it for unit conversions or totals that aren't about spending."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["log", "status", "recent", "undo", "currency"],
                "description": "'log' (default) records a new expense; "
                               "'status' totals today and this month; "
                               "'recent' lists the last entries; 'undo' "
                               "removes the most recent one; 'currency' sets "
                               "the label shown with amounts.",
            },
            "amount": {
                "type": "NUMBER",
                "description": "For 'log': how much was spent (positive number).",
            },
            "category": {
                "type": "STRING",
                "description": "For 'log': short category in the user's own "
                               "words — 'food', 'transport', 'yemek'… Optional.",
            },
            "note": {
                "type": "STRING",
                "description": "For 'log': a few words about what it was. "
                               "Optional.",
            },
            "currency": {
                "type": "STRING",
                "description": "For 'currency': the label to show, e.g. '€', "
                               "'USD', '₺'. Stored until changed.",
            },
            "month": {
                "type": "STRING",
                "description": "For 'status'/'recent': YYYY-MM to view a "
                               "different month (default: current).",
            },
        },
        "required": [],
    },
}

_MAX_ENTRIES = 2000        # oldest are dropped rather than letting the file grow forever
_MAX_TEXT = 160


def _load() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("entries", [])
            data.setdefault("currency", "")
            return data
    except (OSError, ValueError):
        pass
    return {"entries": [], "currency": ""}


def _save(data: dict) -> None:
    try:
        # Cap on write: a year of coffee is a few hundred lines, and a file
        # that grew without bound would eventually fail to load at all.
        data["entries"] = data["entries"][-_MAX_ENTRIES:]
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    except OSError:
        pass


def _fmt(amount: float, currency: str) -> str:
    text = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return f"{text} {currency}".strip()


def _month_of(entry: dict) -> str:
    return str(entry.get("date") or "")[:7]


def _remember(data: dict) -> None:
    """One rolling note so a later conversation knows roughly where the month stands."""
    try:
        from memory.memory_manager import remember
        today = date.today().isoformat()
        now = _month_of({"date": today})
        month_total = sum(float(e.get("amount") or 0) for e in data["entries"]
                          if _month_of(e) == now)
        cur = data.get("currency") or ""
        remember("expenses_month",
                 f"Spent {_fmt(month_total, cur)} so far in {now} "
                 f"({sum(1 for e in data['entries'] if _month_of(e) == now)} "
                 f"logged expenses).", "notes")
    except Exception:
        pass


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
        cur = data.get("currency") or ""

        # -------- CURRENCY --------
        if action in ("currency", "set_currency"):
            label = str(parameters.get("currency") or "").strip()[:12]
            if not label:
                return ("No currency label given — say something like 'euros', "
                        "'USD' or '₺' and I'll show it with every amount.")
            data["currency"] = label
            _save(data)
            return f"Currency label set to {label}. Totals will show it from now on."

        # -------- UNDO --------
        if action == "undo":
            if not data["entries"]:
                return "There are no expenses to undo."
            last = data["entries"].pop()
            _save(data)
            _remember(data)
            return (f"Removed the last expense: {_fmt(float(last.get('amount') or 0), cur)} "
                    f"for {last.get('note') or last.get('category') or 'it'} "
                    f"on {last.get('date')}.")

        # -------- STATUS --------
        if action in ("status", "stats", "total"):
            month = str(parameters.get("month") or "").strip() or date.today().strftime("%Y-%m")
            today = date.today().isoformat()
            day_total = sum(float(e.get("amount") or 0) for e in data["entries"]
                            if e.get("date") == today)
            month_entries = [e for e in data["entries"] if _month_of(e) == month]
            month_total = sum(float(e.get("amount") or 0) for e in month_entries)

            by_cat: dict[str, float] = {}
            for e in month_entries:
                cat = str(e.get("category") or "other") or "other"
                by_cat[cat] = by_cat.get(cat, 0) + float(e.get("amount") or 0)
            top = sorted(by_cat.items(), key=lambda kv: -kv[1])[:6]

            lines = [f"{month} — {_fmt(month_total, cur)}",
                     f"Today — {_fmt(day_total, cur)}",
                     f"{len(month_entries)} entries", ""]
            if top:
                lines.append("BY CATEGORY")
                for cat, amt in top:
                    lines.append(f"  {cat:<14} {_fmt(amt, cur)}")

            if not month_entries and not day_total:
                return f"Nothing logged for {month} yet."
            _show("💰 EXPENSES", "\n".join(lines))
            cur_line = cur or "(no currency set)"
            return (f"Today: {_fmt(day_total, cur_line)}. {month} total: "
                    f"{_fmt(month_total, cur_line)} across {len(month_entries)} "
                    f"entries — breakdown on screen.")

        # -------- RECENT --------
        if action in ("recent", "list", "show"):
            month = str(parameters.get("month") or "").strip()
            entries = data["entries"]
            if month:
                entries = [e for e in entries if _month_of(e) == month]
            if not entries:
                return "No expenses logged yet."
            show = entries[-12:]
            body = "\n".join(
                f"{e.get('date', '?')}  {_fmt(float(e.get('amount') or 0), cur):>12}"
                f"  {e.get('category') or ''}  {e.get('note') or ''}".rstrip()
                for e in reversed(show))
            _show("💰 RECENT EXPENSES", body)
            newest = show[-1]
            return (f"{len(show)} most recent on screen, newest first: "
                    f"{_fmt(float(newest.get('amount') or 0), cur)} for "
                    f"{newest.get('note') or newest.get('category') or 'it'} "
                    f"on {newest.get('date')}.")

        # -------- LOG (default) --------
        try:
            amount = float(parameters.get("amount"))
        except (TypeError, ValueError):
            return "How much was it? Give me the number and I'll log it."
        if amount <= 0:
            return "The amount has to be a positive number."
        amount = round(amount, 2)

        category = str(parameters.get("category") or "").strip()[:_MAX_TEXT]
        note = str(parameters.get("note") or "").strip()[:_MAX_TEXT]
        entry = {"date": date.today().isoformat(),
                 "ts": datetime.now().isoformat(timespec="seconds"),
                 "amount": amount,
                 "category": category,
                 "note": note}
        data["entries"].append(entry)
        _save(data)
        _remember(data)

        today_total = sum(float(e.get("amount") or 0) for e in data["entries"]
                          if e.get("date") == entry["date"])
        month = entry["date"][:7]
        month_total = sum(float(e.get("amount") or 0) for e in data["entries"]
                          if _month_of(e) == month)
        cur_line = cur or ""
        bits = [f"Logged {_fmt(amount, cur_line)}" +
                (f" for {note or category}" if (note or category) else "") + "."]
        bits.append(f"Today: {_fmt(today_total, cur_line)}. "
                    f"This month: {_fmt(month_total, cur_line)}.")
        return " ".join(bits)
    except Exception as e:
        return "Sir, the expense tracker failed: " + str(e)
