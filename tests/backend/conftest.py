import os
import sys
from typing import Callable, Iterator

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.app.main import create_app  # noqa: E402
from backend.app.database import Base, get_db  # noqa: E402
from backend.app.auth.dependencies import get_current_user  # noqa: E402
from backend.app.models import User  # noqa: E402


@pytest.fixture(scope="function")
def test_app_client() -> Iterator[tuple[TestClient, sessionmaker]]:
    db_dir = Path(tempfile.mkdtemp(prefix="backend_tests_"))
    db_path = db_dir / "test_backend.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    app = create_app()

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
            db.commit()  # Auto-commit on success like production
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSessionLocal


@pytest.fixture
def authorized_client(test_app_client) -> Iterator[tuple[TestClient, Callable[[], User], sessionmaker]]:
    client, TestingSessionLocal = test_app_client
    session = TestingSessionLocal()
    user = User(
        github_id="1",
        github_username="tester",
        email="tester@example.com",
        avatar_url="http://example.com/avatar.png",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()

    def override_current_user() -> User:
        session_inner = TestingSessionLocal()
        try:
            return session_inner.query(User).filter(User.id == user.id).one()
        finally:
            session_inner.close()

    client.app.dependency_overrides[get_current_user] = override_current_user

    yield client, override_current_user, TestingSessionLocal

    client.app.dependency_overrides.pop(get_current_user, None)

