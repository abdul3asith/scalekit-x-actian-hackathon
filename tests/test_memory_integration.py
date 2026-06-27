"""Integration test for Actian VectorAI per-user memory. Exercises the adapter
directly with synthetic vectors (no Nebius needed). Skips if Actian is disabled
or the server isn't reachable."""

import pytest

from app.config import settings
from app.data import memory


def _adapter_or_skip():
    if not memory._available():
        pytest.skip("Actian disabled or client not installed")
    try:
        from actian_vectorai import VectorAIClient

        with VectorAIClient(f"{settings.actian_host}:{settings.actian_port}") as c:
            c.health_check()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Actian server not reachable: {exc}")
    return memory._AdapterActian()


def _cleanup(*staff_ids):
    from actian_vectorai import VectorAIClient

    with VectorAIClient(f"{settings.actian_host}:{settings.actian_port}") as c:
        for sid in staff_ids:
            try:
                c.collections.delete(memory._collection_name(sid))
            except Exception:  # noqa: BLE001
                pass


def test_memory_roundtrip_and_isolation():
    adapter = _adapter_or_skip()
    sid_a, sid_b = "pytest-mem-aaaa", "pytest-mem-bbbb"
    vec = [0.02] * settings.embed_dim
    try:
        adapter.upsert(sid_a, vec, "alpha prefers mornings")
        found = adapter.search(sid_a, vec, 5)
        assert "alpha prefers mornings" in found

        # A different staff's collection must not see A's memory.
        other = adapter.search(sid_b, vec, 5)
        assert other == []
    finally:
        _cleanup(sid_a, sid_b)
