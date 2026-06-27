# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A voice-driven staff scheduling assistant. Staff phone in and check/set/adjust their shifts by voice. The
defining architectural choice: **the backend is the LLM**. It registers with VAPI as a "custom LLM" — an
OpenAI-compatible `/chat/completions` endpoint — so VAPI handles only voice (STT/TTS) while this FastAPI app
runs native function-calling against Nebius and is the **only** component that touches data.

Two principles drive everything:
- **Correctness lives in the data layer, never the LLM.** No-double-booking is a Postgres `EXCLUDE` constraint
  (`migrations/001_init.sql`), not a prompt instruction. Tool functions catch the exclusion violation and turn
  it into a clean message for the model.
- **Every tool call is scoped to a verified `staff_id`.** The model never gets raw DB access; `tools.dispatch`
  always passes the resolved `staff_id` down to the data layer.

## Commands

```bash
make install        # deps via scripts/install.sh — DO NOT use plain `pip install -r` (see protobuf note below)
make db-up          # start Postgres (applies migrations/001 on FIRST boot only)
make run            # uvicorn app.main:app --reload --port 8000
make seed           # idempotent demo staff + shifts (scripts/seed_demo.py)
make test           # pytest -q
make vapi           # create the two VAPI assistants + squad (scripts/setup_vapi_assistant.py)

pytest tests/test_coverage_integration.py                                   # one file
pytest tests/test_coverage_integration.py::test_sequential_decline_then_exhausted   # one test
```

DB-integration tests **skip** (not fail) when Postgres is unreachable — see the `db_conn` fixture in
`tests/conftest.py`. So a green run with Postgres down means only the unit tests actually ran.

Test the voice path without voice — impersonate VAPI by streaming a completion as a known caller:
```bash
curl -N -X POST http://localhost:8000/chat/completions \
  -H "Authorization: Bearer $BACKEND_API_KEY" \
  -H "x-caller-number: +14155550123" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What shifts do I have this week?"}]}'
```

## Architecture

Request flow (`app/routes/vapi.py` → `app/llm/loop.py` → `app/llm/tools.py` → `app/data/*`):

1. **`/chat/completions`** (`routes/vapi.py`) is the single entrypoint VAPI calls. It validates a static
   bearer token, extracts the caller's phone (tries several body/header shapes via `_extract_phone`), and
   reads `metadata.mode` to branch **inbound vs outbound**.
2. **`stream_response`** (`llm/loop.py`) builds the system prompt, then `_run_tool_loop` drives Nebius with
   `tool_choice="auto"` for up to `MAX_TOOL_ROUNDS`, executing each tool call server-side and feeding results
   back. The final assistant text is streamed back as OpenAI-compatible SSE chunks (word-by-word so TTS starts
   early). **The loop never raises out** — any failure becomes a spoken fallback so the call doesn't drop.
3. **`tools.dispatch`** (`llm/tools.py`) maps a tool name to a data-layer call, injecting `staff_id`. Two
   schema sets: `INBOUND_TOOL_SCHEMAS` (manage own schedule + memory + request coverage) and
   `OUTBOUND_TOOL_SCHEMAS` (just `respond_to_coverage`).

### The two modes

One endpoint, one custom-LLM, behaviour switched by call metadata:
- **inbound** (default): a staff member managing their own schedule. Identity resolved from caller phone →
  `staff_id`. Unregistered numbers get a "please onboard on the web first" message.
- **outbound**: *we* placed this call to ask a candidate to cover a shift. The handoff context
  (`coverage_request_id`, `candidate_staff_id`) arrives in call `metadata`, set by us when we dialed.

`scripts/setup_vapi_assistant.py` creates two VAPI assistants (inbound scheduler, outbound coverage caller)
in a squad — both point their custom-LLM `url` at this backend; the backend, not VAPI, decides behaviour.

### Identity bridge (the crux of per-user isolation)

A voice call only gives us a phone number. The mapping `phone_e164 → verified staff identity` is established
once, over the web:
- `routes/web.py`: `/auth/login` → Scalekit → `/auth/callback` → `/register-phone`.
- `auth/scalekit.py`: wraps the Scalekit SDK. `authenticate()` normalizes the SDK's variable response shape —
  `organization_id` is **top-level** on the result, while user claims are camelCase under `user` (`sub`→`id`).
- `auth/identity.py`: `resolve_staff_by_phone` (call time) and `upsert_staff` (onboarding). Phone is
  normalized to E.164 on both write and lookup, so they must stay consistent.

### Coverage flow (the most involved feature)

When a staff member asks for leave on a shift, the backend finds and calls replacements sequentially:
- `services/coverage_flow.py` orchestrates: `start_coverage` → `call_next` (find next same-role, *free*
  candidate not already tried) → `vapi_out.place_coverage_call` → on decline, advance; on accept, reassign.
- `data/coverage.py` is the DB side. `find_next_candidate` is the matching query (same role, no overlapping
  active shift, not previously attempted). `accept` reassigns the shift to the candidate — the same
  `no_double_book` exclusion constraint still guarantees safety at reassignment time.
- `services/vapi_out.py` places the outbound VAPI call, passing context two ways: `metadata` (so our backend
  knows which request this call is about) and `assistantOverrides.variableValues` (for the spoken first
  message template).

### Per-user memory (`data/memory.py`)

Actian VectorAI has no built-in multi-tenancy, so isolation is **one collection per staff member**
(`user-<staff_id>-memories`). Embeddings come from Nebius; collection vector size must equal
`settings.embed_dim` (4096 for Qwen3-Embedding-8B). All Actian-specific calls are centralized in
`_AdapterActian` — the one place to touch if the client API changes.

## Things that will bite you

- **Never `pip install -r requirements.txt` for the Scalekit + Actian combo.** `scalekit-sdk-python` pins
  `protobuf<7`, which silently downgrades the version `actian-vectorai-client` needs. `scripts/install.sh`
  installs Scalekit `--no-deps` then reasserts `protobuf>=6.31.1,<7` / `grpcio-status>=1.67.0`. Protobuf is
  held on the 6.x line (Scalekit's generated `*_pb2` modules don't load on 7.x).
- **`migrations/002_coverage.sql` is NOT auto-applied.** `docker-compose.yml` only mounts `001_init.sql` into
  the Postgres init dir, and init scripts run **only on first boot of an empty volume**. After 001 has booted,
  apply 002 (and any later migration) by hand: `psql "$DATABASE_URL" -f migrations/002_coverage.sql`. The
  coverage feature won't work until you do.
- **The connection pool is autocommit** (`data/db.py`) — each statement is its own transaction. Multi-statement
  operations (e.g. coverage `accept`) are **not** atomic across statements; don't assume rollback semantics.
- **Scalekit and Actian imports are guarded** (`auth/scalekit.py`, `data/memory.py`). The app boots without the
  wheels; auth returns 503 and memory degrades to a no-op (`ACTIAN_ENABLED=false` does the same). Scheduling
  still works. Don't "fix" the bare-import guards.
- **Config is a single `settings` singleton** (`app/config.py`, pydantic-settings, `lru_cache`d). Add new env
  vars there; derived booleans like `outbound_calling_ready` / `scalekit_configured` gate optional features.

## Git workflow

Branch type vocabulary in use here includes `setup/` (initial subsystem scaffolding) alongside the standard
`feat/ fix/ refactor/ docs/ chore/ test/`. Follow the user's global workflow: branch from fresh `main`, stage
explicitly, one logical change per PR, hand back the PR URL without merging.
