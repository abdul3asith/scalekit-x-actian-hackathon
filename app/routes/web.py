"""Web onboarding: Scalekit login -> verified identity -> phone registration.
This is the bridge that lets a later voice call resolve to a real staff_id."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import scalekit
from app.auth.identity import normalize_phone, upsert_staff
from app.data.db import connection

router = APIRouter(tags=["web"])
logger = logging.getLogger("uvicorn.error")


@router.get("/auth/login")
async def login(request: Request):
    if not scalekit.is_ready():
        return HTMLResponse(
            "<h3>Scalekit not configured</h3><p>Set SCALEKIT_* env vars and install "
            "the SDK (scripts/install.sh).</p>",
            status_code=503,
        )
    state = uuid.uuid4().hex
    request.session["oauth_state"] = state
    return RedirectResponse(scalekit.authorization_url(state), status_code=302)


@router.get("/auth/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    # Diagnostic: which params arrived (keys only -- never log the code itself).
    logger.info("auth/callback params: %s", list(request.query_params.keys()))

    if error:
        return HTMLResponse(
            f"<h3>Scalekit returned an error</h3><p><b>{error}</b><br>{error_description or ''}</p>",
            status_code=400,
        )
    if not code:
        return HTMLResponse(
            "<h3>Missing authorization code</h3>"
            "<p>Don't open this page directly. Start at "
            "<a href='/auth/login'>/auth/login</a> and complete sign-in.</p>",
            status_code=400,
        )
    try:
        identity = scalekit.authenticate(code)
    except Exception as exc:  # noqa: BLE001 - surface exchange failures to the screen
        logger.exception("authenticate_with_code failed")
        return HTMLResponse(f"<h3>Auth exchange failed</h3><pre>{exc}</pre>", status_code=400)

    request.session["identity"] = identity
    return RedirectResponse("/register-phone", status_code=302)


@router.get("/register-phone", response_class=HTMLResponse)
async def register_phone_form(request: Request):
    identity = request.session.get("identity")
    if not identity:
        return RedirectResponse("/auth/login", status_code=302)
    name = identity.get("full_name", "there")
    return HTMLResponse(
        f"""
        <html><body style="font-family:sans-serif;max-width:480px;margin:40px auto">
        <h2>Hi {name}</h2>
        <p>Register the phone number you'll call from. Calls from this number will
        be scoped to your verified identity.</p>
        <form method="post" action="/register-phone">
          <input name="phone" placeholder="+14155550123" style="padding:8px;width:100%"
                 required />
          <button type="submit" style="margin-top:12px;padding:8px 16px">Register</button>
        </form>
        </body></html>
        """
    )


@router.post("/register-phone", response_class=HTMLResponse)
async def register_phone(request: Request, phone: str = Form(...)):
    identity = request.session.get("identity")
    if not identity:
        return RedirectResponse("/auth/login", status_code=302)

    async with connection() as conn:
        staff = await upsert_staff(
            conn,
            scalekit_user_id=identity["scalekit_user_id"],
            full_name=identity["full_name"],
            email=identity.get("email"),
            phone_e164=phone,
            org_id=identity.get("org_id"),
        )
    return HTMLResponse(
        f"""
        <html><body style="font-family:sans-serif;max-width:480px;margin:40px auto">
        <h2>Registered ✅</h2>
        <p><b>{staff['full_name']}</b> is now reachable at
        <b>{normalize_phone(phone)}</b>. Call the agent from that number.</p>
        </body></html>
        """
    )
