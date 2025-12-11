from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor


def test_get_cache_initializes_once(monkeypatch):
    """
    get_cache() must not run cache.initialize() concurrently.

    We patch backend.app.dependencies.cache with a fake cache object and verify
    initialize() is called exactly once even under concurrent access.
    """
    import backend.app.dependencies as deps

    class FakeCache:
        def __init__(self):
            self._initialized = False
            self.init_calls = 0

        def initialize(self, force: bool = False) -> bool:  # noqa: ARG002
            self.init_calls += 1
            self._initialized = True
            return True

    fake_cache = FakeCache()
    monkeypatch.setattr(deps, "cache", fake_cache, raising=True)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: deps.get_cache(), range(100)))

    assert all(r is fake_cache for r in results)
    assert fake_cache.init_calls == 1
