"""Simple per-key cooldown limiter shared by the auth and chat routes.

KNOWN LIMITATION: the buckets below are plain process-local dicts, not a
shared store (e.g. Redis). That's fine for the current deployment — a single
Gunicorn worker (see backend/Dockerfile's CMD) — but it means these limits
are only enforced per-process: they reset on every restart/redeploy, and
would under-count requests if this app ever ran with multiple workers or
multiple replicas, since each process would track its own timestamps. Scaling
horizontally would require moving these buckets to Redis (or similar) so all
processes share one view of "when did this key last make a request."
"""

import time

# Keyed by user id — a single shared timestamp would let one user's chat
# request block every other logged-in user for MIN_SECONDS_BETWEEN_CHATS.
_last_chat_time_by_user: dict[str, float] = {}
# Keyed by request IP, separately per endpoint, so a burst of register
# attempts from one address doesn't also throttle that address's login
# attempts (or vice versa).
_last_login_time_by_ip: dict[str, float] = {}
_last_register_time_by_ip: dict[str, float] = {}


def too_soon(bucket: dict[str, float], key: str, min_seconds: float) -> bool:
    """True (and leaves `bucket` untouched) if `key` was last seen under
    `min_seconds` ago; otherwise records `key` as seen now and returns False."""
    now = time.monotonic()
    last = bucket.get(key, 0.0)
    if now - last < min_seconds:
        return True
    bucket[key] = now
    return False
