"""In-process sliding-window rate limiting for the auth endpoints.

Scope, stated plainly: this counts requests inside one process. A deployment
running several workers or replicas would let each one allow the full quota, so
the effective limit multiplies by the number of processes. Doing better needs
shared state — Redis — which is a fourth service this stack does not otherwise
need. For a single-container deployment it is correct, and it raises the cost
of online password guessing from free to slow, which is the point.

The durable control against a targeted attack on one account is the lockout in
app.services.auth, which lives in the database and therefore holds regardless
of how many processes are serving.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock


@dataclass(frozen=True)
class RateLimitPolicy:
    """How many requests are allowed, and over what window."""

    max_requests: int
    window_seconds: int


@dataclass
class RateLimitResult:
    """The outcome of a check."""

    allowed: bool
    # Seconds until the caller may retry. Zero when allowed.
    retry_after: int = 0


@dataclass
class SlidingWindowRateLimiter:
    """Track request timestamps per key and refuse once a window is full.

    A sliding window rather than a fixed one: a fixed window lets a caller
    spend the whole quota at 11:59:59 and the whole quota again at 12:00:00,
    which is twice the intended rate at the moment it matters most.
    """

    policy: RateLimitPolicy
    _hits: dict[str, deque[float]] = field(default_factory=dict)
    # Uvicorn serves requests on a thread pool for sync handlers, so two
    # requests really can touch one key at once.
    _lock: Lock = field(default_factory=Lock)
    # Below this many tracked callers the sweep is not worth the walk.
    _eviction_threshold: int = 512

    def check(self, key: str, *, now: float | None = None) -> RateLimitResult:
        """Record a request against `key` and say whether it is allowed."""
        current = time.monotonic() if now is None else now
        cutoff = current - self.policy.window_seconds

        with self._lock:
            hits = self._hits.setdefault(key, deque())

            # Drop everything that has aged out of the window.
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.policy.max_requests:
                oldest = hits[0]
                retry_after = max(
                    1, int(oldest + self.policy.window_seconds - current) + 1
                )
                return RateLimitResult(allowed=False, retry_after=retry_after)

            hits.append(current)
            self._evict_idle_keys(cutoff)

            return RateLimitResult(allowed=True)

    def _evict_idle_keys(self, cutoff: float) -> None:
        """Drop keys whose every hit has aged out.

        Without this `_hits` grows one entry per distinct client address and
        never shrinks — a slow memory leak on an endpoint anyone can reach
        unauthenticated, which is a denial-of-service vector rather than
        untidiness.

        Swept on write rather than on a timer: the dictionary only grows when
        something is added, so that is exactly when it is worth checking. The
        scan is bounded by the number of distinct callers in one window, and
        only runs once the map is large enough to be worth walking.
        """
        if len(self._hits) < self._eviction_threshold:
            return

        stale = [
            key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff
        ]

        for key in stale:
            del self._hits[key]

    def reset(self, key: str) -> None:
        """Forget a key's history — used after a successful login."""
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        """Drop all state. Test helper."""
        with self._lock:
            self._hits.clear()


# Login is the endpoint worth guessing against, so it gets the tighter budget.
# Generous enough that a person mistyping a password a few times is unaffected.
LOGIN_POLICY = RateLimitPolicy(max_requests=10, window_seconds=300)

# Registration is rate limited to make bulk account creation tedious rather
# than free.
REGISTER_POLICY = RateLimitPolicy(max_requests=5, window_seconds=3600)

login_rate_limiter = SlidingWindowRateLimiter(LOGIN_POLICY)
register_rate_limiter = SlidingWindowRateLimiter(REGISTER_POLICY)
