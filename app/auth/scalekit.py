"""Scalekit Full Stack Auth wrapper. Used only for the one-time web onboarding
flow that establishes a verified identity, which we then bind to a phone number.

The Scalekit SDK is installed separately with --no-deps (see scripts/install.sh),
so its import is guarded to let the app boot without it during development."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import settings

try:  # pragma: no cover - depends on environment
    from scalekit import (  # type: ignore
        AuthorizationUrlOptions,
        CodeAuthenticationOptions,
        ScalekitClient,
    )

    _SDK_IMPORTED = True
except Exception:  # noqa: BLE001
    _SDK_IMPORTED = False


def is_ready() -> bool:
    return _SDK_IMPORTED and settings.scalekit_configured


@lru_cache
def get_client() -> Any:
    if not is_ready():
        raise RuntimeError(
            "Scalekit is not configured. Set SCALEKIT_* env vars and install "
            "scalekit-sdk-python (see scripts/install.sh)."
        )
    return ScalekitClient(
        settings.scalekit_environment_url,
        settings.scalekit_client_id,
        settings.scalekit_client_secret,
    )


def authorization_url(state: str) -> str:
    options = AuthorizationUrlOptions()
    options.state = state
    return get_client().get_authorization_url(
        settings.scalekit_redirect_uri,
        options,
    )


def _coerce(obj: Any, *names: str) -> Any:
    """Read an attribute or dict key, trying several names (SDK shape varies)."""
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def authenticate(code: str) -> dict[str, Any]:
    """Exchange an auth code for the verified user identity.

    The SDK returns ``{"user": {...}, "organization_id": <oid>, "id_token": ...}``
    where ``user`` maps claims to camelCase (sub->id, name, email, givenName, ...)
    and ``organization_id`` sits at the TOP LEVEL (from the ``oid`` claim).
    """
    result = get_client().authenticate_with_code(
        code, settings.scalekit_redirect_uri, CodeAuthenticationOptions()
    )
    user = _coerce(result, "user") or result
    return {
        "scalekit_user_id": _coerce(user, "id", "sub", "user_id"),
        "email": _coerce(user, "email"),
        "full_name": _coerce(user, "name", "full_name", "givenName", "given_name")
        or "Staff member",
        # organization_id is top-level on the result; fall back to user/oid just in case.
        "org_id": _coerce(result, "organization_id", "org_id", "oid")
        or _coerce(user, "organization_id", "oid"),
    }
