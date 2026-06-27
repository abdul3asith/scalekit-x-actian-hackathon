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
