"""
Pytest configuration and fixtures.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy.orm import Session

# Add src to path for imports
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Now we can import from src
import bbs.models.base as db_base
from bbs.models.area import Area
from meshbbs_radio.connection import MockMeshCoreConnection
from utils.config import Config, set_config
from web.auth.models import AdminUser as AdminUserModel


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_db() -> Generator[str, None, None]:
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def config(temp_db: str) -> Config:
    """Create test configuration."""
    cfg = Config(
        serial_port="/dev/null",
        baud_rate=115200,
        database_path=temp_db,
        log_path="",
        log_level="DEBUG",
        bbs_name="Test BBS",
    )
    set_config(cfg)
    return cfg


@pytest.fixture
def db_session(config: Config) -> Generator[Session, None, None]:
    """Create database session for testing."""
    # Reset global state to ensure fresh database for each test
    db_base._engine = None
    db_base._SessionFactory = None

    db_base.init_database(config.database_path)

    with db_base.get_session() as session:
        yield session

    # Cleanup: reset global state after test
    db_base._engine = None
    db_base._SessionFactory = None


@pytest.fixture
def mock_connection() -> MockMeshCoreConnection:
    """Create mock MeshCore connection."""
    return MockMeshCoreConnection(node_name="TestBBS")


@pytest.fixture
def sample_areas(db_session: Session) -> list[Area]:
    """Create sample message areas for tests.

    Note: init_database creates default areas (generale, tech, emergenze).
    This fixture returns those areas instead of creating conflicting ones.
    """
    # Query the areas created by init_database
    areas = db_session.query(Area).all()
    if areas:
        return areas

    # Fallback: create areas if none exist
    areas = [
        Area(name="general", description="General discussion"),
        Area(name="tech", description="Technical topics"),
        Area(name="news", description="News and announcements"),
    ]
    for area in areas:
        db_session.add(area)
    db_session.commit()

    return areas


@pytest.fixture
def test_sender_key() -> str:
    """Return a test sender public key."""
    return "A" * 64


@pytest.fixture
def test_sender_key_2() -> str:
    """Return a second test sender public key."""
    return "B" * 64


@pytest.fixture
def admin_sender_key(db_session: Session) -> str:
    """Return an admin user's public key."""
    from bbs.models.user import User

    admin_key = "C" * 64
    admin = User(public_key=admin_key, nickname="Admin", is_admin=True)
    db_session.add(admin)
    db_session.commit()
    return admin_key
