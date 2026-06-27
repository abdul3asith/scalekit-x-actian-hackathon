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


def _unregistered_message() -> str:
    return (
        "I couldn't match this number to a registered staff member. "
        "Please sign in on the web portal and register your phone number first, "
        "then call back."
    )


async def _run_tool_loop(messages: list[dict[str, Any]], staff: dict[str, Any]) -> str:
    """Run chat completions + tool execution until the model returns final text."""
    client = get_client()
    staff_id = str(staff["id"])

    async with connection() as conn:
        for _ in range(MAX_TOOL_ROUNDS):
            resp = await client.chat.completions.create(
                model=settings.nebius_chat_model,
                messages=messages,
                tools=tools.TOOL_SCHEMAS,
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
                    result = await tools.dispatch(call.function.name, args, conn, staff_id)
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
    incoming_messages: list[dict[str, Any]], staff: dict[str, Any] | None
) -> AsyncIterator[str]:
    """Yield OpenAI-compatible SSE chunks for VAPI's custom-LLM endpoint."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    # First chunk announces the assistant role (OpenAI streaming convention).
    yield _sse_chunk(completion_id, created, {"role": "assistant"}, None)

    if staff is None:
        text = _unregistered_message()
    else:
        messages = [{"role": "system", "content": system_prompt(staff)}]
        # Keep only user/assistant turns from VAPI; we own the system + tool messages.
        messages.extend(
            m for m in incoming_messages if m.get("role") in ("user", "assistant")
        )
        try:
            text = await _run_tool_loop(messages, staff)
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
