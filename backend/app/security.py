"""Abuse protection: optional rate limiting and API key verification."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Header, HTTPException, Request

from .utils import settings

_request_history: Dict[str, List[float]] = defaultdict(list)


def reset_rate_limit_history() -> None:
    """Helper for unit tests to clear rate limiter history."""
    _request_history.clear()


def parse_rate_limit(limit_str: str) -> Tuple[int, int]:
    """Parse rate limit strings like '10/minute', '5/second', '100/hour'."""
    parts = limit_str.split("/")
    if len(parts) != 2:
        return 10, 60
    count = int(parts[0].strip())
    unit = parts[1].strip().lower()
    if unit in ("second", "sec", "s"):
        window = 1
    elif unit in ("minute", "min", "m"):
        window = 60
    elif unit in ("hour", "hr", "h"):
        window = 3600
    elif unit in ("day", "d"):
        window = 86400
    else:
        window = 60
    return count, window


def verify_abuse_protection(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> None:
    """Dependency enforcing optional API Key header and rate limiting."""
    # 1. Optional API key check
    if settings.api_key:
        if not x_api_key or x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # 2. Optional Rate limiting check
    if settings.rate_limit_generation:
        max_reqs, window_sec = parse_rate_limit(settings.rate_limit_generation)
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Filter timestamps outside the sliding window
        history = [ts for ts in _request_history[client_ip] if now - ts < window_sec]
        if len(history) >= max_reqs:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        history.append(now)
        _request_history[client_ip] = history
