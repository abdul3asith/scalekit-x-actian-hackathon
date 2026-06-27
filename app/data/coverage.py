"""Shift-coverage orchestration logic (DB side).

Flow: a requester asks to be covered for one of their shifts -> we create a
coverage_request -> repeatedly pick the next same-role, available candidate (who
hasn't been tried yet) and call them -> on accept, the shift is reassigned to the
candidate (the Postgres exclusion constraint still guarantees no double-booking).
"""

from __future__ import annotations

from typing import Any

import psycopg


def _staff_brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "staff_id": str(row["id"]),
        "name": row.get("full_name"),
        "phone": row.get("phone_e164"),
        "role": row.get("role"),
    }


async def create_request(
    conn: psycopg.AsyncConnection, requester_staff_id: str, shift_id: str
) -> dict[str, Any]:
    """Open a coverage request for one of the requester's own active shifts."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, role, start_time, end_time FROM shifts "
            "WHERE id = %s AND staff_id = %s AND status = 'active'",
            (shift_id, requester_staff_id),
        )
        shift = await cur.fetchone()
        if shift is None:
            return {"ok": False, "error": "not_found", "message": "No such active shift of yours."}

        # Reuse an existing open request for this shift if present.
        await cur.execute(
            "SELECT id FROM coverage_requests WHERE shift_id = %s AND status = 'open'",
            (shift_id,),
        )
        existing = await cur.fetchone()
        if existing:
            return {"ok": True, "coverage_request_id": str(existing["id"]), "reused": True}

        await cur.execute(
            "INSERT INTO coverage_requests (shift_id, requester_staff_id) "
            "VALUES (%s, %s) RETURNING id",
            (shift_id, requester_staff_id),
        )
        row = await cur.fetchone()
    return {"ok": True, "coverage_request_id": str(row["id"])}


async def context(conn: psycopg.AsyncConnection, coverage_request_id: str) -> dict[str, Any] | None:
    """Full context for a coverage request: the shift + requester (for prompts)."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT cr.id, cr.status, cr.shift_id, cr.requester_staff_id,
                   sh.role, sh.location, sh.start_time, sh.end_time,
                   st.full_name AS requester_name
            FROM coverage_requests cr
            JOIN shifts sh ON sh.id = cr.shift_id
            JOIN staff st ON st.id = cr.requester_staff_id
            WHERE cr.id = %s
            """,
            (coverage_request_id,),
        )
        r = await cur.fetchone()
    if r is None:
        return None
    return {
        "coverage_request_id": str(r["id"]),
        "status": r["status"],
        "shift": {
            "shift_id": str(r["shift_id"]),
            "role": r["role"],
            "location": r["location"],
            "start": r["start_time"].isoformat(),
            "end": r["end_time"].isoformat(),
        },
        "requester": {
            "staff_id": str(r["requester_staff_id"]),
            "name": r["requester_name"],
        },
    }


async def find_next_candidate(
    conn: psycopg.AsyncConnection, coverage_request_id: str
) -> dict[str, Any] | None:
    """Next same-role, available staff member who hasn't been tried for this request."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT cr.requester_staff_id, sh.role, sh.start_time, sh.end_time "
            "FROM coverage_requests cr JOIN shifts sh ON sh.id = cr.shift_id "
            "WHERE cr.id = %s",
            (coverage_request_id,),
        )
        req = await cur.fetchone()
        if req is None:
            return None

        await cur.execute(
            """
            SELECT s.id, s.full_name, s.phone_e164, s.role
            FROM staff s
            WHERE s.id <> %(requester)s
              AND s.phone_e164 IS NOT NULL
              AND (%(role)s::text IS NULL OR s.role = %(role)s)
              -- not already tried for this request
              AND NOT EXISTS (
                  SELECT 1 FROM coverage_attempts a
                  WHERE a.coverage_request_id = %(req_id)s AND a.candidate_staff_id = s.id
              )
              -- free: no overlapping active shift
              AND NOT EXISTS (
                  SELECT 1 FROM shifts x
                  WHERE x.staff_id = s.id AND x.status = 'active'
                    AND tstzrange(x.start_time, x.end_time)
                        && tstzrange(%(start)s, %(end)s)
              )
            ORDER BY s.full_name
            LIMIT 1
            """,
            {
                "requester": req["requester_staff_id"],
                "role": req["role"],
                "req_id": coverage_request_id,
                "start": req["start_time"],
                "end": req["end_time"],
            },
        )
        cand = await cur.fetchone()
    return _staff_brief(cand) if cand else None


async def record_attempt(
    conn: psycopg.AsyncConnection,
    coverage_request_id: str,
    candidate_staff_id: str,
    vapi_call_id: str | None = None,
) -> str:
    async with conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO coverage_attempts (coverage_request_id, candidate_staff_id, vapi_call_id) "
            "VALUES (%s, %s, %s) RETURNING id",
            (coverage_request_id, candidate_staff_id, vapi_call_id),
        )
        row = await cur.fetchone()
    return str(row["id"])


async def mark_request(
    conn: psycopg.AsyncConnection,
    coverage_request_id: str,
    status: str,
    covered_by: str | None = None,
) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE coverage_requests SET status = %s, covered_by_staff_id = %s, updated_at = now() "
            "WHERE id = %s",
            (status, covered_by, coverage_request_id),
        )


async def accept(
    conn: psycopg.AsyncConnection, coverage_request_id: str, candidate_staff_id: str
) -> dict[str, Any]:
    """Candidate accepts: reassign the shift to them and close the request."""
    ctx = await context(conn, coverage_request_id)
    if ctx is None:
        return {"ok": False, "error": "not_found"}
    if ctx["status"] != "open":
        return {"ok": False, "error": "already_resolved", "message": "This shift is already settled."}

    shift_id = ctx["shift"]["shift_id"]
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE shifts SET staff_id = %s WHERE id = %s AND status = 'active'",
                (candidate_staff_id, shift_id),
            )
            await cur.execute(
                "UPDATE coverage_attempts SET status = 'accepted' "
                "WHERE coverage_request_id = %s AND candidate_staff_id = %s",
                (coverage_request_id, candidate_staff_id),
            )
    except psycopg.errors.ExclusionViolation:
        return {"ok": False, "error": "now_conflicting", "message": "You just got booked elsewhere for that time."}

    await mark_request(conn, coverage_request_id, "covered", covered_by=candidate_staff_id)
    return {"ok": True, "covered_shift_id": shift_id}


async def decline(
    conn: psycopg.AsyncConnection, coverage_request_id: str, candidate_staff_id: str
) -> dict[str, Any]:
    """Candidate declines: mark the attempt; caller decides whether to try the next."""
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE coverage_attempts SET status = 'declined' "
            "WHERE coverage_request_id = %s AND candidate_staff_id = %s",
            (coverage_request_id, candidate_staff_id),
        )
    return {"ok": True}
