"""
JARVIS plugin — Encoding toolbox.

"base64 encode this", "decode this URL blob", "sha256 of this string",
"rot13 it for me" — the small transformations developers and CTF players
reach for constantly, done by hashlib/base64/urllib rather than by a
model that might quietly corrupt a byte.

WHY THE MODEL MUST NOT DO THIS ITSELF
--------------------------------------
Base64 and hex are pure arithmetic on bytes; models invent characters
under long outputs the way people invent digits under long addition. One
wrong letter and the decode fails with a confusing error thirty minutes
later. The model extracts (operation, format, payload); the standard
library does the work.

PASSWORDS ARE OUT OF SCOPE
--------------------------
Hashing a password by hand is not a security practice, and echoing one
into a chat is not either — password_generator exists for creating
secrets, and a password manager is the answer for storing them. This
toolbox is for data transformation: API payloads, checksums, debugging.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import urllib.parse

PLUGIN = {
    "name": "encoding_toolbox",
    "description": (
        "Encodes/decodes data and computes hashes: base64, hex, URL "
        "encoding, ROT13, and SHA-1/SHA-256/MD5 digests. Use for: 'base64 "
        "encode this string', 'decode eyJ…', 'url encode this query', "
        "'sha256 of \"hello\"', 'what's the md5 of this', 'hex dump this'. "
        "Pass `data`, `format` and `action` (encode/decode/hash). Do NOT "
        "use it to hash or store passwords (that is password_generator / "
        "a password manager), NOT for file encryption, NOT for unit "
        "conversions."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["encode", "decode", "hash"],
                "description": "encode = plain → format; decode = format → "
                               "plain; hash = one-way digest (use `format` "
                               "for the algorithm when hashing).",
            },
            "format": {
                "type": "STRING",
                "enum": ["base64", "hex", "url", "rot13", "sha256", "sha1", "md5"],
                "description": "Target format for encode/decode, or digest "
                               "algorithm for hash (default base64 / sha256).",
            },
            "data": {
                "type": "STRING",
                "description": "The payload to transform.",
            },
        },
        "required": ["action", "data"],
    },
}

_MAX = 100_000
_HASHES = {"sha256": hashlib.sha256, "sha1": hashlib.sha1, "md5": hashlib.md5}


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _out(label: str, value: str) -> str:
        if player:
            try:
                player.show_content(f"🔧 {label}", value)
            except Exception:
                pass
        # Long digests/encodings go to the panel; the spoken line stays short.
        if len(value) > 280:
            return f"{label} on screen ({len(value)} chars). First 60: {value[:60]}…"
        return f"{label}: {value}"

    try:
        action = str(parameters.get("action") or "encode").strip().lower()
        fmt = str(parameters.get("format") or "").strip().lower() or \
            ("sha256" if action == "hash" else "base64")
        data = str(parameters.get("data") or "")
        if not data:
            return "Give me some data to work on."
        if len(data) > _MAX:
            return f"Too long ({len(data)} chars) — cap is {_MAX}."

        if action == "hash":
            fn = _HASHES.get(fmt)
            if fn is None:
                return f"I can hash with sha256, sha1 or md5 — not '{fmt}'."
            digest = fn(data.encode("utf-8")).hexdigest()
            return _out(f"{fmt.upper()} HASH", digest)

        if fmt == "rot13":
            # ROT13 is its own inverse — encode and decode are the same op.
            return _out("ROT13", _rot13(data))

        if action == "encode":
            raw = data.encode("utf-8")
            if fmt == "base64":
                return _out("BASE64", base64.b64encode(raw).decode("ascii"))
            if fmt == "hex":
                return _out("HEX", raw.hex())
            if fmt == "url":
                return _out("URL ENCODED", urllib.parse.quote(data, safe=""))
            return f"Unknown format '{fmt}'. Try base64, hex, url or rot13."

        # decode
        try:
            if fmt == "base64":
                pad = "=" * (-len(data) % 4)
                return _out("DECODED", base64.b64decode(data + pad, validate=False)
                            .decode("utf-8", errors="replace"))
            if fmt == "hex":
                return _out("DECODED", bytes.fromhex(data.strip()).decode(
                    "utf-8", errors="replace"))
            if fmt == "url":
                return _out("DECODED", urllib.parse.unquote(data))
            return f"Unknown format '{fmt}'. Try base64, hex or url."
        except (binascii.Error, ValueError) as e:
            return f"That doesn't decode as {fmt} ({e})."
    except Exception as e:
        return "Sir, the encoding toolbox failed: " + str(e)


def _rot13(s: str) -> str:
    out = []
    for c in s:
        if "a" <= c <= "z":
            out.append(chr((ord(c) - ord("a") + 13) % 26 + ord("a")))
        elif "A" <= c <= "Z":
            out.append(chr((ord(c) - ord("A") + 13) % 26 + ord("A")))
        else:
            out.append(c)
    return "".join(out)
