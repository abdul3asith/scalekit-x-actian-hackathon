"""Coverage orchestration: combines the DB layer (app.data.coverage) with the
outbound caller (app.services.vapi_out). Sequential strategy -- one candidate at
a time; on decline we advance to the next same-role, available staff member."""

from __future__ import annotations

from typing import Any

import psycopg

from app.data import coverage
from app.services import vapi_out


async def start_coverage(
    conn: psycopg.AsyncConnection, requester_staff_id: str, shift_id: str
) -> dict[str, Any]:
    """Open a coverage request for the requester's shift and call the first candidate."""
    res = await coverage.create_request(conn, requester_staff_id, shift_id)
    if not res.get("ok"):
        return res
    return await call_next(conn, res["coverage_request_id"])


async def call_next(conn: psycopg.AsyncConnection, coverage_request_id: str) -> dict[str, Any]:
    """Find and call the next same-role, available candidate (or mark exhausted)."""
    ctx = await coverage.context(conn, coverage_request_id)
    if ctx is None:
        return {"ok": False, "error": "not_found"}
    if ctx["status"] != "open":
        return {"ok": True, "status": ctx["status"], "message": "Coverage already resolved."}

    candidate = await coverage.find_next_candidate(conn, coverage_request_id)
    if candidate is None:
        await coverage.mark_request(conn, coverage_request_id, "exhausted")
        return {
            "ok": True,
            "status": "exhausted",
            "message": "No more same-role, available staff to call.",
        }

    call_id = await vapi_out.place_coverage_call(ctx, candidate)
    await coverage.record_attempt(conn, coverage_request_id, candidate["staff_id"], call_id)
    return {
        "ok": True,
        "status": "calling",
        "candidate": candidate,
        "call_placed": bool(call_id),
        "handoff": vapi_out.handoff_payload(ctx, candidate),
    }


async def handle_response(
    conn: psycopg.AsyncConnection,
    coverage_request_id: str,
    candidate_staff_id: str,
    accepted: bool,
) -> dict[str, Any]:
    """Record a candidate's accept/decline; on decline, call the next candidate."""
    if accepted:
        return await coverage.accept(conn, coverage_request_id, candidate_staff_id)

    await coverage.decline(conn, coverage_request_id, candidate_staff_id)
    nxt = await call_next(conn, coverage_request_id)
    return {"ok": True, "declined": True, "next": nxt}
