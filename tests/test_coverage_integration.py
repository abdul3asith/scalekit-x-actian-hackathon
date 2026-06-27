"""Integration tests for the shift-coverage flow: same-role + free candidate
selection, sequential advancement on decline, and shift reassignment on accept.
Outbound dialing is not configured in tests, so place_coverage_call() no-ops."""

import pytest_asyncio

from app.data import coverage
from app.services import coverage_flow

PHONES = {
    "R": "+19990000001",  # requester (guard)
    "A": "+19990000002",  # guard, free  -> valid candidate
    "B": "+19990000003",  # guard, busy  -> skipped
    "C": "+19990000004",  # cleaner      -> wrong role, skipped
}


async def _mkstaff(cur, name, phone, role):
    await cur.execute(
        "INSERT INTO staff (full_name, phone_e164, role) VALUES (%s, %s, %s) RETURNING id",
        (name, phone, role),
    )
    return str((await cur.fetchone())["id"])


async def _mkshift(cur, staff_id, role, start, end):
    await cur.execute(
        "INSERT INTO shifts (staff_id, role, start_time, end_time) VALUES (%s,%s,%s,%s) RETURNING id",
        (staff_id, role, start, end),
    )
    return str((await cur.fetchone())["id"])


@pytest_asyncio.fixture
async def world(db_conn):
    """Requester R with a guard shift; A (guard/free), B (guard/busy), C (cleaner)."""
    start, end = "2026-10-01T09:00:00+00", "2026-10-01T17:00:00+00"
    async with db_conn.cursor() as cur:
        for p in PHONES.values():
            await cur.execute("DELETE FROM staff WHERE phone_e164 = %s", (p,))
        ids = {
            "R": await _mkstaff(cur, "Req R", PHONES["R"], "pyrole"),
            "A": await _mkstaff(cur, "Cand A", PHONES["A"], "pyrole"),
            "B": await _mkstaff(cur, "Cand B", PHONES["B"], "pyrole"),
            "C": await _mkstaff(cur, "Cand C", PHONES["C"], "pyrole-other"),
        }
        shift_id = await _mkshift(cur, ids["R"], "pyrole", start, end)
        # B is busy during the shift window.
        await _mkshift(cur, ids["B"], "pyrole", "2026-10-01T10:00:00+00", "2026-10-01T12:00:00+00")
    yield {"ids": ids, "shift_id": shift_id}
    async with db_conn.cursor() as cur:
        for p in PHONES.values():
            await cur.execute("DELETE FROM staff WHERE phone_e164 = %s", (p,))


async def test_picks_same_role_free_candidate_and_reassigns_on_accept(db_conn, world):
    res = await coverage_flow.start_coverage(db_conn, world["ids"]["R"], world["shift_id"])
    assert res["status"] == "calling"
    assert res["candidate"]["staff_id"] == world["ids"]["A"]  # A: guard + free (not B busy, not C cleaner)
    crid = res["handoff"]["coverage_request_id"]

    accept = await coverage_flow.handle_response(db_conn, crid, world["ids"]["A"], accepted=True)
    assert accept["ok"] is True

    async with db_conn.cursor() as cur:
        await cur.execute("SELECT staff_id FROM shifts WHERE id = %s", (world["shift_id"],))
        owner = str((await cur.fetchone())["staff_id"])
    assert owner == world["ids"]["A"]  # shift reassigned to the cover


async def test_sequential_decline_then_exhausted(db_conn, world):
    res = await coverage_flow.start_coverage(db_conn, world["ids"]["R"], world["shift_id"])
    crid = res["handoff"]["coverage_request_id"]
    assert res["candidate"]["staff_id"] == world["ids"]["A"]

    # A declines -> no other same-role, free candidate (B busy, C wrong role) -> exhausted.
    out = await coverage_flow.handle_response(db_conn, crid, world["ids"]["A"], accepted=False)
    assert out["declined"] is True
    assert out["next"]["status"] == "exhausted"

    ctx = await coverage.context(db_conn, crid)
    assert ctx["status"] == "exhausted"
