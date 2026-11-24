import pytest


@pytest.fixture(autouse=True)
def reset_login_rate_limiter():
    """The login limiter is module-level state; start every test with empty buckets."""
    from app.features.auth.rate_limit import login_limiter

    login_limiter.reset()
    yield
