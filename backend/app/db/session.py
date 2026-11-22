from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

DATABASE_URL = settings.database_url

# Configure reliable SQLAlchemy connection pooling against Supabase PostgreSQL or SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Automatically detects severed/idle connections and reconnects
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=120,        # Recycle connections every 2 minutes before Supabase idle timeout
        pool_timeout=30,
        connect_args={"connect_timeout": settings.db_connect_timeout},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency generator yielding a database session for requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
