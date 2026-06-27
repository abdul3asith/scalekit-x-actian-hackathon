"""Create the two VAPI assistants (inbound scheduler + outbound coverage caller)
and a squad grouping them. Both use THIS backend as their custom LLM; the backend
switches behaviour by call metadata (inbound vs outbound).

Run after the backend is reachable at PUBLIC_BASE_URL (cloudflared/ngrok in dev):
    python scripts/setup_vapi_assistant.py

Requires VAPI_API_KEY. Prints the assistant + squad IDs; put the assistant IDs
into .env as VAPI_INBOUND_ASSISTANT_ID / VAPI_OUTBOUND_ASSISTANT_ID so the backend
can place outbound calls.
"""

from __future__ import annotations

import json
import sys

import httpx

from app.config import settings

BASE = settings.vapi_base_url
HEADERS = {"Authorization": f"Bearer {settings.vapi_api_key}"}
LLM_URL = settings.public_base_url.rstrip("/")


def _model() -> dict:
    # VAPI appends /chat/completions to url and sends these headers to our backend.
    return {
        "provider": "custom-llm",
        "url": LLM_URL,
        "model": settings.nebius_chat_model,
        "headers": {"Authorization": f"Bearer {settings.backend_api_key}"},
    }


INBOUND = {
    "name": "Scheduler — Inbound",
    "firstMessage": "Hi, this is your scheduling assistant. How can I help with your shifts?",
    "model": _model(),
    "voice": {"provider": "vapi", "voiceId": "Elliot"},
    "transcriber": {"provider": "deepgram", "model": "nova-2"},
}

OUTBOUND = {
    "name": "Scheduler — Outbound Coverage",
    # Variables filled per-call via assistantOverrides.variableValues (see app/services/vapi_out.py).
    "firstMessage": "Hi {{candidateName}}, this is the scheduling assistant. "
    "I'm calling to see if you can cover a shift for {{requesterName}}: {{shiftSummary}}. Are you available?",
    "model": _model(),
    "voice": {"provider": "vapi", "voiceId": "Elliot"},
    "transcriber": {"provider": "deepgram", "model": "nova-2"},
}


def create_assistant(cfg: dict) -> dict:
    resp = httpx.post(f"{BASE}/assistant", headers=HEADERS, json=cfg, timeout=30)
    resp.raise_for_status()
    return resp.json()


def create_squad(inbound_id: str, outbound_id: str) -> dict:
    body = {
        "name": "Scheduling Squad",
        "members": [
            {"assistantId": inbound_id},
            {"assistantId": outbound_id},
        ],
    }
    resp = httpx.post(f"{BASE}/squad", headers=HEADERS, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    if not settings.vapi_api_key:
        print("VAPI_API_KEY not set. Assistant configs that would be created:")
        print(json.dumps({"inbound": INBOUND, "outbound": OUTBOUND}, indent=2))
        return 1
    if LLM_URL.startswith("http://localhost"):
        print(f"WARNING: PUBLIC_BASE_URL is {LLM_URL!r} — VAPI can't reach localhost.")
        print("Start a tunnel and set PUBLIC_BASE_URL to the public URL first.")
        return 1

    inbound = create_assistant(INBOUND)
    outbound = create_assistant(OUTBOUND)
    squad = create_squad(inbound["id"], outbound["id"])

    print("Created:")
    print(f"  inbound assistant : {inbound['id']}")
    print(f"  outbound assistant: {outbound['id']}")
    print(f"  squad             : {squad['id']}")
    print("\nAdd to .env:")
    print(f"  VAPI_INBOUND_ASSISTANT_ID={inbound['id']}")
    print(f"  VAPI_OUTBOUND_ASSISTANT_ID={outbound['id']}")
    print("\nThen attach a phone number to the inbound assistant (or squad) in the")
    print("VAPI dashboard, and set VAPI_PHONE_NUMBER_ID for outbound coverage calls.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
