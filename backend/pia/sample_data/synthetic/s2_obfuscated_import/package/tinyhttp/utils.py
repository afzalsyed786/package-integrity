import re

_EXPR = re.compile(r"^[\d+\-*/(). ]+$")


def safe_math(expr: str) -> float:
    """Evaluate a purely arithmetic expression (baseline eval usage, present in source)."""
    if not _EXPR.match(expr):
        raise ValueError("only arithmetic is allowed")
    return eval(expr, {"__builtins__": {}}, {})
