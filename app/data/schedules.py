"""Overlap-safe schedule operations. Every function is scoped to a single
staff_id, and double-booking is prevented by the Postgres ``no_double_book``
exclusion constraint (see migrations/001_init.sql) -- not by the LLM.

All functions return plain JSON-serializable dicts, because their results are fed
straight back to the model as tool outputs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg


def _parse_dt(value: str) -> datetime:
    """Parse an ISO-8601 datetime the model produced (accepts a trailing 'Z')."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _shift_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "shift_id": str(row["id"]),
        "role": row.get("role"),
        "location": row.get("location"),
        "start_time": row["start_time"].isoformat(),
        "end_time": row["end_time"].isoformat(),
        "notes": row.get("notes"),
        "status": row["status"],
    }


async def get_my_schedule(
    conn: psycopg.AsyncConnection,
    staff_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Return the staff member's active shifts, optionally within a window."""
    clauses = ["staff_id = %(staff_id)s", "status = 'active'"]
    params: dict[str, Any] = {"staff_id": staff_id}
    if date_from:
        clauses.append("end_time >= %(date_from)s")
        params["date_from"] = _parse_dt(date_from)
    if date_to:
        clauses.append("start_time <= %(date_to)s")
        params["date_to"] = _parse_dt(date_to)

    sql = (
        "SELECT id, role, location, start_time, end_time, notes, status "
        f"FROM shifts WHERE {' AND '.join(clauses)} ORDER BY start_time"
    )
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        rows = await cur.fetchall()
    return {"shifts": [_shift_to_dict(r) for r in rows], "count": len(rows)}


async def check_availability(
    conn: psycopg.AsyncConnection, staff_id: str, start: str, end: str
) -> dict[str, Any]:
    """Report whether a proposed window collides with existing active shifts."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, role, location, start_time, end_time, notes, status
            FROM shifts
            WHERE staff_id = %(staff_id)s
              AND status = 'active'
              AND tstzrange(start_time, end_time) && tstzrange(%(start)s, %(end)s)
            ORDER BY start_time
            """,
            {"staff_id": staff_id, "start": _parse_dt(start), "end": _parse_dt(end)},
        )
        rows = await cur.fetchall()
    return {
        "available": len(rows) == 0,
        "conflicts": [_shift_to_dict(r) for r in rows],
    }


async def set_shift(
    conn: psycopg.AsyncConnection,
    staff_id: str,
    start: str,
    end: str,
    role: str | None = None,
    location: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Create an active shift. Relies on the exclusion constraint to reject overlaps."""
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO shifts (staff_id, role, location, start_time, end_time, notes)
                VALUES (%(staff_id)s, %(role)s, %(location)s, %(start)s, %(end)s, %(notes)s)
                RETURNING id, role, location, start_time, end_time, notes, status
                """,
                {
                    "staff_id": staff_id,
                    "role": role,
                    "location": location,
                    "start": _parse_dt(start),
                    "end": _parse_dt(end),
                    "notes": notes,
                },
            )
            row = await cur.fetchone()
        return {"ok": True, "shift": _shift_to_dict(row)}
    except psycopg.errors.ExclusionViolation:
        conflicts = await check_availability(conn, staff_id, start, end)
        return {
            "ok": False,
            "error": "overlap",
            "message": "That time overlaps an existing shift. Pick a non-overlapping slot.",
            "conflicts": conflicts["conflicts"],
        }
    except psycopg.errors.CheckViolation:
        return {
            "ok": False,
            "error": "invalid_time",
            "message": "End time must be after start time.",
        }


async def adjust_shift(
    conn: psycopg.AsyncConnection,
    staff_id: str,
    shift_id: str,
    new_start: str | None = None,
    new_end: str | None = None,
    new_role: str | None = None,
    new_location: str | None = None,
) -> dict[str, Any]:
    """Update fields on one of the staff member's own shifts."""
    sets: list[str] = []
    params: dict[str, Any] = {"shift_id": shift_id, "staff_id": staff_id}
    if new_start is not None:
        sets.append("start_time = %(start)s")
        params["start"] = _parse_dt(new_start)
    if new_end is not None:
        sets.append("end_time = %(end)s")
        params["end"] = _parse_dt(new_end)
    if new_role is not None:
        sets.append("role = %(role)s")
        params["role"] = new_role
    if new_location is not None:
        sets.append("location = %(location)s")
        params["location"] = new_location
    if not sets:
        return {"ok": False, "error": "no_changes", "message": "Nothing to update."}

    try:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE shifts SET {', '.join(sets)}
                WHERE id = %(shift_id)s AND staff_id = %(staff_id)s AND status = 'active'
                RETURNING id, role, location, start_time, end_time, notes, status
                """,
                params,
            )
            row = await cur.fetchone()
        if row is None:
            return {"ok": False, "error": "not_found", "message": "No such active shift for you."}
        return {"ok": True, "shift": _shift_to_dict(row)}
    except psycopg.errors.ExclusionViolation:
        return {
            "ok": False,
            "error": "overlap",
            "message": "The new time overlaps another of your shifts.",
        }
    except psycopg.errors.CheckViolation:
        return {"ok": False, "error": "invalid_time", "message": "End must be after start."}


async def cancel_shift(
    conn: psycopg.AsyncConnection, staff_id: str, shift_id: str
) -> dict[str, Any]:
    """Cancel one of the staff member's own shifts (soft delete)."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE shifts SET status = 'cancelled'
            WHERE id = %(shift_id)s AND staff_id = %(staff_id)s AND status = 'active'
            RETURNING id
            """,
            {"shift_id": shift_id, "staff_id": staff_id},
        )
        row = await cur.fetchone()
    if row is None:
        return {"ok": False, "error": "not_found", "message": "No such active shift for you."}
    return {"ok": True, "cancelled_shift_id": str(row["id"])}
