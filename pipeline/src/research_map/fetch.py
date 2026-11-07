"""Polite, cached HTTP GET.

Every page is stored under the cache directory keyed by URL, so reruns cost
no requests. Fresh requests are spaced by `delay` seconds.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx

USER_AGENT = "research-map/0.1 (+https://github.com/pisan-labs/research-map)"


class CachedFetcher:
    def __init__(self, cache_dir: Path, delay: float = 1.0, timeout: float = 30.0):
        self.cache_dir = cache_dir
        self.delay = delay
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout,
        )
        self._last = 0.0

    def path_for(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()[:16]
        return self.cache_dir / f"{h}.html"

    def get(self, url: str, refresh: bool = False) -> str:
        path = self.path_for(url)
        if path.exists() and not refresh:
            return path.read_text(encoding="utf-8")
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self.client.get(url)
        self._last = time.monotonic()
        resp.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(resp.text, encoding="utf-8")
        return resp.text
