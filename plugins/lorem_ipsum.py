"""
JARVIS plugin — Lorem ipsum generator.

"give me three paragraphs of placeholder text", "lorem ipsum 50 words",
"doldurulacak metin ver" — classic dummy copy for layouts, mockups and
wireframes that need words with the right texture before the real ones
exist.

WHY LOREM RHYTHM MATTERS
-------------------------
Real-looking prose at the right density is what makes a design review
about spacing instead of about "test test test". The vocabulary below is
the traditional lorem set; sentences are assembled from a small grammar so
paragraphs don't repeat every line — enough variety for a mock, not a
Markov novel.

LANGUAGE SWITCH
---------------
English/Turkish word banks are offered as alternatives; the sentence
shapes stay the same and only the vocabulary swaps. This is filler, and
everyone reading it knows that.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import secrets

PLUGIN = {
    "name": "lorem_ipsum",
    "description": (
        "Generates placeholder text (lorem ipsum) in paragraphs, sentences "
        "or words for mockups and layout tests. Use for: 'give me lorem "
        "ipsum', 'three paragraphs of placeholder text', '50 words of dummy "
        "copy', 'doldurulacak metin'. Pass `count` and `unit` "
        "(paragraphs/sentences/words) and optional `language` ('la' "
        "traditional, 'en', 'tr'). NOT for generating real content — if "
        "they need actual copy, write it yourself; NOT translation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "unit": {
                "type": "STRING",
                "enum": ["paragraphs", "sentences", "words"],
                "description": "What `count` counts (default paragraphs).",
            },
            "count": {
                "type": "INTEGER",
                "description": "How many (default 3 paragraphs / 4 sentences "
                               "/ 50 words; max 50 paragraphs, 500 words).",
            },
            "language": {
                "type": "STRING",
                "description": "'la' (traditional lorem, default), 'en', or "
                               "'tr' for Turkish filler words.",
            },
        },
        "required": [],
    },
}

_LA = ("lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
       "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
       "et", "dolore", "magna", "aliqua", "enim", "ad", "minim", "veniam",
       "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi",
       "aliquip", "ex", "ea", "commodo", "consequat", "duis", "aute", "irure",
       "in", "reprehenderit", "voluptate", "velit", "esse", "cillum", "fugiat",
       "nulla", "pariatur", "excepteur", "sunt", "culpa", "qui", "officia",
       "deserunt", "mollit", "anim", "id", "est", "laborum", "vero", "eos",
       "accusamus", "iure", "odio", "dignissimos", "ducimus", "blanditiis",
       "praesentium", "voluptatum", "deleniti", "atque", "corrupti",
       "quos", "quas", "molestias", "excepturi", "occaecati", "cupiditate")

_EN = ("the", "quick", "sample", "layout", "needs", "words", "before", "real",
       "copy", "arrives", "design", "review", "flows", "better", "with",
       "texture", "than", "with", "grey", "bars", "and", "empty", "boxes",
       "spacing", "looks", "honest", "when", "lines", "wrap", "naturally",
       "across", "columns", "and", "cards", "team", "signs", "off", "faster",
       "when", "nothing", "distracts", "from", "the", "structure", "itself")

_TR = ("bu", "metin", "yer", "tutucudur", "tasarım", "sınaması", "için",
       "konulmuştur", "kelimeler", "gerçek", "olana", "dek", "burada",
       "bekler", "görünüm", "daha", "net", "olur", "satırlar", "doğru",
       "yerde", "kenetlendiğinde", "ekipler", "hızlı", "onay", "verir",
       "boş", "kutular", "yerine", "yazı", "dolsun", "istiyoruz",
       "düzen", "kendini", "göstersin", "diye", "bu", "cümleler", "var")

_BANKS = {"la": _LA, "en": _EN, "tr": _TR}


def _words(lang: str, n: int) -> list[str]:
    bank = _BANKS.get(lang) or _LA
    return [secrets.choice(bank) for _ in range(n)]


def _sentence(lang: str) -> str:
    # 6–14 content words, first capitalized, trailing period — lorem's shape.
    ws = _words(lang, 6 + secrets.randbelow(9))
    ws[0] = ws[0][:1].upper() + ws[0][1:]
    return " ".join(ws) + "."


def _paragraph(lang: str, min_sents: int = 3, max_sents: int = 6) -> str:
    n = min_sents + secrets.randbelow(max_sents - min_sents + 1)
    return " ".join(_sentence(lang) for _ in range(n))


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(body: str) -> None:
        if player:
            try:
                player.show_content("📜 LOREM IPSUM", body)
            except Exception:
                pass

    try:
        unit = str(parameters.get("unit") or "paragraphs").strip().lower()
        lang = str(parameters.get("language") or "la").strip().lower()
        if lang not in _BANKS:
            lang = "la"
        try:
            count = int(parameters.get("count") or
                        (50 if unit == "words" else 4 if unit == "sentences" else 3))
        except (TypeError, ValueError):
            count = 3

        if unit == "words":
            count = max(1, min(count, 500))
            text = " ".join(_words(lang, count))
            _show(text)
            return text if len(text) <= 400 else f"{count} words on screen."

        if unit == "sentences":
            count = max(1, min(count, 50))
            text = " ".join(_sentence(lang) for _ in range(count))
            _show(text)
            return text if len(text) <= 400 else f"{count} sentences on screen."

        if unit != "paragraphs":
            return "Unit must be paragraphs, sentences or words."
        count = max(1, min(count, 50))
        paras = [_paragraph(lang) for _ in range(count)]
        text = "\n\n".join(paras)
        _show(text)
        return (f"{count} paragraph(s), "
                f"{sum(len(p.split()) for p in paras)} words — on screen.")
    except Exception as e:
        return "Sir, the lorem generator failed: " + str(e)
