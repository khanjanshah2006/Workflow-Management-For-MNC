import pytest
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    """
    Ensure UUID columns in SQLite in-memory test databases have TEXT affinity (VARCHAR(36)),
    preventing SQLite's NUMERIC affinity from interpreting scientific-notation-like UUID hexes
    (e.g., '1e309...') as floating-point infinity ('inf').
    """
    return "VARCHAR(36)"


@pytest.fixture(autouse=True)
def reset_login_rate_limiter():
    """The login limiter is module-level state; start every test with empty buckets."""
    from app.features.auth.rate_limit import login_limiter

    login_limiter.reset()
    yield
