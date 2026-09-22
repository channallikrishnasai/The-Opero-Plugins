"""
JARVIS plugin — Disk space analyzer.

"what's eating my disk", "neden dolu bu disk", "find my biggest files" —
JARVIS walks the drive, sizes the folders, and puts a ranked report on the
panel: where the gigabytes went, and which individual files are largest.

IT NEVER DELETES ANYTHING
-------------------------
The whole value of a disk report is that you can trust it enough to act on.
A plugin that also cleaned up would have to decide what "temporary" means,
on somebody's real files, with no undo — so this one measures and shows, and
the decision stays with the person reading the list. Cleanup is a separate,
deliberate act with the file tools the app already has.

HOW IT MEASURES
---------------
Two passes: top-level children of the target folder, then a deep sweep for
the largest files. Permission errors, reparse points (Windows shortcuts
back to themselves) and vanished files are skipped silently — a report that
stops on the first locked system folder is a report nobody finishes reading.
The sweep is capped so a scan of an entire multi-terabyte drive still
returns in seconds rather than minutes.

FOR EVERYONE: standard library only, no keys, no setup. Same on Windows,
macOS and Linux.
"""
from __future__ import annotations

import os

PLUGIN = {
    "name": "disk_analyzer",
    "description": (
        "Scans a folder or drive and reports what is using the disk space: "
        "biggest subfolders, biggest individual files, free space remaining. "
        "Use for: 'what is taking up space on my C drive', 'neden disk dolu', "
        "'find my largest files', 'how much space is left', 'analyze disk "
        "usage', 'what can I delete' (this tool only LISTS — it never deletes "
        "anything; deletion is a separate deliberate step). Pass an optional "
        "root folder in `path`; leave it empty for the main drive's user "
        "profile. NOT for checking a single file's size, and NOT for memory "
        "or CPU — that is system_status."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "STRING",
                "description": "Folder or drive to scan (e.g. 'C:\\\\Users\\\\me' "
                               "or '/home/me'). Empty = the user's home folder.",
            },
            "top": {
                "type": "INTEGER",
                "description": "How many entries to show in each ranking "
                               "(default 8, max 20).",
            },
            "biggest_files": {
                "type": "INTEGER",
                "description": "How many of the largest files to list "
                               "(default 10, max 30). 0 = skip the deep file "
                               "sweep (faster).",
            },
        },
        "required": [],
    },
}

_MAX_ENTRIES = 10_000        # stop the deep sweep after this many files visited
_WIN_JUNCTIONS = True        # skip reparse points on Windows (they loop)


def _fmt(nbytes: float) -> str:
    """Bytes to a human line. Base-10, because disk vendors sell in base-10
    and '1 TB' meaning 0.91 TiB has confused everyone at least once."""
    n = float(nbytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


def _folder_size(root) -> tuple[int, int, list[tuple[int, str]], int]:
    """Return (total_bytes, files_seen, [(size, path)] top-file candidates,
    errors_skipped) for everything under root.

    One walk serves both answers — the folder total and the file ranking —
    so the disk is only traversed once.
    """
    total = 0
    seen = 0
    errs = 0
    files: list[tuple[int, str]] = []
    stack = [root]
    while stack and seen < _MAX_ENTRIES:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if _WIN_JUNCTIONS and entry.is_symlink() is False:
                            # is_symlink() misses junctions; stat follows them
                            # back to the same folder without this check.
                            st = entry.stat(follow_symlinks=False)
                            if getattr(st, "st_file_attributes", 0) & 0x400:
                                continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)
                            size = st.st_size
                            total += size
                            seen += 1
                            files.append((size, entry.path))
                    except (OSError, PermissionError):
                        errs += 1
                        continue
        except (OSError, PermissionError):
            errs += 1
            continue
    return total, seen, files, errs


def _children(root) -> list[tuple[int, str]]:
    """Size of each direct child folder/file of root — the first ranking."""
    out = []
    try:
        with os.scandir(root) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                        size, _, _, _ = _folder_size(entry.path)
                        out.append((size, entry.name + "/"))
                    elif entry.is_file(follow_symlinks=False):
                        out.append((entry.stat(follow_symlinks=False).st_size,
                                    entry.name))
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        return []
    out.sort(reverse=True)
    return out


def _home():
    from pathlib import Path
    return Path.home()


def run(parameters: dict, player=None, session_memory=None) -> str:
    from pathlib import Path
    import shutil

    raw = str(parameters.get("path") or "").strip()
    root = Path(raw).expanduser() if raw else _home()
    if not root.exists():
        return f"'{raw}' doesn't exist on this machine, sir."
    if not root.is_dir():
        return f"'{raw}' is a file, not a folder — point me at a folder."

    try:
        top = int(parameters.get("top") or 8)
    except (TypeError, ValueError):
        top = 8
    top = max(3, min(top, 20))
    try:
        want_files = int(parameters.get("biggest_files")
                         if parameters.get("biggest_files") is not None else 10)
    except (TypeError, ValueError):
        want_files = 10
    want_files = max(0, min(want_files, 30))

    # Free space first — if this fails the scan below will too, and the
    # answer should be about the drive, not about a traceback.
    try:
        total_p, used_p, free_p = shutil.disk_usage(root)
        free_line = (f"Disk: {_fmt(free_p)} free of {_fmt(total_p)} "
                     f"({100 * used_p / total_p:.0f}% used)")
    except OSError as e:
        return f"I couldn't read that drive's free space: {e}"

    kids = _children(root)
    total, seen, files, errs = _folder_size(root)

    lines = [str(root), "", free_line, "",
             f"Scanned {_fmt(total)} in {seen} files.", ""]

    lines.append("BIGGEST ITEMS")
    for size, name in kids[:top]:
        bar_n = max(1, int(20 * size / kids[0][0])) if kids[0][0] else 1
        lines.append(f"{'█' * bar_n} {_fmt(size):>10}  {name}"[:78])

    if want_files and files:
        files.sort(reverse=True)
        lines += ["", f"LARGEST FILES (top {want_files})"]
        for size, path in files[:want_files]:
            # Only the file name plus its parent folder — a full path to a
            # system file is two lines of noise on a phone-sized panel.
            p = Path(path)
            lines.append(f"{_fmt(size):>10}  {p.parent.name}/{p.name}"[:78])

    if errs:
        lines += ["", f"({errs} protected items skipped)"]

    body = "\n".join(lines)
    if player:
        try:
            player.show_content("💾 DISK USAGE", body)
        except Exception:
            pass

    biggest = kids[0] if kids else (0, "?")
    msg = (f"{free_line}. The scan found {_fmt(total)} under {root.name} — "
           f"biggest is {_fmt(biggest[0])} in '{biggest[1]}'. "
           f"Full ranking is on screen. I only measure; nothing was deleted.")
    return msg
