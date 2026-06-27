"""VAPI custom-LLM endpoint. VAPI is configured to treat this OpenAI-compatible
``/chat/completions`` endpoint as its model.

Two modes, distinguished by the call's ``metadata.mode``:
- inbound (default): a staff member managing their own schedule (identity resolved
  from the caller's phone number).
- outbound: we placed this call to ask a candidate to cover a shift; the coverage
  handoff context arrives in metadata (coverage_request_id, candidate_staff_id).
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth.identity import resolve_staff_by_phone
from app.config import settings
from app.data import coverage
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


def _extract_metadata(body: dict[str, Any]) -> dict[str, Any]:
    """Coverage handoff metadata can ride on the call object or the body."""
    return (body.get("call") or {}).get("metadata") or body.get("metadata") or {}


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    authorization: str | None = Header(default=None),
    x_caller_number: str | None = Header(default=None),
    x_vapi_mode: str | None = Header(default=None),
):
    _check_api_key(authorization)
    body = await request.json()
    messages = body.get("messages", [])
    metadata = _extract_metadata(body)
    phone = _extract_phone(body, x_caller_number)
    mode = metadata.get("mode") or x_vapi_mode or "inbound"

    # --- Outbound coverage call ---
    if mode == "outbound" and metadata.get("coverage_request_id"):
        async with connection() as conn:
            ctx = await coverage.context(conn, metadata["coverage_request_id"])
            candidate = await resolve_staff_by_phone(conn, phone) if phone else None
        if ctx is not None:
            coverage_context = {
                **ctx,
                "candidate_staff_id": metadata.get("candidate_staff_id")
                or (str(candidate["id"]) if candidate else None),
                "candidate_name": candidate["full_name"] if candidate else None,
            }
            return StreamingResponse(
                stream_response(messages, candidate, mode="outbound", coverage_context=coverage_context),
                media_type="text/event-stream",
            )

    # --- Inbound: staff managing their own schedule ---
    staff = None
    if phone:
        async with connection() as conn:
            staff = await resolve_staff_by_phone(conn, phone)

    return StreamingResponse(
        stream_response(messages, staff),
        media_type="text/event-stream",
    )
