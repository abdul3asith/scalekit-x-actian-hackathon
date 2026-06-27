"""Integration tests for the overlap-safe schedule layer, run against the real
Postgres exclusion constraint. Skips if Postgres isn't reachable."""

import pytest_asyncio

from app.data import schedules

TEST_PHONE = "+19998887777"


@pytest_asyncio.fixture
async def staff_id(db_conn):
    """A throwaway staff row, cleaned up after the test (shifts cascade-delete)."""
    async with db_conn.cursor() as cur:
        await cur.execute("DELETE FROM staff WHERE phone_e164 = %s", (TEST_PHONE,))
        await cur.execute(
            "INSERT INTO staff (full_name, phone_e164) VALUES ('Test User', %s) RETURNING id",
            (TEST_PHONE,),
        )
        row = await cur.fetchone()
    yield str(row["id"])
    async with db_conn.cursor() as cur:
        await cur.execute("DELETE FROM staff WHERE phone_e164 = %s", (TEST_PHONE,))


async def test_overlap_is_rejected_adjacent_is_allowed(db_conn, staff_id):
    base = "2026-09-01"

    ok = await schedules.set_shift(db_conn, staff_id, f"{base}T09:00:00+00", f"{base}T17:00:00+00")
    assert ok["ok"] is True

    overlap = await schedules.set_shift(db_conn, staff_id, f"{base}T16:00:00+00", f"{base}T20:00:00+00")
    assert overlap["ok"] is False
    assert overlap["error"] == "overlap"
    assert overlap["conflicts"], "overlap should report the conflicting shift"

    adjacent = await schedules.set_shift(db_conn, staff_id, f"{base}T17:00:00+00", f"{base}T21:00:00+00")
    assert adjacent["ok"] is True


async def test_cancel_frees_the_slot(db_conn, staff_id):
    base = "2026-09-02"
    first = await schedules.set_shift(db_conn, staff_id, f"{base}T09:00:00+00", f"{base}T17:00:00+00")
    assert first["ok"] is True

    blocked = await schedules.set_shift(db_conn, staff_id, f"{base}T10:00:00+00", f"{base}T12:00:00+00")
    assert blocked["ok"] is False

    cancelled = await schedules.cancel_shift(db_conn, staff_id, first["shift"]["shift_id"])
    assert cancelled["ok"] is True

    now_ok = await schedules.set_shift(db_conn, staff_id, f"{base}T10:00:00+00", f"{base}T12:00:00+00")
    assert now_ok["ok"] is True


async def test_invalid_time_range_rejected(db_conn, staff_id):
    base = "2026-09-03"
    res = await schedules.set_shift(db_conn, staff_id, f"{base}T12:00:00+00", f"{base}T09:00:00+00")
    assert res["ok"] is False
    assert res["error"] == "invalid_time"


async def test_isolation_other_staff_unaffected(db_conn, staff_id):
    """A shift for one staff member never blocks another's identical slot."""
    base = "2026-09-04"
    await schedules.set_shift(db_conn, staff_id, f"{base}T09:00:00+00", f"{base}T17:00:00+00")

    async with db_conn.cursor() as cur:
        await cur.execute("DELETE FROM staff WHERE phone_e164 = %s", ("+19998887778",))
        await cur.execute(
            "INSERT INTO staff (full_name, phone_e164) VALUES ('Other', %s) RETURNING id",
            ("+19998887778",),
        )
        other = str((await cur.fetchone())["id"])
    try:
        res = await schedules.set_shift(db_conn, other, f"{base}T09:00:00+00", f"{base}T17:00:00+00")
        assert res["ok"] is True  # same slot, different staff -> allowed
    finally:
        async with db_conn.cursor() as cur:
            await cur.execute("DELETE FROM staff WHERE phone_e164 = %s", ("+19998887778",))
