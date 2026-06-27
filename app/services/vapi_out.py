"""Place outbound VAPI calls to candidate staff for shift coverage.

The handoff JSON (coverage context) is passed to the outbound assistant two ways:
- ``metadata`` on the call -> forwarded to our custom-LLM endpoint so the backend
  knows which coverage request this call is about (mode = outbound).
- ``assistantOverrides.variableValues`` -> used by the assistant's spoken
  firstMessage template ({{requesterName}}, {{shiftSummary}}, {{candidateName}}).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("uvicorn.error")


def shift_summary(ctx: dict[str, Any]) -> str:
    """Human/voice-friendly description of the shift to cover."""
    shift = ctx["shift"]
    try:
        start = datetime.fromisoformat(shift["start"])
        end = datetime.fromisoformat(shift["end"])
        when = start.strftime("%A %b %-d, %-I:%M %p") + end.strftime(" to %-I:%M %p")
    except Exception:  # noqa: BLE001
        when = f"{shift['start']} to {shift['end']}"
    role = shift.get("role") or "shift"
    loc = f" at {shift['location']}" if shift.get("location") else ""
    return f"{role}{loc} on {when}"


def handoff_payload(ctx: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """The structured handoff JSON shared from inbound -> outbound."""
    return {
        "coverage_request_id": ctx["coverage_request_id"],
        "shift": ctx["shift"],
        "requester": ctx["requester"],
        "candidate": candidate,
    }


async def place_coverage_call(
    ctx: dict[str, Any], candidate: dict[str, Any]
) -> str | None:
    """Dial a candidate via VAPI's outbound API. Returns the call id, or None if
    outbound calling isn't configured (so the flow stays testable without a number)."""
    payload = handoff_payload(ctx, candidate)

    if not settings.outbound_calling_ready:
        logger.warning(
            "Outbound calling not configured (need VAPI_API_KEY, VAPI_PHONE_NUMBER_ID, "
            "VAPI_OUTBOUND_ASSISTANT_ID). Would have called %s for %s",
            candidate.get("phone"),
            payload["coverage_request_id"],
        )
        return None

    body = {
        "assistantId": settings.vapi_outbound_assistant_id,
        "phoneNumberId": settings.vapi_phone_number_id,
        "customer": {"number": candidate["phone"]},
        "metadata": {
            "mode": "outbound",
            "coverage_request_id": ctx["coverage_request_id"],
            "candidate_staff_id": candidate["staff_id"],
        },
        "assistantOverrides": {
            "variableValues": {
                "requesterName": ctx["requester"]["name"],
                "candidateName": candidate.get("name") or "there",
                "shiftSummary": shift_summary(ctx),
            }
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.vapi_base_url}/call",
            headers={"Authorization": f"Bearer {settings.vapi_api_key}"},
            json=body,
        )
    if resp.status_code >= 300:
        logger.error("VAPI outbound call failed (%s): %s", resp.status_code, resp.text)
        return None
    call_id = resp.json().get("id")
    logger.info("Placed outbound coverage call %s to %s", call_id, candidate.get("phone"))
    return call_id
