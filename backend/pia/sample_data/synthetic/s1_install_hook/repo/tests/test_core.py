from colorfmt import colorize, strip_ansi


def test_roundtrip():
    assert strip_ansi(colorize("hi", "red")) == "hi"
