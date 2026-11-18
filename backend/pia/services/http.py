import hashlib
import logging
import random
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

log = logging.getLogger("pia.http")
RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpError(Exception):
    pass


class NotFound(HttpError):
    pass


class RateLimiter:
    """Per-host minimum spacing between requests."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._next: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next.get(host, 0.0))
            self._next[host] = slot + self.min_interval
        if slot > now:
            time.sleep(slot - now)


class HttpClient:
    """Read-only HTTP client with retries, backoff, rate limiting and ETag caching."""

    def __init__(self, settings):
        self.s = settings
        self.session = requests.Session()
        self.session.headers["User-Agent"] = settings.user_agent
        self.limiter = RateLimiter(settings.min_request_interval)
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _request(self, method: str, url: str, **kw) -> requests.Response:
        if urlparse(url).scheme != "https":
            raise HttpError(f"refusing non-HTTPS URL: {url}")
        attempts = self.s.http_retries + 1
        for i in range(attempts):
            self.limiter.wait(urlparse(url).netloc)
            try:
                r = self.session.request(method, url, timeout=self.s.limits.http_timeout, **kw)
            except requests.RequestException as e:
                if i == attempts - 1:
                    raise HttpError(f"network error for {url}: {e}") from e
                self._backoff(i, None)
                continue
            if r.status_code in RETRY_STATUS and i < attempts - 1:
                log.warning("HTTP %s for %s, retrying", r.status_code, url)
                retry_after = r.headers.get("Retry-After")
                r.close()
                self._backoff(i, retry_after)
                continue
            return r
        raise HttpError(f"retries exhausted for {url}")

    @staticmethod
    def _backoff(attempt: int, retry_after):
        try:
            hinted = float(retry_after) if retry_after else 0.0
        except ValueError:
            hinted = 0.0
        time.sleep(min(max(hinted, 0.5 * 2**attempt + random.random() * 0.3), 20))

    def get_json(self, url: str, ttl: int = 300, headers: dict | None = None):
        now = time.time()
        with self._lock:
            cached = self._cache.get(url)
        if cached and now - cached["t"] < ttl:
            return cached["data"]
        h = dict(headers or {})
        if cached and cached.get("etag"):
            h["If-None-Match"] = cached["etag"]
        r = self._request("GET", url, headers=h)
        if r.status_code == 304 and cached:
            cached["t"] = now
            return cached["data"]
        if r.status_code == 404:
            raise NotFound(f"not found: {url}")
        if r.status_code >= 400:
            raise HttpError(f"HTTP {r.status_code} for {url}")
        if len(r.content) > self.s.limits.max_metadata_bytes:
            raise HttpError(f"metadata response too large for {url}")
        data = r.json()
        with self._lock:
            self._cache[url] = {"t": now, "etag": r.headers.get("ETag"), "data": data}
        return data

    def download(self, url: str, dest: Path, max_bytes: int) -> dict:
        r = self._request("GET", url, stream=True)
        try:
            if r.status_code == 404:
                raise NotFound(f"not found: {url}")
            if r.status_code >= 400:
                raise HttpError(f"HTTP {r.status_code} downloading {url}")
            declared = r.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise HttpError(f"download of {int(declared)} bytes exceeds limit of {max_bytes}")
            hashes = {k: hashlib.new(k) for k in ("sha256", "sha512", "sha1")}
            total = 0
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(65536):
                    total += len(chunk)
                    if total > max_bytes:
                        raise HttpError(f"download exceeded limit of {max_bytes} bytes")
                    fh.write(chunk)
                    for h in hashes.values():
                        h.update(chunk)
            return {"size": total, "digests": {k: h.hexdigest() for k, h in hashes.items()}}
        finally:
            r.close()


def hash_file(path: Path) -> dict:
    hashes = {k: hashlib.new(k) for k in ("sha256", "sha512", "sha1")}
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            size += len(chunk)
            for h in hashes.values():
                h.update(chunk)
    return {"size": size, "digests": {k: h.hexdigest() for k, h in hashes.items()}}
