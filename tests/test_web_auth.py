"""Verify the web auth wiring without needing a live Scalekit login:
- /auth/login redirects into Scalekit's authorize endpoint
- /register-phone is session-gated and persists the phone->identity mapping
- scalekit.authenticate() maps the SDK response to our identity dict

The register-phone test forges a Starlette session cookie (same scheme the app
uses) so we can exercise the authenticated route without a real OAuth code.
"""

import base64
import json

import itsdangerous
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.auth import scalekit
from app.config import settings
from app.main import app


def _session_cookie(data: dict) -> str:
    signer = itsdangerous.TimestampSigner(settings.session_secret)
    raw = base64.b64encode(json.dumps(data).encode())
    return signer.sign(raw).decode()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_login_redirects_to_scalekit(client):
    if not scalekit.is_ready():
        pytest.skip("Scalekit not configured")
    resp = client.get("/auth/login", follow_redirects=False)
    assert resp.status_code == 302
    assert "/oauth/authorize" in resp.headers["location"]


def test_register_phone_requires_login(client):
    resp = client.get("/register-phone", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"].endswith("/auth/login")


def test_register_phone_persists_mapping(client):
    phone = "+13105550001"
    uid = "test_sk_web_001"
    identity = {
        "scalekit_user_id": uid,
        "full_name": "Web Test User",
        "email": "web@test.dev",
        "org_id": None,
    }
    try:
        client.cookies.set("session", _session_cookie({"identity": identity}))
        resp = client.post("/register-phone", data={"phone": phone})
        assert resp.status_code == 200
        assert "Registered" in resp.text

        with psycopg.connect(settings.database_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT full_name, scalekit_user_id FROM staff WHERE phone_e164 = %s",
                (phone,),
            )
            row = cur.fetchone()
        assert row is not None
        assert row[1] == uid
    finally:
        with psycopg.connect(settings.database_url) as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM staff WHERE scalekit_user_id = %s", (uid,))
            conn.commit()


def test_authenticate_maps_real_scalekit_shape(monkeypatch):
    """Mirrors the real authenticate_with_code() return: a ``user`` dict (claims
    mapped to camelCase) plus ``organization_id`` at the TOP LEVEL. Values are
    taken from a real Scalekit ID token."""
    real = {
        "user": {
            "id": "usr_131753913350095874",
            "name": "Haseeb Khan",
            "givenName": "Haseeb",
            "familyName": "Khan",
            "email": "haseebkhanyt@gmail.com",
            "emailVerified": True,
        },
        "id_token": "eyJ...",
        "access_token": "eyJ...",
        "organization_id": "org_131753913266209794",
    }

    class FakeClient:
        def authenticate_with_code(self, code, redirect_uri, options):
            return real

    monkeypatch.setattr(scalekit, "get_client", lambda: FakeClient())
    ident = scalekit.authenticate("dummy-code")
    assert ident == {
        "scalekit_user_id": "usr_131753913350095874",
        "email": "haseebkhanyt@gmail.com",
        "full_name": "Haseeb Khan",
        "org_id": "org_131753913266209794",
    }
