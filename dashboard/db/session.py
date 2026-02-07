"""Database engine and session for C2 dashboard."""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base


def _db_path() -> str:
    path = os.getenv("DASHBOARD_DB")
    if path:
        return path
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    out = os.path.join(root, "outputs")
    if not os.path.isdir(out):
        os.makedirs(out, exist_ok=True)
    return os.path.join(out, "c2.sqlite")


_db_url = f"sqlite:///{_db_path()}"

engine = create_engine(_db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Session:
    """Context manager for a database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
