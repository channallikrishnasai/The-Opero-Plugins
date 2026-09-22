"""
JARVIS plugin — Text statistics.

"how many words is this paragraph", "kaç karakter", "reading time for my
essay" — counts, densities and estimated read/speak times for any chunk
of text the user pastes or the model is holding.

WHY COUNT IN CODE
-----------------
Word boundaries differ per language (Chinese has no spaces; Turkish
attaches suffixes), and "is this short enough for a tweet" needs the same
answer twice in a row. Code counts codepoints and whitespace runs the
same way every time; the numbers go on the panel where they can be
compared side by side.

WHAT IT REPORTS
---------------
Characters (with/without spaces), words, sentences, paragraphs, unique-
word ratio (a rough lexical-diversity signal), estimated reading time
(~200 wpm in the reader's language — treated as an estimate, not a
measurement) and speaking time (~130 wpm).

It does not grade style. Tone and clarity are the model's job in the
conversation; this file only measures.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

PLUGIN = {
    "name": "text_stats",
    "description": (
        "Counts words, characters, sentences and paragraphs in a piece of "
        "text and estimates reading/speaking time. Use for: 'how many words "
        "is this', 'is this under 280 characters', 'kaç kelime var', "
        "'reading time for this essay', 'how long to read this aloud'. Pass "
        "the full text in `text`. You may summarize the numbers yourself "
        "for a quick answer — call the tool when exact figures or the panel "
        "are wanted. NOT a grammar checker, NOT a summarizer (do that "
        "yourself), NOT translation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "text": {
                "type": "STRING",
                "description": "The text to measure, verbatim.",
            },
        },
        "required": ["text"],
    },
}

_READ_WPM = 200
_SPEAK_WPM = 130
_MAX_LEN = 200_000


def _sentences(text: str) -> int:
    # End punctuation + newline-ish splits; good enough as a count, and the
    # docstring says estimates where they are estimates.
    n = 0
    for chunk in text.replace("!", ".").replace("?", ".").split("."):
        if chunk.strip():
            n += 1
    return max(n, text.count("\n\n") + 1 if text.strip() else 0)


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        text = str(parameters.get("text") or "")
        if not text.strip():
            return "There's no text to measure."
        if len(text) > _MAX_LEN:
            text = text[:_MAX_LEN]
            truncated = True
        else:
            truncated = False

        chars = len(text)
        chars_ns = sum(1 for c in text if not c.isspace())
        words = text.split()
        n_words = len(words)
        paras = len([p for p in text.split("\n\n") if p.strip()])
        sents = _sentences(text)
        uniq = len({w.casefold().strip(".,!?;:'\"()[]") for w in words})
        lexical = (uniq / n_words * 100) if n_words else 0.0

        read_s = n_words / _READ_WPM * 60
        speak_s = n_words / _SPEAK_WPM * 60

        def mmss(sec: float) -> str:
            sec = max(0, int(round(sec)))
            return f"{sec // 60}:{sec % 60:02d}"

        longest = max(words, key=len) if words else ""
        lines = [
            f"Words           {n_words}",
            f"Characters      {chars}  ({chars_ns} without spaces)",
            f"Sentences       {sents}",
            f"Paragraphs      {paras}",
            f"Unique words    {uniq}  ({lexical:.0f}%",
            f"                    lexical diversity)",
            f"Reading time    ~{mmss(read_s)}  (at {_READ_WPM} wpm)",
            f"Speaking time   ~{mmss(speak_s)}  (at {_SPEAK_WPM} wpm)",
        ]
        if longest:
            lines.append(f"Longest word    {longest}")
        if truncated:
            lines.append("(text truncated at 200k characters)")

        if player:
            try:
                player.show_content("🔤 TEXT STATS", "\n".join(lines))
            except Exception:
                pass

        return (f"{n_words} words, {chars} characters, {sents} sentences. "
                f"~{mmss(read_s)} to read, ~{mmss(speak_s)} to say. "
                f"Details on screen.")
    except Exception as e:
        return "Sir, the text stats failed: " + str(e)
