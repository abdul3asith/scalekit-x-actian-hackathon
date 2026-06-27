-- Schedule store schema. Correctness (no double-booking) is enforced HERE,
-- at the data layer, not by the LLM.

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist; -- required for the EXCLUDE constraint below

-- Verified staff identities. scalekit_user_id + phone_e164 are written during the
-- one-time web onboarding (Scalekit login + phone registration). A voice call is
-- resolved to a staff_id by matching the caller's number against phone_e164.
CREATE TABLE IF NOT EXISTS staff (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scalekit_user_id  TEXT UNIQUE,
    full_name         TEXT NOT NULL,
    email             TEXT,
    phone_e164        TEXT UNIQUE NOT NULL,
    org_id            TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shifts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_id    UUID NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    role        TEXT,
    location    TEXT,
    start_time  TIMESTAMPTZ NOT NULL,
    end_time    TIMESTAMPTZ NOT NULL,
    notes       TEXT,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT shift_time_valid CHECK (end_time > start_time),

    -- THE correctness guarantee: a staff member cannot have two ACTIVE shifts whose
    -- time ranges overlap. An overlapping INSERT/UPDATE raises an exclusion violation,
    -- which the backend catches and reports back to the agent as a clean message.
    CONSTRAINT no_double_book EXCLUDE USING gist (
        staff_id WITH =,
        tstzrange(start_time, end_time) WITH &&
    ) WHERE (status = 'active')
);

CREATE INDEX IF NOT EXISTS idx_shifts_staff_time ON shifts (staff_id, start_time);
