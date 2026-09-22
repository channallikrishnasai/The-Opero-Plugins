"""
JARVIS plugin — Daily journal.

"bugün ne yaptığımı not et", "remember I had the dentist at 3", "read back
today's journal", "what did I write yesterday about the meeting" — a plain
spoken diary that lives in memory/journal.jsonl and can be read back, day by
day or searched.

WHY A FILE, AND WHY JSONL
-------------------------
Everything else about the user already lives in memory/ — water totals,
pomodoro minutes — because that is the folder that survives updates and
backs up with the rest of the profile. JSONL (one JSON object per line)
means appending is one line, a corrupted entry costs only itself, and the
file still opens in any text editor when something looks wrong.

WHAT THE MODEL DOES VS WHAT THIS FILE DOES
------------------------------------------
The model decides what is worth writing — it filters the ramble down to the
note — and this plugin only stores, dates and retrieves. That keeps every
language working with no translation table: the note is written in the
user's own words and comes back in the same ones.

IT KEEPS NO MEMORY OF ITS OWN BEYOND THE FILE
----------------------------------------------
One rolling `remember()` note carries "what was the last journal entry"
into long-term memory so a later conversation can pick the thread up;
history itself stays in the JSONL, queryable by date or search.

FOR EVERYONE: standard library only, no keys, no setup. Same on Windows,
macOS and Linux.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "journal.jsonl"

PLUGIN = {
    "name": "journal",
    "description": (
        "Writes dated entries to a personal journal and reads them back. Use "
        "for: 'note that I ...', 'remember I have a call at 5', 'add to my "
        "journal', 'read today's journal', 'what did I write yesterday', "
        "'search my journal for dentist', 'bugün ne yaptığımı yaz'. This is "
        "a DIARY of things that happened or were decided — do NOT use it for "
        "one-off timed alerts (that is the reminder tool), for facts about "
        "the user that should be known forever across topics (that is "
        "save_memory), or for files and notes on disk (that is the file "
        "tools). Entries are stored under memory/journal.jsonl and are never "
        "sent anywhere."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["write", "read", "search"],
                "description": "'write' (default) appends an entry; 'read' "
                               "shows a day's entries (default today); "
                               "'search' finds entries containing a phrase.",
            },
            "text": {
                "type": "STRING",
                "description": "For 'write': the entry itself, already "
                               "condensed to what's worth remembering, in "
                               "the user's own language.",
            },
            "day": {
                "type": "STRING",
                "description": "For 'read': a date as YYYY-MM-DD, or 'today' "
                               "(default), 'yesterday'. Ignored by 'search'.",
            },
            "query": {
                "type": "STRING",
                "description": "For 'search': words to look for, matched "
                               "case-insensitively across all entries.",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Max entries to return for read/search "
                               "(default 10, max 50).",
            },
        },
        "required": [],
    },
}

_MAX_TEXT = 2000        # a journal line, not a document


def _load_lines() -> list[dict]:
    """Read the JSONL, skipping any corrupt line rather than failing whole."""
    out = []
    try:
        with STATE_FILE.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict) and obj.get("text"):
                    out.append(obj)
    except OSError:
        pass
    return out


def _append(text: str) -> dict:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {"date": date.today().isoformat(),
             "ts": datetime.now().isoformat(timespec="seconds"),
             "text": text}
    with STATE_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _day_key(raw: str) -> str:
    raw = (raw or "").strip().lower()
    today = date.today()
    if raw in ("", "today", "bugün"):
        return today.isoformat()
    if raw in ("yesterday", "dün"):
        return (today - timedelta(days=1)).isoformat()
    # Already an ISO date, or something the model should have normalized.
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return today.isoformat()


def _remember(entry: dict) -> None:
    """One rolling long-term note — replaces itself each time, never piles up."""
    try:
        from memory.memory_manager import remember
        remember("journal_last",
                 f"Last journal entry ({entry['date']}): {entry['text'][:300]}",
                 "notes")
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
        action = str(parameters.get("action") or "write").strip().lower()
        try:
            limit = int(parameters.get("limit") or 10)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))

        # -------- SEARCH --------
        if action == "search":
            q = str(parameters.get("query") or "").strip()
            if not q:
                return "Tell me what to look for in the journal."
            needle = q.casefold()
            hits = [e for e in _load_lines() if needle in e["text"].casefold()]
            if not hits:
                return f"I found no journal entries containing '{q}'."
            hits = hits[-limit:]
            body = "\n\n".join(f"{e['date']}  {e['text']}" for e in hits)
            _show(f"🔎 JOURNAL · {q.upper()}", body)
            newest = hits[-1]
            return (f"{len(hits)} entr{'y' if len(hits) == 1 else 'ies'} "
                    f"mention '{q}', most recent from {newest['date']}: "
                    f"“{newest['text'][:160]}” — all on screen.")

        # -------- READ --------
        if action == "read":
            key = _day_key(str(parameters.get("day") or ""))
            day = [e for e in _load_lines() if e.get("date") == key]
            if not day:
                return f"There's nothing in the journal for {key}."
            day = day[-limit:]
            body = "\n\n".join(
                f"{e['ts'].split('T', 1)[-1][:5]}  {e['text']}" for e in day)
            _show(f"📖 JOURNAL · {key}", body)
            return (f"{len(day)} entr{'y' if len(day) == 1 else 'ies'} on "
                    f"{key}, on screen. Most recent: "
                    f"“{day[-1]['text'][:160]}”.")

        # -------- WRITE (default) --------
        text = str(parameters.get("text") or "").strip()
        if not text:
            return "Tell me what to write down first."
        text = text[:_MAX_TEXT]
        entry = _append(text)
        _remember(entry)
        return (f"Written to your journal for {entry['date']}: "
                f"“{text[:120]}”{'…' if len(text) > 120 else ''}.")
    except Exception as e:
        return "Sir, the journal failed: " + str(e)
