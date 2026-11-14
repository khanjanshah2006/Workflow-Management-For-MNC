import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()
# Also check backend/.env explicitly so it loads regardless of cwd
_backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
if os.path.exists(_backend_env):
    load_dotenv(_backend_env)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

# SQLAlchemy 2.0 defaults to psycopg (v3); ensure postgresql+psycopg2 is used
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# Configure reliable SQLAlchemy connection pooling against Supabase PostgreSQL or SQLite
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Automatically detects severed/idle connections and reconnects
        pool_size=5,             # Sensible pool size for development
        max_overflow=10,
        pool_recycle=120,        # Recycle connections every 2 minutes before Supabase idle timeout
        pool_timeout=30,
        connect_args={"connect_timeout": 3},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency generator yielding a database session for requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
