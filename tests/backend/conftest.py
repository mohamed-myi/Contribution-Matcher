import os
import sys
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.app.auth.dependencies import get_current_user  # noqa: E402
from backend.app.database import get_db  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.models import User  # noqa: E402


@pytest.fixture
def test_app_client(test_db) -> Iterator[tuple[TestClient, sessionmaker]]:
    db_url, TestingSessionLocal, engine = test_db

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
def authorized_client(
    test_app_client,
) -> Iterator[tuple[TestClient, Callable[[], User], sessionmaker]]:
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
