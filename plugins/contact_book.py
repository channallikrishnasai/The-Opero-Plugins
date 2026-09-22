"""
JARVIS plugin — Contact book.

"what's mom's number", "kaydet 555 123 4567 Ahmet", "add Sara, +44 7700
900123, works at Northwind" — names and numbers the assistant should know
without a phone in the room.

WHY IT LIVES IN MEMORY/
----------------------
Contacts are the most personal small dataset a personal assistant holds.
They stay in memory/contacts.json on this machine, are never sent anywhere
by this plugin, and are only ever read back to the person who asked. No
cloud, no sync, no address-book permission — the whole file is a JSON list
of {name, phone, note}.

IT NEVER DIALS
--------------
Recording and recalling a number is the plugin. Calling, messaging and
emailing go through the app's existing communication tools, which have
their own confirmations — a contact lookup must never become a side
channel that skips them.

NORMALISED ENOUGH TO FIND
-------------------------
Lookup is case-insensitive and matches on part of a name, because people
say "mom", "Mom", "MOM" and saved the entry as "Mom (mother)".

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "contacts.json"

PLUGIN = {
    "name": "contact_book",
    "description": (
        "Stores and recalls personal contacts (name, phone, optional note) "
        "on this machine. Use for: 'what's mom's number', 'save this number "
        "555-1234 as Ahmet', 'add contact Sara +44 7700 900123', 'list my "
        "contacts', 'delete contact Ahmet', 'Ahmet'in numarası ne'. This "
        "plugin only LOOKS UP and SAVES numbers — it never calls or texts "
        "anyone; actually contacting a person is send_message / the call "
        "tools. NOT for notes (journal) or businesses you don't know yet."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["add", "search", "list", "delete"],
                "description": "'search' (default when name given), 'add', "
                               "'list' (max 30), 'delete'.",
            },
            "name": {
                "type": "STRING",
                "description": "Contact's name as the user says it.",
            },
            "phone": {
                "type": "STRING",
                "description": "Phone number for 'add' / 'delete' confirmation.",
            },
            "note": {
                "type": "STRING",
                "description": "Optional short note — 'mom', 'dentist', "
                               "'Northwind'.",
            },
            "query": {
                "type": "STRING",
                "description": "For 'search': partial name to look for.",
            },
        },
        "required": [],
    },
}

_MAX = 1000


def _load() -> list[dict]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [c for c in data if isinstance(c, dict) and c.get("name")]
    except (OSError, ValueError):
        pass
    return []


def _save(rows: list[dict]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(rows[:_MAX], ensure_ascii=False, indent=1),
                              encoding="utf-8")
    except OSError:
        pass


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\w\s+]", " ", str(s or "")).casefold().split())


def _matches(row: dict, needle: str) -> bool:
    n = _norm(needle)
    if not n:
        return False
    hay = _norm(row.get("name")) + " " + _norm(row.get("note"))
    return n in hay or any(tok.startswith(n) or n.startswith(tok)
                           for tok in hay.split() if len(tok) > 2)


def _fmt(row: dict) -> str:
    note = f"  · {row['note']}" if row.get("note") else ""
    return f"{row.get('name', '?')}  {row.get('phone', '')}{note}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "").strip().lower()
        name = str(parameters.get("name") or "").strip()
        phone = str(parameters.get("phone") or "").strip()
        note = str(parameters.get("note") or "").strip()[:120]
        query = str(parameters.get("query") or "").strip()
        rows = _load()

        # Default: given a name or query → search; nothing → list.
        if not action:
            action = "search" if (query or name) else "list"

        if action == "add":
            if not name:
                return "Who should I save? Give me a name and a number."
            if not phone and not note:
                return (f"Give me a number or a note for {name} — a name "
                        f"alone isn't a contact I can read back usefully.")
            existing = next((r for r in rows if _norm(r.get("name")) == _norm(name)), None)
            if existing:
                existing["phone"] = phone or existing.get("phone", "")
                existing["note"] = note or existing.get("note", "")
                _save(rows)
                return f"Updated {existing['name']}: {_fmt(existing)}."
            row = {"name": name[:80], "phone": phone[:40], "note": note}
            rows.append(row)
            _save(rows)
            return f"Saved {_fmt(row)}. That's {len(rows)} contact(s) now."

        if action in ("delete", "remove"):
            target = query or name
            if not target:
                return "Which contact should I delete?"
            hit = next((r for r in rows if _matches(r, target)), None)
            if not hit:
                return f"I couldn't find a contact matching '{target}'."
            rows.remove(hit)
            _save(rows)
            return f"Deleted {hit.get('name')}."

        if action == "list":
            if not rows:
                return "Your contact book is empty."
            show = rows[:30]
            body = "\n".join(_fmt(r) for r in show)
            _show("👥 CONTACTS", body)
            return (f"{len(rows)} contact(s) saved, {len(show)} on screen. "
                    f"First few: " + "; ".join(r.get("name", "") for r in show[:5]) + ".")

        # -------- SEARCH --------
        needle = query or name
        if not needle:
            return "Who are you looking for?"
        hits = [r for r in rows if _matches(r, needle)]
        if not hits:
            return f"No contact matches '{needle}'."
        if len(hits) == 1:
            return f"{hits[0].get('name')}: {hits[0].get('phone') or 'no number'}" + \
                   (f" ({hits[0]['note']})" if hits[0].get("note") else "") + "."
        body = "\n".join(_fmt(r) for r in hits[:30])
        _show(f"👥 {needle.upper()}", body)
        return (f"{len(hits)} matches for '{needle}': " +
                "; ".join(f"{r.get('name')} {r.get('phone') or ''}" for r in hits[:5]) +
                " — all on screen.")
    except Exception as e:
        return "Sir, the contact book failed: " + str(e)
