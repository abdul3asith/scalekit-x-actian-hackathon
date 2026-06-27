"""The orchestration core: drive Nebius with native function calling, execute
tool calls server-side (scoped to staff_id), then stream the final assistant
text back to VAPI as OpenAI-compatible SSE chunks."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.data.db import connection
from app.llm import tools
from app.llm.nebius import get_client

MAX_TOOL_ROUNDS = 6


def system_prompt(staff: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    return (
        "You are a hands-free staff scheduling assistant spoken to over the phone. "
        f"The current UTC time is {now}. "
        f"You are talking to {staff.get('full_name', 'a staff member')}. "
        "Help them check, set, and adjust THEIR OWN shifts. "
        "Use the tools for anything involving schedule data or memory -- never guess. "
        "When booking, convert relative dates ('tomorrow', 'next Friday') to absolute ISO-8601 "
        "times before calling tools. If a booking overlaps, tell them clearly and offer to pick "
        "another time. Keep replies short and natural for speech."
    )


def coverage_system_prompt(ctx: dict[str, Any]) -> str:
    """System prompt for an OUTBOUND call asking a candidate to cover a shift."""
    from app.services.vapi_out import shift_summary

    candidate = ctx.get("candidate_name") or "there"
    requester = ctx["requester"]["name"]
    return (
        "You are a staff scheduling assistant making an OUTBOUND call. "
        f"You are calling {candidate} to ask if they can cover a shift for {requester}. "
        f"The shift is: {shift_summary(ctx)}. "
        "Greet them briefly, explain you're calling to see if they can cover this shift, "
        "and ask if they're available. As soon as they clearly accept or decline, call "
        "respond_to_coverage with accepted true or false. Thank them and keep it short."
    )


def _unregistered_message() -> str:
    return (
        "I couldn't match this number to a registered staff member. "
        "Please sign in on the web portal and register your phone number first, "
        "then call back."
    )


async def _run_tool_loop(
    messages: list[dict[str, Any]],
    staff_id: str,
    tool_schemas: list[dict[str, Any]],
    tool_context: dict[str, Any] | None = None,
) -> str:
    """Run chat completions + tool execution until the model returns final text."""
    client = get_client()

    async with connection() as conn:
        for _ in range(MAX_TOOL_ROUNDS):
            resp = await client.chat.completions.create(
                model=settings.nebius_chat_model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                return msg.content or ""

            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                try:
                    result = await tools.dispatch(
                        call.function.name, args, conn, staff_id, tool_context
                    )
                except Exception as exc:  # noqa: BLE001 - surface tool errors to the model
                    result = {"ok": False, "error": "tool_exception", "message": str(exc)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, default=str),
                    }
                )

    return "Sorry, I got stuck working through that. Could you try rephrasing?"


def _sse_chunk(completion_id: str, created: int, delta: dict[str, Any], finish: str | None) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": settings.nebius_chat_model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload)}\n\n"


async def stream_response(
    incoming_messages: list[dict[str, Any]],
    staff: dict[str, Any] | None,
    mode: str = "inbound",
    coverage_context: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Yield OpenAI-compatible SSE chunks for VAPI's custom-LLM endpoint.

    mode="inbound": staff manages their own schedule.
    mode="outbound": calling a candidate (coverage_context) to cover a shift.
    """
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    # First chunk announces the assistant role (OpenAI streaming convention).
    yield _sse_chunk(completion_id, created, {"role": "assistant"}, None)

    convo = [m for m in incoming_messages if m.get("role") in ("user", "assistant")]

    try:
        if mode == "outbound" and coverage_context:
            messages = [{"role": "system", "content": coverage_system_prompt(coverage_context)}]
            messages.extend(convo)
            text = await _run_tool_loop(
                messages,
                staff_id=coverage_context["candidate_staff_id"],
                tool_schemas=tools.OUTBOUND_TOOL_SCHEMAS,
                tool_context={
                    "coverage_request_id": coverage_context["coverage_request_id"],
                    "candidate_staff_id": coverage_context["candidate_staff_id"],
                },
            )
        elif staff is None:
            text = _unregistered_message()
        else:
            messages = [{"role": "system", "content": system_prompt(staff)}]
            messages.extend(convo)
            text = await _run_tool_loop(
                messages, str(staff["id"]), tools.INBOUND_TOOL_SCHEMAS
            )
    except Exception:  # noqa: BLE001 - never drop the call; speak a fallback
        text = "Sorry, I'm having trouble reaching the scheduling system right now. Please try again in a moment."

    # Stream the final text word-by-word so VAPI's TTS can start speaking early.
    for token in _chunk_text(text):
        yield _sse_chunk(completion_id, created, {"content": token}, None)

    yield _sse_chunk(completion_id, created, {}, "stop")
    yield "data: [DONE]\n\n"


def _chunk_text(text: str) -> list[str]:
    """Split into small streamable pieces while preserving spacing."""
    if not text:
        return [""]
    words = text.split(" ")
    return [w if i == 0 else " " + w for i, w in enumerate(words)]
