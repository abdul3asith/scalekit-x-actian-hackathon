"""Bridge from a phone number (what a voice call gives us) to a verified
staff identity (established during Scalekit web onboarding)."""

from __future__ import annotations

import re
from typing import Any

import psycopg


def normalize_phone(raw: str) -> str:
    """Best-effort E.164 normalization: keep digits, preserve a leading '+'."""
    raw = (raw or "").strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    return ("+" + digits) if has_plus else digits


async def resolve_staff_by_phone(
    conn: psycopg.AsyncConnection, phone: str
) -> dict[str, Any] | None:
    """Return the staff row whose phone matches, or None if unregistered."""
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, full_name, email, phone_e164, scalekit_user_id, org_id "
            "FROM staff WHERE phone_e164 = %s",
            (normalized,),
        )
        return await cur.fetchone()


async def upsert_staff(
    conn: psycopg.AsyncConnection,
    *,
    scalekit_user_id: str,
    full_name: str,
    email: str | None,
    phone_e164: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    """Create or update the phone -> verified-identity mapping (onboarding)."""
    normalized = normalize_phone(phone_e164)
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO staff (scalekit_user_id, full_name, email, phone_e164, org_id)
            VALUES (%(uid)s, %(name)s, %(email)s, %(phone)s, %(org)s)
            ON CONFLICT (scalekit_user_id) DO UPDATE
                SET full_name = EXCLUDED.full_name,
                    email = EXCLUDED.email,
                    phone_e164 = EXCLUDED.phone_e164,
                    org_id = EXCLUDED.org_id
            RETURNING id, full_name, email, phone_e164, scalekit_user_id, org_id
            """,
            {
                "uid": scalekit_user_id,
                "name": full_name,
                "email": email,
                "phone": normalized,
                "org": org_id,
            },
        )
        return await cur.fetchone()
