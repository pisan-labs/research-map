"""Polite, cached HTTP GET.

Every page is stored under the cache directory keyed by URL, so reruns cost
no requests. Fresh requests are spaced by `delay` seconds.
"""

from __future__ import annotations

import hashlib
import os
import ssl
import time
from pathlib import Path

import httpx

USER_AGENT = "research-map/0.1 (+https://github.com/pisan-labs/research-map)"
CERTS_DIR = Path(__file__).resolve().parents[3] / "config" / "certs"


def ssl_context(extra_dir: Path = CERTS_DIR) -> ssl.SSLContext:
    """System trust plus extra intermediate certificates from config/certs/.

    Some university servers (tacoma.uw.edu, jacobsschool.ucsd.edu) omit the
    intermediate certificate. Browsers fetch it on their own; here it is added
    to the trust store instead, so verification stays on.
    """
    cafile = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    if extra_dir.is_dir():
        for pem in sorted(extra_dir.glob("*.pem")):
            ctx.load_verify_locations(cafile=str(pem))
    return ctx


class CachedFetcher:
    def __init__(self, cache_dir: Path, delay: float = 1.0, timeout: float = 30.0):
        self.cache_dir = cache_dir
        self.delay = delay
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout,
            verify=ssl_context(),
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
