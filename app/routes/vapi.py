"""VAPI custom-LLM endpoint. VAPI is configured to treat this OpenAI-compatible
``/chat/completions`` endpoint as its model. We resolve the caller's identity from
their phone number, run the Nebius tool loop server-side, and stream SSE back."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth.identity import resolve_staff_by_phone
from app.config import settings
from app.data.db import connection
from app.llm.loop import stream_response

router = APIRouter(tags=["vapi"])


def _check_api_key(authorization: str | None) -> None:
    expected = settings.backend_api_key
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    if not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


def _extract_phone(body: dict[str, Any], header_phone: str | None) -> str | None:
    """Find the caller's number across the shapes VAPI / test clients may send."""
    candidates = [
        header_phone,
        body.get("phone"),
        (body.get("call") or {}).get("customer", {}).get("number"),
        (body.get("customer") or {}).get("number"),
        (body.get("metadata") or {}).get("phone"),
    ]
    return next((c for c in candidates if c), None)


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
    x_caller_number: str | None = Header(default=None),
):
    _check_api_key(authorization)
    body = await request.json()
    messages = body.get("messages", [])
    phone = _extract_phone(body, x_caller_number)

    staff = None
    if phone:
        async with connection() as conn:
            staff = await resolve_staff_by_phone(conn, phone)

    return StreamingResponse(
        stream_response(messages, staff),
        media_type="text/event-stream",
    )
