"""
JARVIS plugin — CSV analyzer.

"what's in this csv", "sum the amount column", "kaç satır var bu dosyada"
— row/column counts, headers, and numeric column statistics for a CSV,
read with the standard library's csv module.

WHY IT EXISTS
-------------
Spreadsheets lie by default: Excel shows you the first screen and trusts
you about the rest. This reads every row (up to a cap), reports what the
file actually contains — shape, headers, per-column min/max/mean for
numeric columns, empty counts, and a few sample rows — so "the data looks
fine" is a measurement rather than a hope.

IT NEVER WRITES
---------------
Analysis only. Transforming or exporting belongs to excel_writer and the
file tools; a plugin that "helpfully cleaned" a dataset would be editing
the user's source of truth.

DELIMITER AUTO-DETECTION
------------------------
Comma, semicolon, tab and pipe are sniffed from the first few KB — the
semicolon CSVs that Excel produces in much of Europe are the usual trap.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import csv
import io

PLUGIN = {
    "name": "csv_analyzer",
    "description": (
        "Reads a CSV file and reports its shape: headers, row count, "
        "numeric column stats (min/max/mean), empty cells, and sample "
        "rows. Use for: 'what's in this csv', 'summarize this file', "
        "'how many rows does it have', 'describe the amount column', 'bu "
        "csv'de ne var'. Pass the file `path` (absolute, or relative to "
        "the user's home). Read-only — never modifies the file. NOT for "
        "generating spreadsheets (excel_writer), NOT for JSON (json_tool), "
        "NOT when the 'CSV' is actually tab-separated Excel paste into a "
        ".txt you haven't confirmed."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {"type": "STRING", "description": "Path to the .csv file."},
            "rows_shown": {
                "type": "INTEGER",
                "description": "Sample rows to display (default 5, max 20).",
            },
        },
        "required": ["path"],
    },
}

_MAX_ROWS = 100_000
_MAX_BYTES = 20_000_000
_SNIFF_BYTES = 8192


def _detect(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        # Fallback: whichever shows up most in the header line.
        header = sample.splitlines()[0] if sample else ","
        counts = {d: header.count(d) for d in ",;\t|"}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def _stats(values: list[str]) -> str | None:
    nums = []
    empty = 0
    for v in values:
        v = v.strip().replace(",", "") if v.count(",") == 1 and \
            v.replace(",", "").replace(".", "").replace("-", "").isdigit() else v.strip()
        if not v:
            empty += 1
            continue
        try:
            nums.append(float(v))
        except ValueError:
            pass
    if not nums:
        return None
    return (f"min {min(nums):g} · max {max(nums):g} · "
            f"mean {sum(nums) / len(nums):g}"
            + (f" · {empty} empty" if empty else ""))


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(body: str) -> None:
        if player:
            try:
                player.show_content("📊 CSV", body)
            except Exception:
                pass

    from pathlib import Path

    try:
        raw_path = str(parameters.get("path") or "").strip()
        if not raw_path:
            return "Give me the path to a CSV file."
        path = Path(raw_path).expanduser()
        if not path.is_file():
            return f"No file at '{raw_path}'."
        if path.stat().st_size > _MAX_BYTES:
            return (f"That file is {path.stat().st_size / 1e6:.0f} MB — over the "
                    f"{_MAX_BYTES // 1_000_000} MB cap for analysis. Slice it "
                    f"first.")

        try:
            rows_shown = int(parameters.get("rows_shown") or 5)
        except (TypeError, ValueError):
            rows_shown = 5
        rows_shown = max(1, min(rows_shown, 20))

        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if not text.strip():
            return "That file is empty."

        delim = _detect(text[:_SNIFF_BYTES])
        reader = csv.reader(io.StringIO(text), delimiter=delim)

        header = next(reader, None)
        if not header:
            return "No header row found — is this really a CSV?"

        body: list[list[str]] = []
        truncated = False
        for row in reader:
            body.append(row)
            if len(body) >= _MAX_ROWS:
                truncated = True
                break

        n_cols = len(header)
        # Pad ragged rows so column indices line up — CSVs from hand edits
        # are often short by a cell.
        for row in body:
            row.extend([""] * (n_cols - len(row)))

        lines = [f"{path.name}",
                 f"Delimiter: {repr(delim)} · {len(body)} data rows × "
                 f"{n_cols} columns",
                 ""]

        # Per-column stats for the first 15 columns (panel real estate).
        for i, name in enumerate(header[:15]):
            col = [row[i] for row in body]
            st = _stats(col)
            line = f"{name[:24]:<24} {st or 'text'}"
            lines.append(line)
        if n_cols > 15:
            lines.append(f"… {n_cols - 15} more columns")
        lines.append("")
        lines.append("SAMPLE")
        lines.append(delim.join(header)[:100])
        for row in body[:rows_shown]:
            lines.append(delim.join(row)[:100])
        if truncated:
            lines.append(f"(capped at {_MAX_ROWS} rows)")

        _show("\n".join(lines))

        numeric_cols = sum(
            1 for i in range(n_cols)
            if _stats([row[i] for row in body[:1000]]) is not None)
        return (f"{path.name}: {len(body)} rows × {n_cols} columns, "
                f"{numeric_cols} numeric. Headers: "
                + ", ".join(header[:6])
                + ("…" if n_cols > 6 else "")
                + ". Stats and samples on screen.")
    except Exception as e:
        return "Sir, the CSV analyzer failed: " + str(e)
