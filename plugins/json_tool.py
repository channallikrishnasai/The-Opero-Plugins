"""
JARVIS plugin — JSON toolbox.

"is this valid json", "pretty print this blob", "give me data.user.email
from this object" — validate, format and pull values out of JSON the user
pasted or an API returned.

WHY A TOOL FOR SOMETHING PYTHON DOES IN ONE LINE
------------------------------------------------
Because the user can't run Python, and because the model reading a 40-line
JSON blob and "extracting" a field is exactly how a wrong value gets
confidently reported. This parses for real (json.loads), so "valid" means
valid, and a path walk is a path walk.

PATH SYNTAX
-----------
Dot keys and [index]: `config.providers[0].api_key`. Missing path →
says so; it never invents a value to fill the hole.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import json

PLUGIN = {
    "name": "json_tool",
    "description": (
        "Validates JSON, pretty-prints it, minifies it, or extracts a value "
        "by path. Use for: 'is this valid json', 'format this json blob', "
        "'minify this', 'get user.email from this object', 'bu json doğru "
        "mu'. Pass `json_text` plus `action` (validate/pretty/minify/get) "
        "and for 'get' a `path` like 'items[0].name'. Parse errors are "
        "reported with line/column so the user can fix them. NOT for CSV "
        "(csv_analyzer), NOT for querying huge files on disk (read a slice "
        "first)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["validate", "pretty", "minify", "get"],
                "description": "validate = ok/error with position; pretty = "
                               "indented; compact = one line; get = value at "
                               "`path`.",
            },
            "json_text": {"type": "STRING", "description": "The JSON payload."},
            "path": {
                "type": "STRING",
                "description": "For 'get': dotted path with optional [i] "
                               "indices — 'users[0].name'.",
            },
        },
        "required": ["json_text"],
    },
}

_MAX = 500_000


def _walk(obj, path: str):
    cur = obj
    token = ""
    i = 0
    steps: list[str] = []
    # Split a.b[0].c into ['a', 'b', '0', 'c'] — tiny parser, no eval.
    while i < len(path):
        ch = path[i]
        if ch == ".":
            if token:
                steps.append(token)
                token = ""
            i += 1
        elif ch == "[":
            if token:
                steps.append(token)
                token = ""
            j = path.find("]", i)
            if j < 0:
                raise ValueError(f"unclosed [ at position {i}")
            steps.append(path[i + 1:j].strip().strip("'\""))
            i = j + 1
        else:
            token += ch
            i += 1
    if token:
        steps.append(token)

    for step in steps:
        if isinstance(cur, list):
            try:
                cur = cur[int(step)]
            except (ValueError, IndexError):
                raise KeyError(f"no index '{step}'")
        elif isinstance(cur, dict):
            if step not in cur:
                raise KeyError(step)
            cur = cur[step]
        else:
            raise KeyError(f"can't descend into {type(cur).__name__} at '{step}'")
    return cur


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "validate").strip().lower()
        if action in ("compact", "minify", "min"):
            action = "minify"
        raw = str(parameters.get("json_text") or "")
        if not raw.strip():
            return "Paste the JSON first."
        if len(raw) > _MAX:
            return f"Too large ({len(raw)} chars) — work with a slice."

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            # Line/column is the whole point: "Expecting ',' delimiter" with
            # no position sends people hunting through a wall of braces.
            return (f"Invalid JSON at line {e.lineno}, column {e.colno}: "
                    f"{e.msg}.")

        if action == "validate":
            kind = type(data).__name__
            size = (len(data) if isinstance(data, (list, dict, str)) else None)
            extra = f" with {size} entries" if size is not None else ""
            return f"Valid JSON — {kind}{extra}."

        if action == "pretty":
            out = json.dumps(data, indent=2, ensure_ascii=False)
            _show("📄 JSON", out[:20000])
            return (f"Pretty-printed ({len(out)} chars) — on screen."
                    if len(out) > 200 else f"```json\n{out}\n```")

        if action == "minify":
            out = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
            if len(out) > 280:
                _show("📄 JSON (minified)", out[:20000])
                return f"Minified to {len(out)} chars — on screen."
            return out

        if action in ("get", "find", "path"):
            path = str(parameters.get("path") or "").strip()
            if not path:
                return "Give a path like 'users[0].name'."
            try:
                val = _walk(data, path)
            except (KeyError, ValueError, IndexError) as e:
                return f"Path '{path}' not found: {e}."
            out = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
            if len(out) > 500:
                _show(f"📄 {path}", str(out)[:20000])
                return f"Value at '{path}' is long ({len(out)} chars) — on screen."
            return str(out)

        return f"Unknown action '{action}'. Use validate, pretty, minify or get."
    except Exception as e:
        return "Sir, the JSON tool failed: " + str(e)
