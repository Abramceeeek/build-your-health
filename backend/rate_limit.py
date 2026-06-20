"""In-process sliding-window rate limiter.

Single-process by design: the `_windows` dict is per-process, so limits are only enforced
correctly with a single worker (the current deploy runs gunicorn --workers 1). If you scale
to >1 worker/replica, limits can be bypassed across processes (M6) — at that point swap the
body of `check_rate_limit` for a shared backend (e.g. Redis sliding window) WITHOUT changing
its signature, so callers stay unchanged.
"""
from collections import deque
from datetime import datetime, timezone

# (user_id, endpoint) → deque of UTC timestamps
_windows: dict[tuple, deque] = {}


def check_rate_limit(
    user_id: int,
    endpoint: str,
    max_calls: int,
    window_seconds: int = 3600,
) -> bool:
    """Return True if the call is allowed; False if limit is exceeded."""
    key = (user_id, endpoint)
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - window_seconds

    window = _windows.setdefault(key, deque())
    while window and window[0] < cutoff:
        window.popleft()

    if len(window) >= max_calls:
        return False

    window.append(now)
    return True
