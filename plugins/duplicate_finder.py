"""
JARVIS plugin — Duplicate file finder.

"find duplicate files in Downloads", "hangi dosyalar kopya" — group files
by size first, then by content hash only among the size-ties, and show
which copies are eating the disk.

WHY IT NEVER DELETES
---------------------
Two files with the same bytes may both be wanted (a photo in Pictures and
the same photo in a project folder), and the one you'd keep is a judgement
about the user's life, not about a checksum. So this measures, groups,
ranks by reclaimable space, and stops. Deletion is a separate, explicit
step taken with the file tools while looking at the paths this prints.

HOW IT SCANS WITHOUT HASHING THE WHOLE DISK
---------------------------------------------
Hashing every file is hours of I/O for a rare collision. Grouping by
size first discards almost everything; md5 runs only inside groups of two
or more that already share a byte count — which is the classic technique,
and the reason this finishes in seconds on a Downloads folder.

Caps keep a pathological tree (a node_modules graveyard) from running
away: files visited and total bytes hashed are both bounded, and the
report says when it hit a cap.

FOR EVERYONE: standard library only, no keys, no setup. Read-only.
"""
from __future__ import annotations

import hashlib

PLUGIN = {
    "name": "duplicate_finder",
    "description": (
        "Finds duplicate files under a folder: groups by size, then by MD5 "
        "content hash, and reports groups with total reclaimable space. "
        "Use for: 'find duplicate files in my Downloads', 'which photos are "
        "copies', 'kopya dosyaları bul', 'how much space can I free with "
        "duplicates'. Pass `path` (default: the user's home — warn that "
        "home-wide scans take longer). READ-ONLY: it never deletes or "
        "moves anything; removal is a separate deliberate step the user "
        "must ask for after seeing the list. NOT for finding SIMILAR (not "
        "identical) images, NOT for empty folders (disk_analyzer shows "
        "what's big)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {"type": "STRING",
                     "description": "Folder to scan (default home — prefer "
                                    "a specific folder like Downloads)."},
            "min_size": {
                "type": "INTEGER",
                "description": "Ignore files smaller than this many bytes "
                               "(default 1024) — skips the thousand tiny "
                               "identical .DS_Store files.",
            },
            "max_groups": {
                "type": "INTEGER",
                "description": "How many groups to show (default 10, max 30).",
            },
        },
        "required": [],
    },
}

_MAX_FILES = 50_000
_MAX_HASH_BYTES = 2_000_000_000     # stop hashing past 2 GB read
_HASH_CHUNK = 1024 * 1024


def _fmt(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


def _md5(path, cap: int) -> str | None:
    h = hashlib.md5()
    read = 0
    try:
        with open(path, "rb") as fh:
            while read < cap:
                chunk = fh.read(_HASH_CHUNK)
                if not chunk:
                    break
                h.update(chunk)
                read += len(chunk)
        return h.hexdigest()
    except OSError:
        return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(body: str) -> None:
        if player:
            try:
                player.show_content("🧬 DUPLICATE FILES", body)
            except Exception:
                pass

    from pathlib import Path
    import os

    try:
        raw = str(parameters.get("path") or "").strip()
        root = Path(raw).expanduser() if raw else Path.home()
        if not root.is_dir():
            return f"'{raw}' isn't a folder I can scan."
        try:
            min_size = int(parameters.get("min_size")
                           if parameters.get("min_size") is not None else 1024)
        except (TypeError, ValueError):
            min_size = 1024
        min_size = max(0, min_size)
        try:
            max_groups = int(parameters.get("max_groups") or 10)
        except (TypeError, ValueError):
            max_groups = 10
        max_groups = max(1, min(max_groups, 30))

        # -- pass 1: index by size --
        by_size: dict[int, list[str]] = {}
        visited = 0
        capped = False
        stack = [str(root)]
        while stack:
            cur = stack.pop()
            try:
                with os.scandir(cur) as it:
                    for entry in it:
                        if visited >= _MAX_FILES:
                            capped = True
                            stack.clear()
                            break
                        try:
                            if entry.is_symlink():
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                st = entry.stat(follow_symlinks=False)
                                if st.st_size >= min_size:
                                    by_size.setdefault(st.st_size, []).append(entry.path)
                                visited += 1
                        except OSError:
                            continue
            except OSError:
                continue

        candidates = {s: ps for s, ps in by_size.items() if len(ps) > 1}
        n_cand = sum(len(ps) for ps in candidates.values())

        # -- pass 2: hash only inside size groups --
        hashed_bytes = 0
        groups: dict[str, list[str]] = {}
        for size in sorted(candidates, reverse=True):
            if hashed_bytes >= _MAX_HASH_BYTES:
                capped = True
                break
            for path in candidates[size]:
                if hashed_bytes >= _MAX_HASH_BYTES:
                    capped = True
                    break
                digest = _md5(path, min(size, _MAX_HASH_BYTES - hashed_bytes))
                hashed_bytes += min(size, _MAX_HASH_BYTES)
                if digest:
                    groups.setdefault(f"{size}:{digest}", []).append(path)

        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        # Reclaim = all copies but one, per group.
        reclaim = 0
        rows = []
        for key, paths in dupes.items():
            size = int(key.split(":", 1)[0])
            reclaim += size * (len(paths) - 1)
            rows.append((size * (len(paths) - 1), size, paths))
        rows.sort(reverse=True)

        if not rows:
            msg = (f"No duplicates over {_fmt(min_size)} in {root.name} "
                   f"({visited} files checked).")
            if capped:
                msg += " (scan hit its cap — a subfolder may remain.)"
            return msg

        lines = [f"{root}", f"{len(rows)} duplicate group(s), "
                            f"{_fmt(reclaim)} reclaimable", ""]
        for saved, size, paths in rows[:max_groups]:
            lines.append(f"▸ save {_fmt(saved)} · {_fmt(size)} × {len(paths)}")
            for p in paths[:6]:
                lines.append(f"    {Path(p).relative_to(root) if Path(p).is_relative_to(root) else p}"[:90])
            if len(paths) > 6:
                lines.append(f"    … {len(paths) - 6} more")
        if len(rows) > max_groups:
            lines.append(f"… {len(rows) - max_groups} more groups")
        if capped:
            lines.append("(scan hit its cap — partial results)")

        _show("\n".join(lines))
        return (f"{len(rows)} duplicate group(s) under {root.name} — about "
                f"{_fmt(reclaim)} could be freed. Nothing was deleted; the "
                f"paths are on screen.")
    except Exception as e:
        return "Sir, the duplicate finder failed: " + str(e)
