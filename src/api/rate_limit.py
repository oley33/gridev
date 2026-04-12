"""Simple in-memory rate limiter.

Uses a sliding window per client IP. No external dependencies.
For production with multiple instances, swap this for Redis-backed limiting.
"""

import time
from collections import defaultdict

from fastapi import Request, HTTPException


class RateLimiter:
    """Per-IP sliding window rate limiter."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self._limit = requests_per_minute
        self._window = 60.0  # seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For behind a proxy."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP (original client), ignore proxy chain
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        """Raise 429 if client has exceeded the rate limit."""
        client_ip = self._get_client_ip(request)
        now = time.monotonic()

        # Prune old timestamps outside the window
        timestamps = self._requests[client_ip]
        cutoff = now - self._window
        self._requests[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._requests[client_ip]) >= self._limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again in a minute.",
            )

        self._requests[client_ip].append(now)
