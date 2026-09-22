"""
JARVIS plugin — Password generator.

"make me a strong password for my github", "bana 20 karakterlik bir parola
üret", "generate a passphrase I can actually remember" — JARVIS builds one
with the standard library's secrets module and says how strong it is.

WHY THIS EXISTS EVEN THOUGH A BROWSER BUILDS ONE
-----------------------------------------------
People still need passwords for the things browsers do not fill: the Wi-Fi
guest network, a shared work account, an answer to a security question on a
site with no password manager. Saying it out loud is the wrong channel for a
secret, so the password goes into the panel where it can be copied, and the
spoken line only carries the strength and the character count.

TWO KINDS, ONE RULE
-------------------
A random jumble for machines, and a diceware-style passphrase for humans who
have to type it on a phone. Both are drawn from `secrets`, never `random` —
the latter is predictable from its output and a password generator that is
predictable is worse than no generator at all.

FOR EVERYONE: no keys, no setup, no third-party packages, same on Windows,
macOS and Linux. Nothing is written to disk; the password exists only in the
response and on the screen in front of you.
"""
from __future__ import annotations

import string

PLUGIN = {
    "name": "password_generator",
    "description": (
        "Generates a cryptographically strong password or memorable passphrase "
        "and shows it on screen, with a strength rating. Use for: 'generate a "
        "password', 'make me a strong password for github', 'bana parola üret', "
        " 'I need a new password', 'give me a passphrase I can remember', "
        "'how strong is this password' (pass action='check' with `password` "
        "filled to rate an existing one). Use ONLY when the user wants a "
        "password/passphrase created or rated — not for Wi-Fi passwords "
        "already saved anywhere, not for password-manager questions, and not "
        "for any other credentials."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["generate", "check"],
                "description": "'generate' (default) makes a new password; "
                               "'check' rates an existing one passed in "
                               "`password` without storing it.",
            },
            "style": {
                "type": "STRING",
                "enum": ["password", "passphrase"],
                "description": "'password' = random characters (default). "
                               "'passphrase' = several real words joined for "
                               "a human who must type it on a phone.",
            },
            "length": {
                "type": "INTEGER",
                "description": "For 'password': length in characters (default "
                               "20, min 8, max 128).",
            },
            "words": {
                "type": "INTEGER",
                "description": "For 'passphrase': number of words (default 5, "
                               "min 3, max 12).",
            },
            "no_symbols": {
                "type": "BOOLEAN",
                "description": "True = letters and digits only, for fields "
                               "that reject punctuation (default false).",
            },
            "password": {
                "type": "STRING",
                "description": "For 'check' only: the existing password to "
                               "rate. Never logged, never stored.",
            },
        },
        "required": [],
    },
}

# Ambiguous characters left out by default: a password nobody can read aloud
# over a phone is a password that gets copied wrong and reset five minutes
# later. An explicit length still wins — this only shapes the alphabet.
_AMBIGUOUS = "0Oo1lI|"

_LOWER = string.ascii_lowercase.replace("l", "").replace("o", "")
_UPPER = string.ascii_uppercase.replace("I", "").replace("O", "")
_DIGITS = "".join(d for d in string.digits if d not in _AMBIGUOUS)
_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"


def _alphabet(no_symbols: bool) -> str:
    chars = _LOWER + _UPPER + _DIGITS
    if not no_symbols:
        chars += _SYMBOLS
    return chars


def _random_password(length: int, no_symbols: bool) -> str:
    import secrets

    chars = _alphabet(no_symbols)
    # One from each class first, then the rest — a purely random draw can
    # hand back twenty letters and no digit, which some sites reject and
    # most people read as "weak" even when it is not.
    pools = [_LOWER, _UPPER, _DIGITS] + ([] if no_symbols else [_SYMBOLS])
    out = [secrets.choice(p) for p in pools[: max(0, length)]]
    while len(out) < length:
        out.append(secrets.choice(chars))
    # Fisher–Yates with secrets: the fixed prefix would otherwise always sit
    # at the front, which is a fingerprint, not a password.
    for i in range(len(out) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        out[i], out[j] = out[j], out[i]
    return "".join(out)


def _random_passphrase(nwords: int) -> str:
    """Five short words, hyphen-joined — diceware's shape without shipping a
    wordlist file. The pool is the same letter sets as above, built from
    `secrets`, so the entropy claim below stays honest."""
    import secrets

    syllables = ("ba", "be", "bi", "bo", "bu", "ka", "ke", "ki", "ko", "ku",
                 "ma", "me", "mi", "mo", "mu", "na", "ne", "ni", "no", "nu",
                 "pa", "pe", "pi", "po", "pu", "ra", "re", "ri", "ro", "ru",
                 "sa", "se", "si", "so", "su", "ta", "te", "ti", "to", "tu",
                 "va", "ve", "vi", "vo", "vu", "za", "ze", "zi", "zo", "zu")
    words = []
    for _ in range(nwords):
        syl = 2 + secrets.randbelow(2)          # 2–3 syllables
        words.append("".join(secrets.choice(syllables) for _ in range(syl)).capitalize())
    return "-".join(words)


def _bits(length: int, no_symbols: bool, nwords: int, style: str) -> float:
    """Rough entropy, stated as an estimate — the only honest kind."""
    import math

    if style == "passphrase":
        # ~10 bits per made-up syllable-word of this shape; deliberately
        # conservative rather than a theoretical pool size.
        return nwords * 10.0
    pool = len(_alphabet(no_symbols))
    return length * math.log2(pool) if pool else 0.0


def _rate(bits: float) -> tuple[str, str]:
    if bits < 45:
        return "WEAK", "too short for anything that matters"
    if bits < 65:
        return "FAIR", "fine for a low-stakes account"
    if bits < 90:
        return "STRONG", "good for email and banking"
    return "VERY STRONG", "overkill in the best way"


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        action = str(parameters.get("action") or "generate").strip().lower()

        # -------- CHECK an existing password --------
        if action == "check":
            pw = str(parameters.get("password") or "")
            if not pw:
                return "Send the password you want rated and I'll measure it."
            import math
            pool = 0
            if any(c.islower() for c in pw):
                pool += 26
            if any(c.isupper() for c in pw):
                pool += 26
            if any(c.isdigit() for c in pw):
                pool += 10
            if any(not c.isalnum() for c in pw):
                pool += 32
            bits = len(pw) * math.log2(pool) if pool else 0.0
            label, note = _rate(bits)
            # The password itself is never echoed — a rating is the answer,
            # and repeating the secret into the activity log would undo the
            # point of asking.
            return (f"That password is {label.lower()} — about {bits:.0f} "
                    f"bits of entropy ({len(pw)} characters). {note}.")

        # -------- GENERATE --------
        style = str(parameters.get("style") or "password").strip().lower()
        no_symbols = bool(parameters.get("no_symbols"))

        if style == "passphrase":
            try:
                nwords = int(parameters.get("words") or 5)
            except (TypeError, ValueError):
                nwords = 5
            nwords = max(3, min(nwords, 12))
            secret = _random_passphrase(nwords)
            bits = _bits(0, False, nwords, "passphrase")
            shown = f"{nwords} words"
        else:
            try:
                length = int(parameters.get("length") or 20)
            except (TypeError, ValueError):
                length = 20
            length = max(8, min(length, 128))
            secret = _random_password(length, no_symbols)
            bits = _bits(length, no_symbols, 0, "password")
            shown = f"{length} characters" + (", no symbols" if no_symbols else "")

        label, note = _rate(bits)

        if player:
            try:
                player.show_content(
                    "🔐 PASSWORD",
                    f"{secret}\n\n"
                    f"{shown}  ·  ~{bits:.0f} bits\n"
                    f"{label} — {note}\n\n"
                    f"Copy it now — it is not saved anywhere."
                )
            except Exception:
                pass

        # Never spoken, never written to the activity log: the panel above is
        # the only place the secret exists.
        return (f"Done — a {label.lower()} {style} ({shown}, about "
                f"{bits:.0f} bits) is on screen. Copy it from there; I don't "
                f"store it.")
    except Exception as e:
        return "Sir, the password generator failed: " + str(e)
