"""
JARVIS plugin — Regex tester.

"does this pattern match '2026-09-23'?", "find all emails in this blob",
"test my regex against this log line" — run the pattern, list the matches
with positions, say why it failed to compile.

WHY NOT LET THE MODEL SIMULATE THE MATCH
----------------------------------------
Regex dialects differ in tiny, fatal ways (digit-class semantics, lazy flags,
lookbehind limits), and mental simulation of backtracking is where models
hallucinate entire match lists. Running Python's re gives the answer this
interpreter will give — which is the one that matters when the pattern is
about to be pasted into this machine's code.

SAFETY
------
Python's re has no per-match timeout, so a pathological pattern can burn
CPU (catastrophic backtracking). The sample text is capped at 10 000
characters and the pattern at 500 — enough for any legitimate use here,
small enough that a bad pattern fails fast in practice. Patterns are
never executed as code, only compiled.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import re

PLUGIN = {
    "name": "regex_tester",
    "description": (
        "Tests a regular expression against sample text using Python's re "
        "engine: lists matches with positions and span indices, or reports "
        "the compile error. Use for: 'does this regex match …', 'find all "
        "email addresses in this text', 'test pattern \\d+ against this "
        "log line', 'why doesn't my regex work'. Pass `pattern`, `text`, "
        "and optional `flags` ('i' ignorecase, 'm' multiline, 's' dotall, "
        "'x' verbose). Python syntax — not POSIX or PCRE-only extensions. "
        "NOT for finding patterns yourself in a file (read the file and "
        "reason about it), NOT for string replace across files (that's the "
        "file tools)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "pattern": {"type": "STRING", "description": "The regex pattern."},
            "text": {"type": "STRING", "description": "Sample text to match against."},
            "flags": {
                "type": "STRING",
                "description": "Optional flags string: i, m, s, x (e.g. 'is').",
            },
            "findall": {
                "type": "BOOLEAN",
                "description": "True = list every match; False (default) = "
                               "first match plus a yes/no verdict.",
            },
        },
        "required": ["pattern", "text"],
    },
}

_MAX_PATTERN = 500
_MAX_TEXT = 10_000
_MAX_SHOW = 50

_FLAGMAP = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL,
            "x": re.VERBOSE, "a": re.ASCII}


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(body: str) -> None:
        if player:
            try:
                player.show_content("🧪 REGEX", body)
            except Exception:
                pass

    try:
        pattern = str(parameters.get("pattern") or "")
        text = str(parameters.get("text") or "")
        if not pattern:
            return "Give me a pattern to test."
        if not text:
            return "Give me some text to test the pattern against."
        if len(pattern) > _MAX_PATTERN:
            return f"Pattern too long (max {_MAX_PATTERN} chars)."
        if len(text) > _MAX_TEXT:
            text = text[:_MAX_TEXT]

        fstr = str(parameters.get("flags") or "")
        flags = 0
        for ch in fstr.lower():
            if ch not in _FLAGMAP:
                return f"Unknown flag '{ch}'. Available: i m s x a."
            flags |= _FLAGMAP[ch]

        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return f"Pattern doesn't compile: {e}"

        want_all = bool(parameters.get("findall"))
        matches = list(rx.finditer(text))
        if not matches:
            _show(f"pattern: {pattern}\nflags: {fstr or '(none)'}\n\nNO MATCH")
            return "No match."

        if not want_all:
            m = matches[0]
            line = (f"Match: {m.group(0)!r} at index {m.start()}–{m.end()}"
                    + (f" · {len(matches)} total in sample" if len(matches) > 1 else ""))
            _show(f"pattern: {pattern}\n{line}\ngroups: {m.groups() or '(none)'}")
            return line + "."

        lines = [f"{len(matches)} match(es)", ""]
        for i, m in enumerate(matches[:_MAX_SHOW], 1):
            lines.append(f"{i}. [{m.start()}:{m.end()}] {m.group(0)!r}")
            if m.groups():
                lines.append(f"   groups: {m.groups()}")
        if len(matches) > _MAX_SHOW:
            lines.append(f"… {len(matches) - _MAX_SHOW} more")
        _show("\n".join(lines))
        preview = matches[0].group(0)
        return (f"{len(matches)} match(es). First: {preview!r} at "
                f"{matches[0].start()}–{matches[0].end()}. All on screen.")
    except Exception as e:
        return "Sir, the regex tester failed: " + str(e)
