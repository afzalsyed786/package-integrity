import re

CODES = {"red": 31, "green": 32, "yellow": 33, "blue": 34, "magenta": 35, "cyan": 36}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def colorize(text: str, color: str, bold: bool = False) -> str:
    code = CODES.get(color)
    if code is None:
        raise ValueError(f"unknown colour {color!r}")
    prefix = f"\x1b[1;{code}m" if bold else f"\x1b[{code}m"
    return f"{prefix}{text}\x1b[0m"


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)
