"""Source map parsing (VLQ decoding) and source-path resolution. Pure data parsing, no execution."""
import base64
import json
import posixpath
import re

B64 = {c: i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")}
MAP_URL = re.compile(r"[#@]\s*sourceMappingURL=([^\s'\"*]+)")
EXTERNAL = ("node_modules/", "webpack/bootstrap", "(webpack)", "webpack/runtime", "<", "\x00")


def decode_vlq(segment: str) -> list[int]:
    values, shift, value = [], 0, 0
    for ch in segment:
        digit = B64.get(ch)
        if digit is None:
            raise ValueError("invalid VLQ character")
        value += (digit & 31) << shift
        if digit & 32:
            shift += 5
        else:
            values.append(-(value >> 1) if value & 1 else value >> 1)
            value, shift = 0, 0
    return values


def mapped_lines(mappings: str) -> list[bool]:
    out = []
    for line in mappings.split(";"):
        mapped = False
        for seg in line.split(","):
            if seg and len(decode_vlq(seg)) >= 4:
                mapped = True
                break
        out.append(mapped)
    return out


def parse_map(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        return None
    return data


def find_map_reference(js_rel: str, js_text: str) -> tuple[str | None, dict | None]:
    """Returns (map path relative to package, inline map dict)."""
    refs = MAP_URL.findall(js_text[-4000:]) or MAP_URL.findall(js_text[:2000])
    if not refs:
        return None, None
    ref = refs[-1]
    if ref.startswith("data:"):
        try:
            payload = ref.split(",", 1)[1]
            return None, parse_map(base64.b64decode(payload).decode("utf-8", "replace"))
        except (IndexError, ValueError):
            return None, None
    if "://" in ref:
        return None, None
    return posixpath.normpath(posixpath.join(posixpath.dirname(js_rel), ref)), None


def is_external_source(src: str) -> bool:
    return any(marker in src for marker in EXTERNAL)


def resolve_source(src: str, map_rel: str, source_root: str, repo_paths: set[str]) -> str | None:
    s = re.sub(r"^(webpack|rollup|vite|turbopack)://+[^/]*/", "", src)
    s = re.sub(r"^\w+://+", "", s)
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(map_rel), source_root or "", s))
    parts = [p for p in joined.split("/") if p not in ("..", ".", "")]
    for i in range(len(parts)):
        cand = "/".join(parts[i:])
        if cand in repo_paths:
            return cand
    return None
