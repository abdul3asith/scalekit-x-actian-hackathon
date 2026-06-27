"""Nebius AI Studio client. Nebius is OpenAI-compatible, so we reuse the OpenAI
SDK for both chat completions (with tool calling) and embeddings -- only the
base_url and key differ."""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI

from app.config import settings


@lru_cache
def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.nebius_api_key,
        base_url=settings.nebius_base_url,
    )


async def embed(text: str) -> list[float]:
    """Embed a single string with the configured Nebius embedding model."""
    resp = await get_client().embeddings.create(
        model=settings.nebius_embed_model,
        input=text,
    )
    return resp.data[0].embedding
