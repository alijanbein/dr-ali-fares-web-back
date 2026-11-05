"""Simple in-memory per-IP limits. These routes are public, and one server
process is all this site needs for now."""
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    # Behind a proxy such as Render, every visitor otherwise appears to share
    # the proxy's address.
    if os.getenv("TRUST_PROXY", "").lower() == "true":
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(key: str, limit: int, window_seconds: int, detail: str) -> None:
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail=detail)
        hits.append(now)
