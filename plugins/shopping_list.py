"""
JARVIS plugin — Shopping list.

"add milk and eggs", "shopping liste ekle bisküvi", "what's on my list",
"take bread off the list", "clear the list — just bought everything" —
the paper list on the fridge, kept in memory/shopping_list.json so it
survives restarts and is readable from anywhere in the house.

WHY A LIST DESERVES ITS OWN PLUGIN
-----------------------------------
The model can remember three items in a conversation and loses the fourth.
A shopping list is exactly the artifact that must outlive the chat: added
in the kitchen, read in the car, cleared at the till. Storage is one JSON
array, deduplicated case-insensitively — "Milk" and "milk" are one item,
because two entries for the same gallon is how lists become untrustworthy.

WHAT IT IS NOT
--------------
Not a to-do manager (habits and tasks live elsewhere), not a note (journal)
and not an expense log (expense_tracker knows prices; this one only knows
names).

FOR EVERYONE: standard library only, no keys, no setup. Same on Windows,
macOS and Linux.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "shopping_list.json"

PLUGIN = {
    "name": "shopping_list",
    "description": (
        "Maintains a persistent shopping list: add items, remove items, show "
        "what's on it, clear it. Use for: 'add milk and eggs to my shopping "
        "list', 'we need bread and 2 kilos of chicken', 'what's on the "
        "shopping list', 'remove milk', 'clear the shopping list', 'markette "
        "ne var'. Pass items as an array of short names (quantities can be "
        "part of the name, e.g. '2 kg chicken'). Do NOT use for tasks/todos, "
        "notes (journal), or expenses (expense_tracker)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["add", "remove", "list", "clear"],
                "description": "'add' (default), 'remove', 'list', 'clear'.",
            },
            "items": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Item names for add/remove — e.g. ['milk', 'eggs'].",
            },
        },
        "required": [],
    },
}

_MAX_ITEMS = 200


def _load() -> list[str]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
    except (OSError, ValueError):
        pass
    return []


def _save(items: list[str]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(items[:_MAX_ITEMS], ensure_ascii=False, indent=1),
                              encoding="utf-8")
    except OSError:
        pass


def _norm(s: str) -> str:
    return " ".join(str(s).strip().casefold().split())


def _parse_items(raw) -> list[str]:
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(body: str) -> None:
        if player:
            try:
                player.show_content("🛒 SHOPPING LIST", body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "add").strip().lower()
        items = _parse_items(parameters.get("items"))
        current = _load()

        if action == "clear":
            if not current:
                return "The shopping list is already empty."
            n = len(current)
            _save([])
            return f"Cleared the shopping list ({n} item(s) gone)."

        if action in ("list", "show", "read"):
            if not current:
                return "Your shopping list is empty."
            body = "\n".join(f"☐ {it}" for it in current)
            _show(body)
            return (f"{len(current)} item(s) on the list: "
                    + ", ".join(current[:8])
                    + ("…" if len(current) > 8 else "") + ". Full list on screen.")

        if action in ("remove", "delete", "drop"):
            if not items:
                return "What should I take off the list?"
            removed, missing = [], []
            for it in items:
                key = _norm(it)
                hit = next((x for x in current if _norm(x) == key), None)
                if hit is None:
                    # prefix match: "milk" removes "2% milk"
                    hit = next((x for x in current if _norm(x).startswith(key)), None)
                if hit:
                    current.remove(hit)
                    removed.append(hit)
                else:
                    missing.append(it)
            _save(current)
            if not removed:
                return f"I couldn't find {', '.join(missing)} on the list."
            msg = f"Removed: {', '.join(removed)}."
            if missing:
                msg += f" Not on the list: {', '.join(missing)}."
            msg += f" {len(current)} item(s) left."
            return msg

        # -------- ADD (default) --------
        if not items:
            return "What should I add to the shopping list?"
        added = []
        for it in items:
            it = it.strip()[:80]
            if not it:
                continue
            if not any(_norm(x) == _norm(it) for x in current):
                current.append(it)
                added.append(it)
        _save(current)
        if not added:
            return "Those are already on the list."
        _show("\n".join(f"☐ {x}" for x in current))
        return (f"Added: {', '.join(added)}. List now has {len(current)} "
                f"item(s) — on screen.")
    except Exception as e:
        return "Sir, the shopping list failed: " + str(e)
