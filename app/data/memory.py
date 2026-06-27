"""Per-user isolated memory backed by Actian VectorAI.

Isolation model: ONE collection per staff member (``mem_<staff_id>``), so one
user's vectors are physically separate from another's. Embeddings come from
Nebius (see app/llm/nebius.py); the collection's vector size must equal
``settings.embed_dim``.

The Actian client API is centralized in the ``_AdapterActian`` class below --
verified against actian-vectorai-client 1.0.1 (see docs.vectoraidb.actian.com).
If Actian is disabled or the client isn't installed, memory degrades to a no-op
so scheduling still works.
"""

from __future__ import annotations

import uuid
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.llm.nebius import embed

# --- Optional dependency: import guarded so the app boots without the wheel. ---
try:  # pragma: no cover - depends on environment
    from actian_vectorai import (  # type: ignore
        CollectionExistsError,
        Distance,
        PointStruct,
        VectorAIClient,
        VectorParams,
    )

    _CLIENT_IMPORTED = True
except Exception:  # noqa: BLE001
    _CLIENT_IMPORTED = False


def _collection_name(staff_id: str) -> str:
    # VectorAI DB has no built-in multi-tenancy; isolation is enforced by giving
    # each user their own collection, named off the verified staff_id.
    return f"user-{staff_id}-memories"


class _AdapterActian:
    """Thin, synchronous wrapper over the Actian VectorAI client.

    All Actian-specific calls live here -- the ONE place to adjust if the wheel's
    API differs. Per-user isolation = one collection per staff_id. The vector size
    and distance metric are fixed at creation and must be identical for every user.
    """

    def __init__(self) -> None:
        self._addr = f"{settings.actian_host}:{settings.actian_port}"
        self._known_collections: set[str] = set()

    def _ensure_collection(self, client: Any, name: str) -> None:
        if name in self._known_collections:
            return
        try:
            client.collections.create(
                name,
                vectors_config=VectorParams(
                    size=settings.embed_dim, distance=Distance.Cosine
                ),
            )
        except CollectionExistsError:
            pass
        self._known_collections.add(name)

    @staticmethod
    def _text_of(result: Any) -> str:
        payload = getattr(result, "payload", None)
        if isinstance(payload, dict):
            return payload.get("text", "")
        return ""

    def upsert(self, staff_id: str, vector: list[float], text: str) -> None:
        name = _collection_name(staff_id)
        with VectorAIClient(self._addr) as client:
            self._ensure_collection(client, name)
            point = PointStruct(
                id=uuid.uuid4().int >> 64,  # 64-bit id
                vector=vector,
                payload={"text": text},
            )
            client.points.upsert(name, [point])

    def search(self, staff_id: str, vector: list[float], k: int) -> list[str]:
        name = _collection_name(staff_id)
        with VectorAIClient(self._addr) as client:
            self._ensure_collection(client, name)
            results = client.points.search(name, vector=vector, limit=k)
            return [t for t in (self._text_of(r) for r in results) if t]


_adapter: _AdapterActian | None = None


def _available() -> bool:
    return settings.actian_enabled and _CLIENT_IMPORTED


def _get_adapter() -> _AdapterActian:
    global _adapter
    if _adapter is None:
        _adapter = _AdapterActian()
    return _adapter


async def remember(staff_id: str, text: str) -> dict[str, Any]:
    """Store a free-form note/preference in the staff member's memory."""
    if not _available():
        return {
            "ok": False,
            "available": False,
            "message": "Memory store is not configured; nothing was saved.",
        }
    vector = await embed(text)
    await run_in_threadpool(_get_adapter().upsert, staff_id, vector, text)
    return {"ok": True, "stored": text}


async def recall(staff_id: str, query: str, k: int = 5) -> dict[str, Any]:
    """Retrieve the staff member's most relevant remembered notes for a query."""
    if not _available():
        return {"available": False, "memories": []}
    vector = await embed(query)
    memories = await run_in_threadpool(_get_adapter().search, staff_id, vector, k)
    return {"available": True, "memories": memories}
