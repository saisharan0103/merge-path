"""Redis singletons + helpers.

In dev/test we may have no Redis running — fall back to fakeredis if the
import is available, then to a tiny in-memory shim. The shim implements only
what we actually use (``publish``, ``set``, ``get``, ``delete``, ``lock``).
"""

from __future__ import annotations

import contextlib
import threading
import time
from typing import Any

from app.config import settings

try:
    import redis as _redis_pkg
except Exception:  # pragma: no cover
    _redis_pkg = None


class _InMemoryRedis:
    """Tiny shim for offline mode. NOT a full redis impl."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._channels: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        with self._lock:
            self._store[key] = value
        return True

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def delete(self, *keys: str) -> int:
        n = 0
        with self._lock:
            for k in keys:
                if k in self._store:
                    del self._store[k]
                    n += 1
        return n

    def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def publish(self, channel: str, message: str) -> int:
        with self._lock:
            self._channels.setdefault(channel, []).append(message)
        return 0

    @contextlib.contextmanager
    def lock(self, name: str, timeout: int = 60, blocking_timeout: int = 5):
        deadline = time.time() + blocking_timeout
        acquired = False
        while time.time() < deadline:
            with self._lock:
                if name not in self._store:
                    self._store[name] = "1"
                    acquired = True
                    break
            time.sleep(0.05)
        try:
            yield acquired
        finally:
            if acquired:
                with self._lock:
                    self._store.pop(name, None)


_client: Any | None = None


def get_redis() -> Any:
    """Return a redis-like client; falls back to in-memory when unreachable."""
    global _client
    if _client is not None:
        return _client
    if _redis_pkg is not None:
        try:
            c = _redis_pkg.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
            c.ping()
            _client = c
            return c
        except Exception:
            pass
    try:
        import fakeredis  # type: ignore

        _client = fakeredis.FakeRedis(decode_responses=True)
        return _client
    except Exception:
        _client = _InMemoryRedis()
        return _client


def repo_lock(repo_id: int, timeout: int = 600, blocking_timeout: int = 30):
    """Per-repo lock — used to serialize git ops on the same clone."""
    client = get_redis()
    if hasattr(client, "lock") and not isinstance(client, _InMemoryRedis):
        return client.lock(f"patchpilot:repo:{repo_id}", timeout=timeout, blocking_timeout=blocking_timeout)
    return client.lock(f"patchpilot:repo:{repo_id}", timeout=timeout, blocking_timeout=blocking_timeout)
