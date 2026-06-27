-- Shift-coverage flow: when a staff member requests leave on a shift, the backend
-- finds same-role, available candidates and calls them (sequentially) to cover.

-- Staff need a role so we can match candidates to a shift's role.
ALTER TABLE staff ADD COLUMN IF NOT EXISTS role TEXT;

-- One coverage request per shift the requester wants covered.
CREATE TABLE IF NOT EXISTS coverage_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shift_id            UUID NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
    requester_staff_id  UUID NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'covered', 'exhausted', 'cancelled')),
    covered_by_staff_id UUID REFERENCES staff(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per candidate we call, in order, for a coverage request.
CREATE TABLE IF NOT EXISTS coverage_attempts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coverage_request_id UUID NOT NULL REFERENCES coverage_requests(id) ON DELETE CASCADE,
    candidate_staff_id  UUID NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'calling'
                        CHECK (status IN ('calling', 'accepted', 'declined', 'no_answer', 'skipped')),
    vapi_call_id        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_coverage_attempts_req ON coverage_attempts(coverage_request_id);
CREATE INDEX IF NOT EXISTS idx_coverage_requests_shift ON coverage_requests(shift_id);
