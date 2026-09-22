"""
JARVIS plugin — Unit converter.

"5 miles in km", "180 fahrenheit kaç santigrat", "how much is 2.5 cups in
ml", "150 lb to kg" — arithmetic the model should never do itself.

WHY THE MATH LIVES HERE
-----------------------
Language models are excellent at deciding WHAT the user asked and terrible
at multiplying 150 by 0.45359237. One wrong digit in a recipe or a dose is
worse than no answer, so the model extracts (value, from, to) and this file
does the multiplication against a fixed table. The table is data, the
formulas are three lines, and the answer is exact every time.

TEMPERATURE IS THE EXCEPTION
----------------------------
Celsius↔Fahrenheit↔Kelvin are affine, not multiplicative — a scale factor
alone would turn 0°C into a plausible-looking wrong number. They are their
own branch with the real formulas, because getting boiling point wrong is
the kind of error that looks right.

NO CURRENCIES, ON PURPOSE
--------------------------
Exchange rates move by the minute; a table baked into a plugin file would
be quietly wrong the day after release. Rates need a live feed, which is
the web-research tool's job — ask for a conversion of money THERE, and ask
for length, mass, temperature and friends HERE.

FOR EVERYONE: standard library only, no keys, no setup. Works in every
language: the model fills the fields, the units match on their common
symbols and names (km, kilometer, kilometre all land on the same row).
"""
from __future__ import annotations

PLUGIN = {
    "name": "unit_converter",
    "description": (
        "Converts between units of measure with exact arithmetic: length, "
        "mass, temperature, volume, area, speed, time, data size, pressure, "
        "energy and angle. Use for: '5 miles in km', '180 fahrenheit kaç "
        "santigrat', '2.5 cups to ml', 'how long is 3 feet in meters', "
        "'convert 150 pounds to kilos', '90 minutes in hours'. Extract the "
        "number, the source unit and the target unit from what the user said "
        "and pass them as value/from/to — common names and symbols both work "
        "(km/kilometer/kilometre). Do NOT use for currencies (live rates — "
        "use web research) or for pure arithmetic that is not a unit "
        "conversion."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "value": {
                "type": "NUMBER",
                "description": "The number to convert (may be negative, e.g. "
                               "for Celsius).",
            },
            "from_unit": {
                "type": "STRING",
                "description": "Source unit as the user said it: 'miles', "
                               "'mi', 'kg', 'celsius', '°F', 'cups'…",
            },
            "to_unit": {
                "type": "STRING",
                "description": "Target unit, same style as from_unit.",
            },
        },
        "required": ["value", "from_unit", "to_unit"],
    },
}

# (dimension, factor-to-base). Aliases are lowercase without spaces/symbols.
# Base units: meter, gram, square-meter, liter, m/s, second, byte, pascal,
# joule, radian. Temperature is handled separately below.
_UNITS: dict[str, tuple[str, float]] = {}


def _u(dim: str, base: float, *names: str) -> None:
    for n in names:
        _UNITS[n] = (dim, base)


_u("length", 1.0,
   "m", "meter", "meters", "metre", "metres",
   "km", "kilometer", "kilometers", "kilometre", "kilometres",
   "cm", "centimeter", "centimeters", "centimetre", "centimetres",
   "mm", "millimeter", "millimeters", "millimetre", "millimetres",
   "mi", "mile", "miles", "yard", "yards", "yd",
   "ft", "foot", "feet", "inch", "inches", "in",
   "nmi", "nauticalmile", "nauticalmiles")
_UNITS["km"] = _UNITS["kilometer"] = _UNITS["kilometers"] = \
    _UNITS["kilometre"] = _UNITS["kilometres"] = ("length", 1000.0)
_UNITS["cm"] = _UNITS["centimeter"] = _UNITS["centimeters"] = \
    _UNITS["centimetre"] = _UNITS["centimetres"] = ("length", 0.01)
_UNITS["mm"] = _UNITS["millimeter"] = _UNITS["millimeters"] = \
    _UNITS["millimetre"] = _UNITS["millimetres"] = ("length", 0.001)
_UNITS["mi"] = ("length", 1609.344)
_UNITS["mile"] = _UNITS["miles"] = ("length", 1609.344)
_UNITS["yard"] = _UNITS["yards"] = _UNITS["yd"] = ("length", 0.9144)
_UNITS["ft"] = _UNITS["foot"] = _UNITS["feet"] = ("length", 0.3048)
_UNITS["inch"] = _UNITS["inches"] = _UNITS["in"] = ("length", 0.0254)
_UNITS["nmi"] = _UNITS["nauticalmile"] = ("length", 1852)

_u("mass", 1.0,
   "g", "gram", "grams", "kg", "kilogram", "kilograms",
   "mg", "milligram", "milligrams",
   "t", "tonne", "tonnes", "metricton",
   "lb", "lbs", "pound", "pounds", "oz", "ounce", "ounces",
   "st", "stone", "stones")
_UNITS["kg"] = ("mass", 1000.0)
_UNITS["mg"] = ("mass", 0.001)
_UNITS["t"] = _UNITS["tonne"] = _UNITS["tonnes"] = ("mass", 1_000_000.0)
_UNITS["lb"] = _UNITS["lbs"] = _UNITS["pound"] = _UNITS["pounds"] = ("mass", 453.59237)
_UNITS["oz"] = _UNITS["ounce"] = _UNITS["ounces"] = ("mass", 28.349523125)
_UNITS["st"] = _UNITS["stone"] = _UNITS["stones"] = ("mass", 6350.29318)

_u("volume", 1.0,
   "l", "liter", "liters", "litre", "litres",
   "ml", "milliliter", "milliliters", "millilitre", "millilitres",
   "cl", "centiliter", "centilitre",
   "cup", "cups", "tbsp", "tablespoon", "tablespoons",
   "tsp", "teaspoon", "teaspoons",
   "gal", "gallon", "gallons", "qt", "quart", "pint", "pints", "pt",
   "floz", "fluidounce")
_UNITS["ml"] = ("volume", 0.001)
_UNITS["cl"] = ("volume", 0.01)
_UNITS["cup"] = _UNITS["cups"] = ("volume", 0.2365882365)
_UNITS["tbsp"] = _UNITS["tablespoon"] = _UNITS["tablespoons"] = ("volume", 0.0147867648)
_UNITS["tsp"] = _UNITS["teaspoon"] = _UNITS["teaspoons"] = ("volume", 0.0049289216)
_UNITS["gal"] = _UNITS["gallon"] = _UNITS["gallons"] = ("volume", 3.785411784)
_UNITS["qt"] = _UNITS["quart"] = ("volume", 0.946352946)
_UNITS["pint"] = _UNITS["pints"] = _UNITS["pt"] = ("volume", 0.473176473)
_UNITS["floz"] = _UNITS["fluidounce"] = ("volume", 0.0295735296)

_u("area", 1.0,
   "m2", "sqm", "squaremeter", "squaremeters", "squaremetre", "squaremetres",
   "km2", "sqkm", "hectare", "hectares", "ha",
   "acre", "acres", "ft2", "sqft", "squarefoot", "squarefeet",
   "mi2", "sqmi", "inch2", "sqin")
_UNITS["km2"] = _UNITS["sqkm"] = ("area", 1_000_000.0)
_UNITS["hectare"] = _UNITS["hectares"] = _UNITS["ha"] = ("area", 10_000.0)
_UNITS["acre"] = _UNITS["acres"] = ("area", 4046.8564224)
_UNITS["ft2"] = _UNITS["sqft"] = _UNITS["squarefoot"] = _UNITS["squarefeet"] = ("area", 0.09290304)
_UNITS["mi2"] = _UNITS["sqmi"] = ("area", 2_589_988.110336)

_u("speed", 1.0,
   "m/s", "mps", "meterpersecond", "km/h", "kph", "kmh",
   "kilometerperhour", "mph", "mileperhour", "knot", "knots", "kn")
_UNITS["km/h"] = _UNITS["kph"] = _UNITS["kmh"] = _UNITS["kilometerperhour"] = ("speed", 1 / 3.6)
_UNITS["mph"] = _UNITS["mileperhour"] = ("speed", 0.44704)
_UNITS["knot"] = _UNITS["knots"] = _UNITS["kn"] = ("speed", 0.514444444)

_u("time", 1.0,
   "s", "sec", "second", "seconds",
   "min", "minute", "minutes",
   "h", "hr", "hour", "hours",
   "day", "days", "d", "week", "weeks", "wk",
   "month", "months", "year", "years", "yr")
_UNITS["min"] = _UNITS["minute"] = _UNITS["minutes"] = ("time", 60.0)
_UNITS["h"] = _UNITS["hr"] = _UNITS["hour"] = _UNITS["hours"] = ("time", 3600.0)
_UNITS["day"] = _UNITS["days"] = _UNITS["d"] = ("time", 86400.0)
_UNITS["week"] = _UNITS["weeks"] = _UNITS["wk"] = ("time", 604800.0)
_UNITS["month"] = _UNITS["months"] = ("time", 2_629_800.0)
_UNITS["year"] = _UNITS["years"] = _UNITS["yr"] = ("time", 31_557_600.0)

_u("data", 1.0,
   "b", "byte", "bytes", "kb", "kilobyte", "kilobytes",
   "mb", "megabyte", "megabytes", "gb", "gigabyte", "gigabytes",
   "tb", "terabyte", "terabytes", "pb", "petabyte",
   "bit", "bits", "kib", "mib", "gib")
_UNITS.update({
    "bit": ("data", 0.125), "bits": ("data", 0.125),
    "kb": ("data", 1e3), "kilobyte": ("data", 1e3), "kilobytes": ("data", 1e3),
    "kib": ("data", 1024.0),
    "mb": ("data", 1e6), "megabyte": ("data", 1e6), "megabytes": ("data", 1e6),
    "mib": ("data", 1048576.0),
    "gb": ("data", 1e9), "gigabyte": ("data", 1e9), "gigabytes": ("data", 1e9),
    "gib": ("data", 1073741824.0),
    "tb": ("data", 1e12), "terabyte": ("data", 1e12), "terabytes": ("data", 1e12),
    "pb": ("data", 1e15), "petabyte": ("data", 1e15),
})

_u("pressure", 1.0,
   "pa", "pascal", "pascals", "kpa", "bar", "bars", "mbar",
   "atm", "psi", "torr", "mmhg")
_UNITS["kpa"] = ("pressure", 1000.0)
_UNITS["mbar"] = ("pressure", 100.0)
_UNITS["bar"] = ("pressure", 100_000.0)
_UNITS["atm"] = ("pressure", 101_325.0)
_UNITS["psi"] = ("pressure", 6894.757293168)
_UNITS["torr"] = ("pressure", 133.3223684211)
_UNITS["mmhg"] = ("pressure", 133.322387415)

_u("energy", 1.0,
   "j", "joule", "joules", "kj", "kilojoule", "kilojoules",
   "cal", "calorie", "calories", "kcal", "kilocalorie", "kilocalories",
   "wh", "kwh", "btu", "ev")
_UNITS["kj"] = _UNITS["kilojoule"] = _UNITS["kilojoules"] = ("energy", 1000.0)
_UNITS["cal"] = _UNITS["calorie"] = _UNITS["calories"] = ("energy", 4.184)
_UNITS["kcal"] = _UNITS["kilocalorie"] = _UNITS["kilocalories"] = ("energy", 4184.0)
_UNITS["wh"] = ("energy", 3600.0)
_UNITS["kwh"] = ("energy", 3_600_000.0)
_UNITS["btu"] = ("energy", 1055.05585262)
_UNITS["ev"] = ("energy", 1.602176634e-19)

_u("angle", 1.0,
   "rad", "radian", "radians", "deg", "degree", "degrees",
   "°", "grad", "gradians", "turn", "turns", "arcmin", "arcsec")
_UNITS["deg"] = _UNITS["degree"] = _UNITS["degrees"] = _UNITS["°"] = ("angle", 0.017453292519943295)
_UNITS["grad"] = _UNITS["gradians"] = ("angle", 0.015707963267948967)
_UNITS["turn"] = _UNITS["turns"] = ("angle", 6.283185307179586)
_UNITS["arcmin"] = ("angle", 0.0002908882086657216)
_UNITS["arcsec"] = ("angle", 4.84813681109536e-6)

# Symbols the model may pass with the ° prefix or plural noise already stripped.
_ALIASES = {
    "°c": "celsius", "°f": "fahrenheit", "°k": "kelvin", "c": "celsius",
    "f": "fahrenheit", "k": "kelvin", "centigrade": "celsius",
    "°": "deg",
}

_TEMPS = {"celsius": "C", "c": "C", "centigrade": "C",
          "fahrenheit": "F", "f": "F",
          "kelvin": "K", "k": "K"}


def _norm_unit(raw: str) -> str:
    s = str(raw or "").strip().lower().replace(" ", "")
    s = s.replace("²", "2").replace("·", "").replace("*", "").replace("/", "")
    return _ALIASES.get(s, s)


def _lookup(raw: str):
    """Resolve a unit string to (dimension, factor) or a temp letter, or None."""
    key = _norm_unit(raw)
    if key in _TEMPS:
        return ("temp", _TEMPS[key])
    if key in _UNITS:
        return _UNITS[key]
    # plural fallback: "kilometers" → "kilometer" already in table; try
    # stripping a trailing s the model may have left on an unknown form
    if key.endswith("s") and key[:-1] in _UNITS:
        return _UNITS[key[:-1]]
    if key.endswith("s") and key[:-1] in _TEMPS:
        return ("temp", _TEMPS[key[:-1]])
    return None


def _to_c(v: float, letter: str) -> float:
    return v if letter == "C" else (v - 32) * 5 / 9 if letter == "F" else v - 273.15


def _from_c(c: float, letter: str) -> float:
    return c if letter == "C" else c * 9 / 5 + 32 if letter == "F" else c + 273.15


def _pretty(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.6g}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        try:
            value = float(parameters.get("value"))
        except (TypeError, ValueError):
            return "I need a number to convert — tell me the value first."

        src = _lookup(str(parameters.get("from_unit") or ""))
        dst = _lookup(str(parameters.get("to_unit") or ""))
        if src is None:
            return (f"I don't know the unit '{parameters.get('from_unit')}'. "
                    f"Say it like 'miles', 'kg' or 'celsius'.")
        if dst is None:
            return (f"I don't know the unit '{parameters.get('to_unit')}'. "
                    f"Say it like 'km', 'pounds' or 'fahrenheit'.")

        if src[0] == "temp" and dst[0] == "temp":
            out = _from_c(_to_c(value, src[1]), dst[1])
        elif src[0] == "temp" or dst[0] == "temp":
            return "Both units have to be temperatures (C, F or K)."
        elif src[0] != dst[0]:
            return (f"'{parameters.get('from_unit')}' and "
                    f"'{parameters.get('to_unit')}' measure different things "
                    f"— I can't turn one into the other.")
        else:
            out = value * src[1] / dst[1]

        from_u = str(parameters.get("from_unit") or "").strip()
        to_u = str(parameters.get("to_unit") or "").strip()
        line = f"{_pretty(value)} {from_u} = {_pretty(out)} {to_u}"

        if player:
            try:
                player.show_content("📐 UNIT CONVERTER", line)
            except Exception:
                pass
        return line
    except Exception as e:
        return "Sir, the conversion failed: " + str(e)
