import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

# SQLAlchemy 2.0 defaults to psycopg (v3); ensure postgresql+psycopg2 is used
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# Configure reliable SQLAlchemy connection pooling against Supabase PostgreSQL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Automatically detects severed/idle connections and reconnects
    pool_size=5,             # Sensible pool size for development
    max_overflow=10,
    pool_recycle=120,        # Recycle connections every 2 minutes before Supabase idle timeout
    pool_timeout=30,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency generator yielding a database session for requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
