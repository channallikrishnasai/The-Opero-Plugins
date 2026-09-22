"""
JARVIS plugin — Bookmark manager.

"save this link for later", "bookmark github.com/… as the opero repo",
"what was that site about docker" — links kept in memory/bookmarks.json
with titles and tags, searchable by anything the user remembers about
them.

WHY BOOKMARKS AND NOT JUST THE BROWSER'S
-----------------------------------------
Browser bookmarks are trapped inside one browser profile on one machine,
invisible to the assistant that overheard you say "I'll send you that
article". A plain JSON list the model can search is worse than Chrome's
folders at pretty icons and better at every actual retrieval: by tag, by
half-remembered word, from anywhere in a conversation.

WHAT IT STORES
--------------
url, title, tags (free words), optional note, date saved. URLs are
sanitized to http/https only — a javascript: or file: payload smuggled
in through chat is dropped, because a link the assistant later "opens"
should never be a script.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "bookmarks.json"

PLUGIN = {
    "name": "bookmark_manager",
    "description": (
        "Saves, lists, searches and deletes personal bookmarks (URL + title "
        "+ tags). Use for: 'bookmark this link', 'save https://… for later', "
        "'what was that docker site I saved', 'list my bookmarks', 'delete "
        "the rakva bookmark', 'yer imlerim'. Pass `url`, `title`, `tags` "
        "(array of words) and for search a `query`. Only http/https URLs "
        "are accepted. NOT for opening tabs now (browser tools), NOT for "
        "notes without a link (journal), NOT for files (file tools)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["add", "search", "list", "delete"],
                "description": "'add' (default when url given), 'search', "
                               "'list' (max 30 shown), 'delete' by url or "
                               "query match.",
            },
            "url": {"type": "STRING", "description": "The link to save or delete."},
            "title": {"type": "STRING", "description": "Human title for the link."},
            "tags": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Free tags — 'docker', 'reference', 'opero'.",
            },
            "note": {"type": "STRING", "description": "Optional one-line why."},
            "query": {
                "type": "STRING",
                "description": "For search/delete: words to look for in "
                               "title, tags, note and url.",
            },
        },
        "required": [],
    },
}

_MAX = 1000


def _load() -> list[dict]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [b for b in data if isinstance(b, dict) and b.get("url")]
    except (OSError, ValueError):
        pass
    return []


def _save(rows: list[dict]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(rows[-_MAX:], ensure_ascii=False, indent=1),
                              encoding="utf-8")
    except OSError:
        pass


def _clean_url(raw: str) -> str | None:
    raw = str(raw or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    try:
        p = urlparse(raw)
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    # A host without a dot is almost certainly a typo or an intranet name
    # the user didn't mean to hand the assistant.
    if "." not in p.netloc and p.netloc.lower() != "localhost":
        return None
    return raw


def _norm(s: str) -> str:
    return " ".join(str(s or "").casefold().split())


def _matches(row: dict, q: str) -> bool:
    needle = _norm(q)
    if not needle:
        return False
    hay = " ".join(_norm(x) for x in
                   [row.get("title"), row.get("url"), row.get("note"),
                    " ".join(row.get("tags") or [])])
    return all(tok in hay for tok in needle.split())


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "").strip().lower()
        url = str(parameters.get("url") or "").strip()
        title = str(parameters.get("title") or "").strip()[:200]
        note = str(parameters.get("note") or "").strip()[:300]
        query = str(parameters.get("query") or "").strip()
        raw_tags = parameters.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = raw_tags.split(",")
        tags = [str(t).strip()[:40] for t in raw_tags if str(t).strip()][:12]

        rows = _load()
        if not action:
            action = "add" if url else ("search" if query else "list")

        if action == "add":
            clean = _clean_url(url)
            if not clean:
                return ("That doesn't look like an http(s) link I can save — "
                        "check the URL.")
            existing = next((r for r in rows if r["url"] == clean), None)
            if existing:
                existing["title"] = title or existing.get("title", "")
                if note:
                    existing["note"] = note
                if tags:
                    existing["tags"] = sorted(set(existing.get("tags") or []) | set(tags))
                _save(rows)
                return f"Updated bookmark: {existing.get('title') or clean}."
            row = {"url": clean, "title": title or clean,
                   "tags": tags, "note": note, "date": date.today().isoformat()}
            rows.append(row)
            _save(rows)
            return (f"Saved “{row['title']}”"
                    + (f" tagged {', '.join(tags)}" if tags else "")
                    + f". {len(rows)} bookmark(s) total.")

        if action == "delete":
            target = query or url
            if not target:
                return "Which bookmark should I delete?"
            hit = next((r for r in rows
                        if r["url"] == _clean_url(target) or _matches(r, target)), None)
            if not hit:
                return f"No bookmark matches '{target}'."
            rows.remove(hit)
            _save(rows)
            return f"Deleted “{hit.get('title') or hit['url']}”."

        if action in ("list", "show"):
            if not rows:
                return "No bookmarks saved yet."
            show = rows[-30:]
            body = "\n".join(
                f"{' · '.join(r.get('tags') or []) or '—'}\n"
                f"  {r.get('title') or r['url']}\n  {r['url']}".strip()
                for r in reversed(show))
            _show("🔖 BOOKMARKS", body)
            return f"{len(rows)} bookmark(s), latest {len(show)} on screen."

        # -------- SEARCH --------
        if not query:
            return "What should I look for in your bookmarks?"
        hits = [r for r in rows if _matches(r, query)]
        if not hits:
            return f"No bookmark matches '{query}'."
        if len(hits) == 1:
            h = hits[0]
            return f"{h.get('title') or h['url']} — {h['url']}" + \
                   (f"  ({h['note']})" if h.get("note") else "")
        body = "\n".join(f"{r.get('title') or r['url']}\n  {r['url']}"
                         for r in hits[:20])
        _show(f"🔖 {query.upper()}", body)
        return (f"{len(hits)} matches for '{query}'. First: "
                f"{hits[0].get('title') or hits[0]['url']} — {hits[0]['url']}")
    except Exception as e:
        return "Sir, the bookmark manager failed: " + str(e)
