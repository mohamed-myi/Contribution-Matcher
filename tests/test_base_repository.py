import pytest

from core.repositories.user_repository import UserRepository


def test_count_unknown_filter_key_raises(test_session):
    repo = UserRepository(test_session)

    with pytest.raises(ValueError, match="Unknown filter key"):
        repo.count(typo_key=5)
