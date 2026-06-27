"""Seed reproducible demo data: a couple of staff with registered phones and a
few shifts each. Idempotent -- safe to run repeatedly.

Usage:  python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio

from app.data.db import close_pool, connection, open_pool

DEMO_STAFF = [
    {"name": "Alice Demo", "phone": "+14155550123", "uid": "demo_alice"},
    {"name": "Bob Demo", "phone": "+14155550199", "uid": "demo_bob"},
]

# (phone, role, start, end)
DEMO_SHIFTS = [
    ("+14155550123", "guard", "2026-07-01T10:00:00+00", "2026-07-01T12:00:00+00"),
    ("+14155550123", "guard", "2026-07-01T17:00:00+00", "2026-07-01T21:00:00+00"),
    ("+14155550199", "guard", "2026-07-01T09:00:00+00", "2026-07-01T17:00:00+00"),
]


async def main() -> None:
    await open_pool()
    try:
        async with connection() as conn:
            async with conn.cursor() as cur:
                for s in DEMO_STAFF:
                    await cur.execute("DELETE FROM staff WHERE phone_e164 = %s", (s["phone"],))
                    await cur.execute(
                        "INSERT INTO staff (full_name, phone_e164, scalekit_user_id) "
                        "VALUES (%s, %s, %s)",
                        (s["name"], s["phone"], s["uid"]),
                    )
                for phone, role, start, end in DEMO_SHIFTS:
                    await cur.execute(
                        """
                        INSERT INTO shifts (staff_id, role, start_time, end_time)
                        SELECT id, %s, %s, %s FROM staff WHERE phone_e164 = %s
                        """,
                        (role, start, end, phone),
                    )
        print("Seeded demo staff and shifts:")
        for s in DEMO_STAFF:
            print(f"  {s['name']:12} {s['phone']}")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
