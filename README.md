# Voice-driven staff scheduling assistant (Scalekit × Actian)

Staff check, set, and adjust their shifts **by voice**. Correctness (no double-booking)
and per-user isolation are enforced at the **data layer**, not left to the LLM.

```
Staff (voice) ── VAPI (STT/TTS) ──▶ Backend (FastAPI, "custom LLM") ──▶ Nebius (LLM inference)
                                          │
                  Scalekit (identity) ────┤
                                          ├──▶ PostgreSQL (schedules, overlap-safe)
                                          └──▶ Actian VectorAI (per-user memory)
```

The backend registers with VAPI as a **custom LLM** (an OpenAI-compatible
`/chat/completions` endpoint). VAPI handles only voice; the backend runs native
function calling against Nebius and is the **only** component that touches data.
Every tool call is scoped to a verified `staff_id`, resolved from the caller's phone
number, which was bound to a Scalekit identity during a one-time web login.

## Stack
| Component | Role |
|-----------|------|
| VAPI | Voice agent (STT/TTS), calls our custom-LLM endpoint |
| Nebius AI Studio | LLM inference + embeddings (OpenAI-compatible) |
| FastAPI backend | Orchestration; the only thing that touches data |
| PostgreSQL | Schedule store; `EXCLUDE` constraint prevents double-booking |
| Actian VectorAI | Per-user isolated memory (`mem_<staff_id>` collections) |
| Scalekit Full Stack Auth | Verified per-user identity (web login + phone mapping) |

## Setup

### 1. Install dependencies (handles the Scalekit ↔ Actian protobuf conflict)
`scalekit-sdk-python` pins `protobuf<7.0.0`, which silently downgrades the version
`actian-vectorai-client` needs. The install script fixes the order:

```bash
python3 -m venv .venv && source .venv/bin/activate
bash scripts/install.sh
```

### 2. Configure
```bash
cp .env.example .env   # then fill in NEBIUS_API_KEY, SCALEKIT_*, BACKEND_API_KEY, etc.
```

### 3. Start Postgres + Actian VectorAI (Postgres schema auto-applies on first boot)
```bash
docker compose up -d
```

### 4. Run the backend
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Expose to VAPI + create the assistant
```bash
ngrok http 8000                       # set PUBLIC_BASE_URL to the https URL in .env
python scripts/setup_vapi_assistant.py
```

## How identity works over voice
1. **Onboarding (web):** staff sign in via Scalekit (`/auth/login` → `/auth/callback`),
   then register their phone at `/register-phone`. This writes `phone_e164 → scalekit_user_id`.
2. **Call time:** VAPI sends the caller's number to `/chat/completions`; the backend
   resolves it to a `staff_id` that scopes every Postgres query and Actian collection.
   Unregistered numbers are asked to onboard first.

## The double-booking guarantee
`migrations/001_init.sql` adds, via `btree_gist`:
```sql
CONSTRAINT no_double_book EXCLUDE USING gist (
    staff_id WITH =,
    tstzrange(start_time, end_time) WITH &&
) WHERE (status = 'active')
```
Overlapping bookings raise an exclusion violation that `app/data/schedules.py` catches
and returns to the agent as a clean "that overlaps an existing shift" message.

## Shift coverage (two assistants + squad)

When a staff member calls in and requests leave on one of their shifts, the system
finds coverage by calling other staff:

1. **Inbound assistant** — the caller asks for leave; the agent calls
   `request_shift_coverage(shift_id)`.
2. **Backend** opens a `coverage_request`, finds the next **same-role, available**
   candidate, and places an **outbound VAPI call** (`POST /call`) using the
   **Outbound assistant**, passing a handoff JSON as call metadata.
3. **Outbound assistant** — asks the candidate to cover the shift; on accept it
   calls `respond_to_coverage(accepted=true)` and the backend **reassigns the shift**
   (the `no_double_book` constraint still guarantees no conflict). On decline, the
   backend advances to the next candidate (sequential).

Both assistants share this backend as their custom LLM; the endpoint switches
behaviour by the call's `metadata.mode` (`inbound` vs `outbound`). They're also
registered as a VAPI **squad**. Create them with `python scripts/setup_vapi_assistant.py`
(after setting `PUBLIC_BASE_URL` to a public tunnel), then set
`VAPI_INBOUND_ASSISTANT_ID` / `VAPI_OUTBOUND_ASSISTANT_ID` / `VAPI_PHONE_NUMBER_ID`.

**Handoff JSON** (inbound → each outbound call):
```json
{
  "coverage_request_id": "uuid",
  "shift": {"shift_id":"uuid","start":"ISO","end":"ISO","role":"guard","location":"..."},
  "requester": {"staff_id":"uuid","name":"Haseeb Khan"},
  "candidate": {"staff_id":"uuid","name":"Alice Demo","phone":"+1..."}
}
```

> **Public tunnel:** VAPI must reach this backend over the internet. Cloudflare quick
> tunnels can be unreliable; an SSH tunnel works well and needs no account:
> `ssh -R 80:localhost:8000 nokey@localhost.run` (or `ngrok http 8000`). Set
> `PUBLIC_BASE_URL` to the printed URL.

## Project layout
```
app/
  config.py            # typed settings
  main.py              # FastAPI wiring + lifespan
  auth/   scalekit.py, identity.py
  data/   db.py, schedules.py, memory.py
  llm/    nebius.py, tools.py, loop.py
  routes/ web.py (onboarding), vapi.py (custom-LLM endpoint)
migrations/001_init.sql
scripts/ install.sh, setup_vapi_assistant.py
docker-compose.yml
```

## Testing without voice
```bash
# Pretend to be VAPI: stream a completion as a known caller number.
curl -N -X POST http://localhost:8000/chat/completions \
  -H "Authorization: Bearer $BACKEND_API_KEY" \
  -H "x-caller-number: +14155550123" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What shifts do I have this week?"}]}'
```

> **Actian VectorAI:** `docker compose up` starts the server (gRPC on `:6574`). The client
> (`pip install actian-vectorai-client`, in `scripts/install.sh`) and the adapter in
> `app/data/memory.py` are verified against `actian-vectorai-client 1.0.1`. Each staff
> member gets an isolated `user-<staff_id>-memories` collection. Set `ACTIAN_ENABLED=false`
> to run the scheduling demo without vector memory.
