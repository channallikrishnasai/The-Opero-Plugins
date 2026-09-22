"""
JARVIS plugin — Color toolbox.

"what's the hex for this rgb", "make a palette from #3366ff", "convert
#ff0000 to hsl", "accessible text color for this background" — color math
for designers, front-end devs, and anyone who has ever squinted at a
three-number RGB in a Figma comment.

WHY HERE
--------
Hex↔RGB↔HSL is arithmetic with off-by-one and 0–255 vs 0–100 traps that
models step on. Palette generation (complementary, analogous, triadic) is
a fixed geometric rule on the hue wheel — implement it once, get it right
forever. Relative luminance and the WCAG contrast ratio are published
formulas; "is this readable" deserves the real calculation, not a vibe.

NO EYEDROPPER
-------------
Reading a pixel off the screen needs a capture stack the app already has
elsewhere (screen tools); this plugin converts and composes colors you
already have in hand.

FOR EVERYONE: standard library only, no keys, no setup.
"""
from __future__ import annotations

import colorsys
import re

PLUGIN = {
    "name": "color_tool",
    "description": (
        "Converts colors between hex, RGB and HSL, generates harmonious "
        "palettes from a seed color, and checks WCAG contrast between "
        "foreground and background. Use for: 'hex for rgb(51,102,255)', "
        "'convert #ff0000 to hsl', 'make a palette from teal', 'what text "
        "color can I read on #1a1a2e', 'complementary color of gold'. Pass "
        "`color` (hex like #3366ff, or 'rgb(…)', or 'hsl(…)', or a common "
        "color name) and optionally `color2` for contrast, `mode` for the "
        "palette type. NOT for picking colors from the screen, NOT for "
        "image editing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["convert", "palette", "contrast"],
                "description": "convert (default) = all representations; "
                               "palette = harmony set from the seed; "
                               "contrast = WCAG ratio vs color2.",
            },
            "color": {
                "type": "STRING",
                "description": "Seed color: '#3366ff', 'rgb(51,102,255)', "
                               "'hsl(220,100%,60%)', or a name like 'teal'.",
            },
            "color2": {
                "type": "STRING",
                "description": "Second color for contrast checks (the "
                               "background, typically).",
            },
            "mode": {
                "type": "STRING",
                "enum": ["complementary", "analogous", "triadic", "split",
                         "monochrome"],
                "description": "Palette harmony (default complementary).",
            },
        },
        "required": ["color"],
    },
}

_NAMED = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0),
    "green": (0, 128, 0), "lime": (0, 255, 0), "blue": (0, 0, 255),
    "yellow": (255, 255, 0), "cyan": (0, 255, 255), "magenta": (255, 0, 255),
    "silver": (192, 192, 192), "gray": (128, 128, 128), "grey": (128, 128, 128),
    "maroon": (128, 0, 0), "olive": (128, 128, 0), "navy": (0, 0, 128),
    "teal": (0, 128, 128), "purple": (128, 0, 128), "orange": (255, 165, 0),
    "pink": (255, 192, 203), "brown": (165, 42, 42), "gold": (255, 215, 0),
    "coral": (255, 127, 80), "turquoise": (64, 224, 208),
    "indigo": (75, 0, 130), "violet": (238, 130, 238),
    "crimson": (220, 20, 60), "skyblue": (135, 206, 235),
}


def parse_color(raw: str) -> tuple[int, int, int]:
    s = str(raw or "").strip().lower()
    if s in _NAMED:
        return _NAMED[s]
    m = re.fullmatch(r"#?([0-9a-f]{6})", s)
    if m:
        h = m.group(1)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    m = re.fullmatch(r"#?([0-9a-f]{3})", s)
    if m:
        h = m.group(1)
        return tuple(int(c * 2, 16) for c in h)  # type: ignore
    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)", s)
    if m:
        return tuple(min(255, int(g)) for g in m.groups())  # type: ignore
    m = re.fullmatch(r"hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%"
                     r"(?:\s*,\s*[\d.]+\s*)?\)", s)
    if m:
        h, sat, lig = (float(g) for g in m.groups())
        r, g, b = colorsys.hls_to_rgb((h % 360) / 360, lig / 100, sat / 100)
        return round(r * 255), round(g * 255), round(b * 255)
    raise ValueError(f"couldn't read '{raw}' as a color")


def to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def to_hsl(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (c / 255 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s * 100, l * 100


def _lum(rgb: tuple[int, int, int]) -> float:
    """WCAG relative luminance."""
    def ch(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _shift_hue(rgb, delta: float):
    h, s, l = to_hsl(rgb)
    r, g, b = colorsys.hls_to_rgb(((h + delta) % 360) / 360, l / 100, s / 100)
    return round(r * 255), round(g * 255), round(b * 255)


def run(parameters: dict, player=None, session_memory=None) -> str:
    def _show(title: str, body: str) -> None:
        if player:
            try:
                player.show_content(title, body)
            except Exception:
                pass

    try:
        action = str(parameters.get("action") or "convert").strip().lower()
        try:
            rgb = parse_color(str(parameters.get("color") or ""))
        except ValueError as e:
            return str(e)

        h, s, l = to_hsl(rgb)
        hexv = to_hex(rgb)

        if action == "palette":
            mode = str(parameters.get("mode") or "complementary").strip().lower()
            deltas = {
                "complementary": [0, 180],
                "analogous": [0, -30, 30, -60, 60],
                "triadic": [0, 120, 240],
                "split": [0, 150, 210],
                "monochrome": [0, 0, 0],
            }.get(mode)
            if deltas is None:
                return f"Unknown palette mode '{mode}'."
            swatches = []
            lines = [f"seed {hexv} · {mode}", ""]
            if mode == "monochrome":
                for dl in (35, 20, 0, -15, -30):
                    hh, ss, ll = h, max(0, min(100, s)), max(0, min(100, l + dl))
                    r, g, b = colorsys.hls_to_rgb(hh / 360, ll / 100, ss / 100)
                    swatches.append((round(r * 255), round(g * 255), round(b * 255)))
            else:
                swatches = [_shift_hue(rgb, d) for d in deltas]
            for c in swatches:
                lines.append(f"{to_hex(c)}   rgb{c}")
            _show("🎨 PALETTE", "\n".join(lines))
            return ("Palette on screen: " + "  ".join(to_hex(c) for c in swatches))

        if action == "contrast":
            raw2 = str(parameters.get("color2") or "").strip()
            if not raw2:
                return "Give me the second color (usually the background)."
            try:
                rgb2 = parse_color(raw2)
            except ValueError as e:
                return str(e)
            ratio = contrast(rgb, rgb2)
            aa = "PASS" if ratio >= 4.5 else "FAIL"
            aaa = "PASS" if ratio >= 7 else "FAIL"
            body = (f"fg {hexv} on bg {to_hex(rgb2)}\n\n"
                    f"Ratio  {ratio:.2f}:1\n"
                    f"AA normal text     {aa} (≥4.5)\n"
                    f"AA large text      {'PASS' if ratio >= 3 else 'FAIL'} (≥3)\n"
                    f"AAA normal text    {aaa} (≥7)")
            _show("🎨 CONTRAST", body)
            verdict = ("readable" if ratio >= 4.5 else
                       "borderline — large text only" if ratio >= 3
                       else "not readable as normal text")
            return f"{hexv} on {to_hex(rgb2)}: {ratio:.2f}:1 — {verdict}. {aa} for AA."

        # convert (default)
        line = (f"{hexv}   rgb({rgb[0]}, {rgb[1]}, {rgb[2]})   "
                f"hsl({h:.0f}, {s:.0f}%, {l:.0f}%)")
        _show("🎨 COLOR", line)
        return line
    except Exception as e:
        return "Sir, the color tool failed: " + str(e)
