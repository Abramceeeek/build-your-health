"""In-process sliding-window rate limiter. No Redis required at current scale."""
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
