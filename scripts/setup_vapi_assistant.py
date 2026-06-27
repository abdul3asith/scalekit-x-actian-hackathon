"""Create (or print the config for) a VAPI assistant whose model is THIS backend's
custom-LLM endpoint. Run after the backend is reachable at PUBLIC_BASE_URL (ngrok in dev).

Usage:
    python scripts/setup_vapi_assistant.py

Requires VAPI_API_KEY in the environment/.env.
"""

from __future__ import annotations

import json
import sys

import httpx

from app.config import settings

ASSISTANT = {
    "name": "Voice Scheduling Assistant",
    "firstMessage": "Hi, this is your scheduling assistant. How can I help with your shifts?",
    "model": {
        # VAPI treats our OpenAI-compatible endpoint as the model.
        "provider": "custom-llm",
        "url": f"{settings.public_base_url.rstrip('/')}",
        "model": settings.nebius_chat_model,
        # VAPI appends /chat/completions to the url above and sends this bearer token.
        "headers": {"Authorization": f"Bearer {settings.backend_api_key}"},
    },
    "voice": {"provider": "vapi", "voiceId": "Elliot"},
    "transcriber": {"provider": "deepgram", "model": "nova-2"},
}


def main() -> int:
    if not settings.vapi_api_key:
        print("VAPI_API_KEY is not set. Here is the assistant config to create manually:")
        print(json.dumps(ASSISTANT, indent=2))
        return 1

    resp = httpx.post(
        "https://api.vapi.ai/assistant",
        headers={"Authorization": f"Bearer {settings.vapi_api_key}"},
        json=ASSISTANT,
        timeout=30,
    )
    if resp.status_code >= 300:
        print(f"Failed ({resp.status_code}): {resp.text}")
        return 1
    data = resp.json()
    print("Created VAPI assistant:")
    print(json.dumps(data, indent=2))
    print("\nNext: attach a phone number to this assistant in the VAPI dashboard,")
    print("or set VAPI_PHONE_NUMBER_ID and extend this script to link it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
