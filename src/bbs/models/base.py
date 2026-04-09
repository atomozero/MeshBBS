"""
Database base configuration and session management.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from contextlib import contextmanager
from typing import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.engine import Engine

# Base class for all models
Base = declarative_base()

# Session factory (will be initialized by init_database)
_SessionFactory = None
_engine = None


def get_engine(db_path: str = "data/bbs.db") -> Engine:
    """
    Create and configure SQLite engine.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Configured SQLAlchemy engine
    """
    global _engine

    if _engine is not None:
        return _engine

    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    _engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Configure SQLite pragmas for better performance
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.close()

    return _engine


def init_database(db_path: str = "data/bbs.db") -> None:
    """
    Initialize the database, creating all tables.

    Args:
        db_path: Path to SQLite database file
    """
    global _SessionFactory

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    _SessionFactory = sessionmaker(bind=engine)

    # Create default areas
    _create_default_data()


def _create_default_data() -> None:
    """Create default areas and initial data."""
    from .area import Area

    with get_session() as session:
        # Check if areas already exist
        existing = session.query(Area).first()
        if existing:
            return

        # Create default areas
        default_areas = [
            Area(
                name="generale",
                description="Area di discussione generale",
                is_public=True,
            ),
            Area(
                name="tech",
                description="Discussioni tecniche e progetti",
                is_public=True,
            ),
            Area(
                name="emergenze",
                description="Comunicazioni urgenti e emergenze",
                is_public=True,
            ),
        ]

        for area in default_areas:
            session.add(area)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Automatically commits on success, rolls back on exception.

    Yields:
        SQLAlchemy Session

    Example:
        with get_session() as session:
            user = session.query(User).first()
            user.last_seen = datetime.utcnow()
    """
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session_factory():
    """Get the session factory for direct usage."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _SessionFactory
