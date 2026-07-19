"""Sliding-window rate limiter.

Time is injected rather than slept through, so the window's edges can be
asserted exactly instead of approximately.
"""

from app.core.rate_limit import (
    RateLimitPolicy,
    SlidingWindowRateLimiter,
)

POLICY = RateLimitPolicy(max_requests=3, window_seconds=60)


def make_limiter() -> SlidingWindowRateLimiter:
    """A limiter allowing 3 requests per 60 seconds."""
    return SlidingWindowRateLimiter(POLICY)


def test_allows_requests_up_to_the_limit() -> None:
    """The budget is spendable in full."""
    limiter = make_limiter()

    for index in range(POLICY.max_requests):
        assert limiter.check("client", now=float(index)).allowed is True


def test_refuses_the_request_after_the_limit() -> None:
    """One past the budget is refused."""
    limiter = make_limiter()

    for index in range(POLICY.max_requests):
        limiter.check("client", now=float(index))

    assert limiter.check("client", now=3.0).allowed is False


def test_refusal_reports_when_to_retry() -> None:
    """Retry-After is what lets a client back off instead of hammering."""
    limiter = make_limiter()

    for _ in range(POLICY.max_requests):
        limiter.check("client", now=0.0)

    result = limiter.check("client", now=10.0)

    # The oldest hit was at t=0 and ages out at t=60, so ~50s remain.
    assert result.allowed is False
    assert 50 <= result.retry_after <= 52


def test_window_slides_rather_than_resetting_wholesale() -> None:
    """The decisive property.

    A fixed window would let a caller spend the whole budget at the end of one
    window and the whole budget again at the start of the next — twice the
    intended rate at the exact moment it matters. Here each hit expires on its
    own schedule, so only the one that aged out is refunded.
    """
    limiter = make_limiter()

    limiter.check("client", now=0.0)
    limiter.check("client", now=30.0)
    limiter.check("client", now=45.0)

    assert limiter.check("client", now=50.0).allowed is False

    # t=61 is past the first hit's expiry but not the others'.
    assert limiter.check("client", now=61.0).allowed is True
    assert limiter.check("client", now=62.0).allowed is False


def test_keys_are_tracked_independently() -> None:
    """One caller exhausting their budget must not block anyone else."""
    limiter = make_limiter()

    for _ in range(POLICY.max_requests):
        limiter.check("noisy", now=0.0)

    assert limiter.check("noisy", now=1.0).allowed is False
    assert limiter.check("quiet", now=1.0).allowed is True


def test_reset_clears_one_key() -> None:
    """A successful login refunds that caller's budget."""
    limiter = make_limiter()

    for _ in range(POLICY.max_requests):
        limiter.check("client", now=0.0)
    assert limiter.check("client", now=1.0).allowed is False

    limiter.reset("client")

    assert limiter.check("client", now=1.0).allowed is True


def test_reset_leaves_other_keys_alone() -> None:
    """Resetting one caller must not refund another's budget."""
    limiter = make_limiter()

    for _ in range(POLICY.max_requests):
        limiter.check("other", now=0.0)

    limiter.reset("client")

    assert limiter.check("other", now=1.0).allowed is False


def test_uses_the_wall_clock_when_no_time_is_given() -> None:
    """The production path takes its own clock reading."""
    limiter = make_limiter()

    assert limiter.check("client").allowed is True


def test_idle_keys_are_evicted() -> None:
    """The map must not grow one entry per caller forever.

    Unbounded growth on an endpoint anyone can reach unauthenticated is a
    denial-of-service vector, not untidiness. An earlier version had a guard
    for this that could never run — `hits.append` meant the deque was never
    empty when it was checked — so the leak was real and the comment claimed
    otherwise.
    """
    limiter = SlidingWindowRateLimiter(POLICY)
    limiter._eviction_threshold = 3

    for index in range(5):
        limiter.check(f"caller-{index}", now=0.0)

    # Every earlier hit has aged out by now; one fresh caller triggers a sweep.
    limiter.check("recent", now=1_000.0)

    assert len(limiter._hits) == 1
    assert "recent" in limiter._hits


def test_active_keys_survive_eviction() -> None:
    """A sweep must not forget callers who are still inside their window."""
    limiter = SlidingWindowRateLimiter(POLICY)
    limiter._eviction_threshold = 2

    limiter.check("old", now=0.0)
    limiter.check("current", now=59.0)
    # t=61 puts the cutoff at 1.0: "old" has aged out, "current" has not.
    limiter.check("newest", now=61.0)

    assert "old" not in limiter._hits
    assert "current" in limiter._hits


def test_eviction_does_not_reset_an_active_budget() -> None:
    """Sweeping must not hand a rate-limited caller a fresh allowance."""
    limiter = SlidingWindowRateLimiter(POLICY)
    limiter._eviction_threshold = 1

    for _ in range(POLICY.max_requests):
        limiter.check("noisy", now=1.0)

    assert limiter.check("noisy", now=2.0).allowed is False
