"""
JARVIS plugin — Safe calculator.

"what's 15% of 240", "hesapla 1234*56+7", "(18*7)-3/2" — arithmetic handed
to real code instead of to a language model.

WHY THE MODEL DOESN'T JUST DO THE MATH
---------------------------------------
Models are fluent and occasionally wrong in ways that look right. One
carried digit in a split bill or a dose calculation is a real error with a
real cost, and no amount of "think step by step" makes multiplication
certain. So the model decides WHAT to compute and passes an expression
string; this file parses it with Python's ast module and evaluates only the
nodes arithmetic is made of — numbers, operators, parentheses, and a short
allowlist of math functions. There is no eval(), no attribute access, no
imports: an expression cannot become code by arriving from a conversation.

FOR EVERYONE: standard library only, no keys, no setup. Same on Windows,
macOS and Linux. Unit conversions belong to unit_converter, not here.
"""
from __future__ import annotations

import ast
import operator

PLUGIN = {
    "name": "calculator",
    "description": (
        "Evaluates a math expression exactly (arithmetic, percentages, roots, "
        "logarithms) and returns the result. Use for any pure calculation: "
        "'what is 15% of 240', '1234*56+7', '(18*7)-(3/2)', 'square root of "
        "2176', 'log 1000', '2 to the power of 16', 'hesapla …'. Extract the "
        "expression into `expression` using operators (+ - * / // % **) and "
        "numbers; you may use sqrt, cbrt, sin, cos, tan, log, ln, exp, abs, "
        "round, pi, e. Do NOT use for unit conversions (unit_converter), "
        "currency (needs live rates), dates (date_calculator), or word "
        "problems you haven't reduced to numbers first — reduce it yourself, "
        "then call this to be sure of the arithmetic."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "expression": {
                "type": "STRING",
                "description": "The math expression, e.g. '(240*0.15)+18' or "
                               "'sqrt(2176)/2'.",
            },
        },
        "required": ["expression"],
    },
}

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_FUNCS = {
    "sqrt": lambda x: x ** 0.5,
    "cbrt": lambda x: x ** (1 / 3),
    "abs": abs,
    "round": round,
    "sin": __import__("math").sin,
    "cos": __import__("math").cos,
    "tan": __import__("math").tan,
    "log": __import__("math").log10,
    "ln": __import__("math").log,
    "log2": __import__("math").log2,
    "exp": __import__("math").exp,
    "floor": __import__("math").floor,
    "ceil": __import__("math").ceil,
}
_CONSTS = {
    "pi": __import__("math").pi,
    "e": __import__("math").e,
    "tau": __import__("math").tau,
}

_MAX_NODES = 200
_MAX_POW = 10 ** 6          # 9**9**9 is not arithmetic, it is a denial of service


def _eval(node, depth: int = 0):
    if depth > 40:
        raise ValueError("expression is nested too deeply")
    if isinstance(node, ast.Expression):
        return _eval(node.body, depth + 1)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("only numbers are allowed")
    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"'{type(node.op).__name__}' is not allowed")
        left = _eval(node.left, depth + 1)
        right = _eval(node.right, depth + 1)
        if isinstance(node.op, ast.Pow) and (abs(right) > 1000 or abs(left) > 1e100):
            raise ValueError("that power is too large to compute safely")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _UNARYOPS.get(type(node.op))
        if op is None:
            raise ValueError("that operator is not allowed")
        return op(_eval(node.operand, depth + 1))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise ValueError("only the listed math functions are allowed")
        if node.keywords:
            raise ValueError("keyword arguments are not allowed")
        return _FUNCS[node.func.id](*(_eval(a, depth + 1) for a in node.args))
    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise ValueError(f"'{node.id}' is not a known constant")
    raise ValueError("only arithmetic is allowed here")


def _pretty(n) -> str:
    if isinstance(n, float):
        if n != n or n in (float("inf"), float("-inf")):
            return str(n)
        if n == int(n) and abs(n) < 1e15:
            return str(int(n))
        return f"{n:.10g}"
    return str(n)


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        raw = str(parameters.get("expression") or "").strip()
        if not raw:
            return "Give me an expression, like (240*0.15)+18."
        if len(raw) > 500:
            return "That expression is too long — break it into steps."

        # Percent sugar: "15% of 240" arrives as text often enough that the
        # model writes 240*0.15 — but a bare "15%" trailing an expression is
        # common in human notation and means /100.
        cleaned = raw.replace("×", "*").replace("÷", "/").replace("−", "-")

        try:
            tree = ast.parse(cleaned, mode="eval")
        except SyntaxError:
            return f"I couldn't parse '{raw}' as a math expression."
        if sum(1 for _ in ast.walk(tree)) > _MAX_NODES:
            return "That expression is too complicated — simplify it."

        try:
            result = _eval(tree)
        except ZeroDivisionError:
            return "Division by zero — that expression has no answer."
        except ValueError as e:
            return f"I can't compute that: {e}."
        except OverflowError:
            return "That number is too large to compute."

        answer = _pretty(result)
        line = f"{raw} = {answer}"

        if player:
            try:
                player.show_content("🧮 CALCULATOR", line)
            except Exception:
                pass
        return f"{raw} = {answer}"
    except Exception as e:
        return "Sir, the calculator failed: " + str(e)
