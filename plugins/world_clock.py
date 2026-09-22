"""
JARVIS plugin — World clock.

"what time is it in Tokyo", "London ve New York saat kaçta", "how many
hours left before it's 9am in San Francisco" — current time in the cities
that matter to the person asking.

HOW IT WORKS
------------
Python's zoneinfo (standard library since 3.9) holds the real IANA time
zone database — the same one the operating system uses — including DST
rules that change twice a year. Nothing here hardcodes offsets: an offset
for Tokyo in January is wrong in July, and a table of offsets would rot
the week after release.

The city list is a small convenience map for the names people actually
say. Anything else the model can pass as a full zone id
(Europe/Istanbul, America/Sao_Paulo…), which is how every zone on earth
is reachable without this file knowing all of them.

FOR EVERYONE: no keys, no setup, no network. Same on Windows, macOS and
Linux. Windows needs tzdata installed if the OS doesn't ship it — the
plugin says so plainly if zoneinfo can't find a zone.
"""
from __future__ import annotations

from datetime import datetime, timedelta

PLUGIN = {
    "name": "world_clock",
    "description": (
        "Current time in world cities/time zones, plus simple 'hours until' "
        "math across zones. Use for: 'what time is it in Tokyo', 'London'da "
        "saat kaç', 'list my world clock', 'how long until 9am in New "
        "York', 'convert now to Sydney time'. Pass city names or IANA zone "
        "ids in `zones` (comma-separated), defaulting to the saved list. "
        "For scheduling a FUTURE meeting at a specific time, still use this "
        "to check the zones, then say the answer plainly — for reminders "
        "use the reminder tool. NOT for date arithmetic (date_calculator) "
        "or unit conversions."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "zones": {
                "type": "STRING",
                "description": "Comma-separated cities or zone ids — 'Tokyo, "
                               "New York, Europe/Istanbul'. Empty = the "
                               "user's saved default list.",
            },
            "action": {
                "type": "STRING",
                "enum": ["now", "set_default"],
                "description": "'now' (default) shows current times; "
                               "'set_default' saves `zones` as the list "
                               "shown when none is passed.",
            },
        },
        "required": [],
    },
}

_STATE = "world_clock_zones"

_CITIES = {
    "istanbul": "Europe/Istanbul", "london": "Europe/London",
    "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "madrid": "Europe/Madrid", "rome": "Europe/Rome",
    "moscow": "Europe/Moscow", "kyiv": "Europe/Kyiv",
    "dubai": "Asia/Dubai", "dubai city": "Asia/Dubai",
    "karachi": "Asia/Karachi", "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata", "bangalore": "Asia/Kolkata",
    "colombo": "Asia/Colombo", "dhaka": "Asia/Dhaka",
    "kathmandu": "Asia/Kathmandu", "bangkok": "Asia/Bangkok",
    "jakarta": "Asia/Jakarta", "singapore": "Asia/Singapore",
    "kuala lumpur": "Asia/Kuala_Lumpur", "hong kong": "Asia/Hong_Kong",
    "shanghai": "Asia/Shanghai", "beijing": "Asia/Shanghai",
    "shenzhen": "Asia/Shanghai", "taipei": "Asia/Taipei",
    "seoul": "Asia/Seoul", "tokyo": "Asia/Tokyo", "osaka": "Asia/Tokyo",
    "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne",
    "auckland": "Pacific/Auckland", "dublin": "Europe/Dublin",
    "lisbon": "Europe/Lisbon", "athens": "Europe/Athens",
    "cairo": "Africa/Cairo", "lagos": "Africa/Lagos",
    "nairobi": "Africa/Nairobi", "johannesburg": "Africa/Johannesburg",
    "new york": "America/New_York", "nyc": "America/New_York",
    "boston": "America/New_York", "washington": "America/New_York",
    "toronto": "America/Toronto", "chicago": "America/Chicago",
    "houston": "America/Chicago", "denver": "America/Denver",
    "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles", "seattle": "America/Los_Angeles",
    "vancouver": "America/Vancouver", "mexico city": "America/Mexico_City",
    "bogota": "America/Bogota", "lima": "America/Lima",
    "santiago": "America/Santiago", "buenos aires": "America/Argentina/Buenos_Aires",
    "sao paulo": "America/Sao_Paulo", "rio": "America/Sao_Paulo",
    "honolulu": "Pacific/Honolulu", "alaska": "America/Anchorage",
    "reykjavik": "Atlantic/Reykjavik",
}

_DEFAULT = ["Istanbul", "London", "New York", "Tokyo"]


def _load_state() -> dict:
    try:
        from memory.config_manager import get_plugin_config
        return get_plugin_config("world_clock") or {}
    except Exception:
        return {}


def _save_state(values: dict) -> None:
    try:
        from memory.config_manager import save_plugin_config
        save_plugin_config("world_clock", values)
    except Exception:
        pass


def _resolve(name: str) -> str:
    """City nickname or zone id → zone id (best effort, lowercased key)."""
    key = name.strip()
    low = key.lower().replace("_", " ")
    if low in _CITIES:
        return _CITIES[low]
    # already a zone id like Europe/Istanbul or America/Argentina/Buenos_Aires
    if "/" in key:
        return key
    # try title-cased guess: "sanfrancisco" won't hit, but that's fine —
    # the model is asked to pass zone ids for uncommon places.
    return key


def _zone_names(raw: str) -> list[str]:
    saved = str(_load_state().get(_STATE) or "").strip()
    src = raw or saved or ", ".join(_DEFAULT)
    return [p.strip() for p in src.split(",") if p.strip()][:12]


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        action = str(parameters.get("action") or "now").strip().lower()
        raw = str(parameters.get("zones") or "").strip()

        if action == "set_default":
            if not raw:
                return "Give me the cities to save, like 'Istanbul, London, NYC'."
            _save_state({_STATE: raw[:300]})
            return f"World clock default list saved: {raw[:200]}."

        names = _zone_names(raw)
        rows = []
        local = datetime.now().astimezone()
        rows.append(f"You are {local.strftime('%Z (%z)')} · "
                    f"{local.strftime('%Y-%m-%d %H:%M')} local")

        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        for name in names:
            zid = _resolve(name)
            try:
                tz = ZoneInfo(zid)
            except (ZoneInfoNotFoundError, ValueError, KeyError):
                rows.append(f"?  {name} — unknown zone (try a city or "
                            f"Area/Location id)")
                continue
            now = datetime.now(tz)
            diff = (now.utcoffset() or timedelta(0)) - \
                   (local.utcoffset() or timedelta(0))
            delta_h = diff.total_seconds() / 3600
            rel = "same time as you" if abs(delta_h) < 0.01 else \
                (f"{delta_h:+g}h vs you")
            rows.append(f"{now.strftime('%H:%M')}  {name}  "
                        f"({now.strftime('%a %d %b')}, {rel})")

        body = "\n".join(rows)
        if player:
            try:
                player.show_content("🌍 WORLD CLOCK", body)
            except Exception:
                pass
        # Lead with the first requested zone so the spoken answer is short.
        first = rows[1] if len(rows) > 1 else rows[0]
        return f"World clock on screen. {first}."
    except ImportError:
        return ("This Python has no zoneinfo/tzdata. Run: pip install tzdata")
    except Exception as e:
        return "Sir, the world clock failed: " + str(e)
