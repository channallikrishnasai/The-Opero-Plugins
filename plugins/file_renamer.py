"""
JARVIS plugin — Batch file renamer.

"rename these photos to trip_001…", "replace spaces with underscores in
Downloads", "screenshot dosyalarına tarih ekle" — a folder-wide rename
that PREVIEWS the full mapping first and only writes when the user says
apply.

WHY TWO STEPS ARE NON-NEGOTIABLE
---------------------------------
A regex replace applied to 400 files with one wrong pattern is 400
mistakes arriving at once, and most file managers' undo is unreliable
across restarts. So action=preview (the default) prints old → new for
every file and touches nothing; action=apply runs the same mapping the
user just approved. The mapping is computed once from the listing at
preview time and re-derived at apply — so if a file appeared in between,
it simply isn't in the plan.

WHAT IT WILL NOT RENAME
------------------------
Directories (renaming a tree is a different, more dangerous operation),
symlinks, and any target that already exists — a collision skips with a
warning instead of overwriting. Everything stays inside the one folder
given: names are basenames only.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import re

PLUGIN = {
    "name": "file_renamer",
    "description": (
        "Batch-renames files in ONE folder with a preview-first workflow. "
        "Modes: 'replace' (find/replace in names, optional regex), 'prefix' "
        "(add before the name), 'suffix' (add before the extension), "
        "'number' (sequential names like trip_001). Actions: 'preview' "
        "(default — shows the mapping, renames NOTHING) and 'apply' (executes "
        "the approved mapping). Use for: 'rename these photos to trip_001', "
        "'replace spaces with underscores in Downloads', 'add prefix IMG_ to "
        "these files'. NEVER call action='apply' on the first pass — always "
        "preview first, show the user, and apply only when they confirm. "
        "Refuse paths that look like system folders (Windows, Program Files, "
        "/etc, /usr). Does not touch subfolders."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {"type": "STRING", "description": "Folder containing the files."},
            "mode": {
                "type": "STRING",
                "enum": ["replace", "prefix", "suffix", "number"],
                "description": "How names change (default replace).",
            },
            "find": {"type": "STRING", "description": "For replace: text/regex to find."},
            "replace": {"type": "STRING", "description": "For replace: replacement text."},
            "use_regex": {"type": "BOOLEAN", "description": "Treat find as a regex (default false)."},
            "text": {"type": "STRING", "description": "For prefix/suffix: the literal to add."},
            "start": {"type": "INTEGER", "description": "For number: first index (default 1)."},
            "digits": {"type": "INTEGER", "description": "For number: zero-pad width (default 3)."},
            "extension": {
                "type": "STRING",
                "description": "For number: replacement extension without dot "
                               "(default: keep each file's own).",
            },
            "action": {
                "type": "STRING",
                "enum": ["preview", "apply"],
                "description": "preview (default) shows the plan; apply "
                               "executes it. Always preview first.",
            },
            "dry_run": {
                "type": "BOOLEAN",
                "description": "Force preview even if action=apply (safety).",
            },
        },
        "required": ["path"],
    },
}

_FORBIDDEN = ("windows", "program files", "programdata", "/etc", "/usr",
              "/bin", "/sbin", "/boot", "/system32", "appdata")
_MAX = 5000


def _blocked(root) -> bool:
    low = str(root).lower().replace("\\", "/")
    parts = low.split("/")
    for bad in _FORBIDDEN:
        if bad.startswith("/"):
            if low == bad or low.startswith(bad + "/"):
                return True
        elif bad in parts:
            # 'windows' as a top-level folder name only, not 'mywindows'
            if any(p == bad for p in parts[:4]):
                return True
    return False


def _plan(root, names: list[str], mode: str, find: str, replace: str,
          use_regex: bool, text: str, start: int, digits: int,
          ext_opt: str) -> list[tuple[str, str, str | None]]:
    """Return [(old, new, skip_reason|None), …] — pure, so preview and apply
    run the same code path."""
    out = []
    seen: set[str] = set()
    i = start
    for old in names:
        p = root / old
        if p.is_symlink() or p.is_dir():
            out.append((old, old, "not a regular file"))
            continue
        stem, dot, ext = old.partition(".")
        if mode == "replace":
            if use_regex:
                try:
                    new = re.sub(find, replace, old)
                except re.error as e:
                    return [(old, old, f"bad regex: {e}")]
            else:
                new = old.replace(find, replace) if find else old
        elif mode == "prefix":
            new = text + old
        elif mode == "suffix":
            new = (old if not dot else stem + text + dot + ext) if dot else old + text
        elif mode == "number":
            use_ext = ext_opt.lstrip(".") or (ext if dot else "")
            new = f"{str(i).zfill(digits)}" + (f".{use_ext}" if use_ext else "")
            i += 1
        else:
            return [(old, old, f"unknown mode {mode}")]

        new = new.strip()
        if not new or new in (".", "..") or "/" in new or "\\" in new:
            out.append((old, old, "invalid target name"))
        elif new == old:
            out.append((old, old, None))
        elif new.lower() in seen:
            out.append((old, old, "duplicate target"))
        elif (root / new).exists():
            out.append((old, old, "target already exists"))
        else:
            seen.add(new.lower())
            out.append((old, new, None))
    return out


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    from pathlib import Path

    try:
        raw = str(parameters.get("path") or "").strip()
        if not raw:
            return "Give me the folder to rename files in."
        root = Path(raw).expanduser()
        if not root.is_dir():
            return f"'{raw}' isn't a folder."
        if _blocked(root):
            return "I won't batch-rename a system folder — pick a normal one."

        action = str(parameters.get("action") or "preview").strip().lower()
        if parameters.get("dry_run"):
            action = "preview"
        mode = str(parameters.get("mode") or "replace").strip().lower()
        find = str(parameters.get("find") or "")
        replace = str(parameters.get("replace") or "")
        use_regex = bool(parameters.get("use_regex"))
        text = str(parameters.get("text") or "")
        try:
            start = int(parameters.get("start") or 1)
        except (TypeError, ValueError):
            start = 1
        try:
            digits = int(parameters.get("digits") or 3)
        except (TypeError, ValueError):
            digits = 3
        digits = max(1, min(digits, 8))
        ext_opt = str(parameters.get("extension") or "")

        if mode == "replace" and not find:
            return "What text should I find? (mode=replace needs `find`)"
        if mode in ("prefix", "suffix") and not text:
            return "What text should I add?"
        if mode == "number" and not ext_opt and not any(
                p.is_file() and "." in p.name for p in root.iterdir()):
            pass   # extension optional — empty is fine

        names = sorted(p.name for p in root.iterdir() if p.is_file())[:_MAX]
        if not names:
            return "No files in that folder."

        plan = _plan(root, names, mode, find, replace, use_regex, text,
                     start, digits, ext_opt)
        changes = [(o, n) for o, n, err in plan if err is None and o != n]
        skips = [(o, err) for o, n, err in plan if err]

        if action != "apply":
            lines = [f"PLAN — {len(changes)} rename(s), nothing changed yet", ""]
            for o, n in changes[:40]:
                lines.append(f"{o}\n  → {n}")
            if len(changes) > 40:
                lines.append(f"… {len(changes) - 40} more")
            if skips:
                lines.append("")
                for o, err in skips[:10]:
                    lines.append(f"skip {o} ({err})")
            _show("✏️ RENAME PREVIEW", "\n".join(lines))
            if not changes:
                return "Nothing to rename — every plan entry was a no-op or a skip."
            return (f"{len(changes)} file(s) would be renamed — preview on "
                    f"screen, NOTHING changed yet. Say 'apply these renames' "
                    f"and I'll run it.")

        # -------- APPLY --------
        done, failed = [], []
        for old, new, err in plan:
            if err or old == new:
                continue
            try:
                (root / old).rename(root / new)
                done.append((old, new))
            except OSError as e:
                failed.append((old, str(e)))
        _show("✏️ RENAMED",
              "\n".join(f"{o} → {n}" for o, n in done[:50]) +
              ("\n\nFAILED:\n" + "\n".join(f"{o}: {e}" for o, e in failed)
               if failed else ""))
        msg = f"Renamed {len(done)} file(s)."
        if failed:
            msg += f" {len(failed)} failed — see panel."
        if skips:
            msg += f" Skipped {len(skips)}."
        return msg
    except Exception as e:
        return "Sir, the file renamer failed: " + str(e)
