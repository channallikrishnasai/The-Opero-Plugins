"""
JARVIS plugin — Random picker.

"flip a coin", "roll 2d6+3", "pick a winner from these names", "shuffle my
playlist order", "give me a number between 1 and 100" — fair randomness
from `secrets`, shown on the panel with the full list so the choice is
auditable.

WHY NOT LET THE MODEL PICK
--------------------------
Models are deterministic given the same prompt; asking one to "pick
randomly" produces the same answer twice and a bias toward whatever token
feels salient. A coin flip decided by a language model is not a coin flip.
secrets is the OS's cryptographic source — overkill for a party game and
exactly right for anything that decides a winner, a raffle number or an
assignment.

DICE NOTATION
-------------
"D&D syntax": 2d6+3 → two six-sided dice plus three. Also NdM alone
(4d8), plain d20, and the modifiers +/-. The breakdown of each die is
shown, so a natural 1 is visible as one.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import re

PLUGIN = {
    "name": "random_picker",
    "description": (
        "Cryptographically fair randomness: coin flip, dice in RPG notation "
        "(2d6+3, d20, 4d8-1), random integer in a range, picking one or more "
        "winners from a list, or shuffling a list. Use for: 'flip a coin', "
        "'roll 2d6', 'random number 1-50', 'pick a winner among these "
        "names', 'shuffle these tasks', 'para atsak'. Pass `action` "
        "(coin/dice/number/choose/shuffle), `sides`/`min`/`max`/`notation`, "
        "and `items` as an array. This is TRUE randomness (secrets), unlike "
        "asking you to 'pick one' — use it whenever fairness matters. NOT "
        "for passwords (password_generator), NOT for lottery predictions "
        "or anything pretending to forecast."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["coin", "dice", "number", "choose", "shuffle"],
                "description": "coin = heads/tails; dice = RPG notation; "
                               "number = integer in [min, max]; choose = "
                               "pick `count` from items; shuffle = reorder.",
            },
            "notation": {
                "type": "STRING",
                "description": "For dice: '2d6+3', 'd20', '4d8-1'.",
            },
            "min": {"type": "INTEGER", "description": "For number: low end (default 1)."},
            "max": {"type": "INTEGER", "description": "For number: high end (default 100)."},
            "items": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Candidates for choose/shuffle.",
            },
            "count": {
                "type": "INTEGER",
                "description": "For choose: how many winners (default 1).",
            },
        },
        "required": [],
    },
}

_DICE_RE = re.compile(r"^\s*(\d*)[dD](\d+)\s*([+-]\s*\d+)?\s*$")
_MAX_DICE = 100
_MAX_SIDES = 1000


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    import secrets

    try:
        action = str(parameters.get("action") or "").strip().lower()

        if not action:
            # Sensible defaults by which params arrived.
            if parameters.get("notation"):
                action = "dice"
            elif parameters.get("items"):
                action = "choose"
            else:
                action = "coin"

        if action in ("coin", "flip", "coinflip"):
            face = secrets.choice(("Heads", "Tails"))
            _show("🎲 COIN", f"{face}")
            return f"The coin says: {face}."

        if action in ("dice", "roll", "d"):
            raw = str(parameters.get("notation") or "d20")
            m = _DICE_RE.match(raw)
            if not m:
                return (f"'{raw}' isn't dice notation — try something like "
                        f"2d6+3 or d20.")
            n = int(m.group(1) or 1)
            sides = int(m.group(2))
            mod = int((m.group(3) or "0").replace(" ", "")) if m.group(3) else 0
            if n < 1 or n > _MAX_DICE or sides < 2 or sides > _MAX_SIDES:
                return (f"I'll roll 1–{_MAX_DICE} dice with 2–{_MAX_SIDES} "
                        f"sides each — that request is outside that.")
            rolls = [secrets.randbelow(sides) + 1 for _ in range(n)]
            total = sum(rolls) + mod
            detail = " + ".join(str(r) for r in rolls)
            if mod:
                detail += f" {'+' if mod > 0 else '-'} {abs(mod)}"
            line = f"{raw.strip().lower()}: [{', '.join(map(str, rolls))}]"
            if mod:
                line += f" {'+' if mod > 0 else '-'} {abs(mod)}"
            line += f" = {total}"
            _show("🎲 ROLL", f"{line}\n\ndetails: {detail}")
            return line + "."

        if action in ("number", "randint", "random"):
            try:
                lo = int(parameters.get("min") if parameters.get("min") is not None else 1)
                hi = int(parameters.get("max") if parameters.get("max") is not None else 100)
            except (TypeError, ValueError):
                return "Give me integer bounds for the range."
            if lo > hi:
                lo, hi = hi, lo
            if hi - lo > 10 ** 12:
                return "That range is too wide."
            n = secrets.randbelow(hi - lo + 1) + lo
            return f"Random number between {lo} and {hi}: {n}."

        items = [str(x).strip() for x in (parameters.get("items") or [])
                 if str(x).strip()]
        if isinstance(parameters.get("items"), str):
            items = [x.strip() for x in str(parameters.get("items")).split(",")
                     if x.strip()]

        if action in ("choose", "pick", "winner"):
            if not items:
                return "Give me the list to choose from."
            try:
                count = int(parameters.get("count") or 1)
            except (TypeError, ValueError):
                count = 1
            count = max(1, min(count, len(items)))
            pool = list(items)
            winners = []
            for _ in range(count):
                winners.append(pool.pop(secrets.randbelow(len(pool))))
            if count == 1:
                _show("🎲 PICK", winners[0])
                return f"Picked: {winners[0]} (from {len(items)} options)."
            _show("🎲 PICK", "\n".join(winners))
            return (f"Picked {count}: {', '.join(winners)} "
                    f"(from {len(items)} options).")

        if action in ("shuffle", "shuffle_list", "mix"):
            if not items:
                return "Give me the list to shuffle."
            mixed = list(items)
            for i in range(len(mixed) - 1, 0, -1):
                j = secrets.randbelow(i + 1)
                mixed[i], mixed[j] = mixed[j], mixed[i]
            _show("🎲 SHUFFLED", "\n".join(f"{i}. {x}"
                                           for i, x in enumerate(mixed, 1)))
            return "Shuffled: " + " · ".join(mixed) + "."

        return (f"I don't know '{action}'. Try coin, dice, number, "
                f"choose or shuffle.")
    except Exception as e:
        return "Sir, the random picker failed: " + str(e)
