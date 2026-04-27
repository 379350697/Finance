"""OAuth token management for OpenAI Codex authentication.

This module supports two token sources:

1. **Codex CLI tokens** – The recommended path. Run ``codex login`` once,
   and the backend reads ``~/.codex/auth.json`` directly.  No custom OAuth
   server or redirect_uri needed.

2. **Manual token file** – A ``~/.finance_oauth.json`` fallback for
   environments where the Codex CLI is not installed.  Users can paste
   tokens obtained externally.

Token refresh is done automatically via the OpenAI ``/oauth/token`` endpoint
using the same ``client_id`` as the Codex CLI.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

# ---------------------------------------------------------------------------
# OpenAI OAuth endpoints (matches codex-rs/login/src/server.rs)
# ---------------------------------------------------------------------------
OPENAI_AUTH_ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{OPENAI_AUTH_ISSUER}/oauth/authorize"
TOKEN_URL = f"{OPENAI_AUTH_ISSUER}/oauth/token"
DEVICE_USERCODE_URL = f"{OPENAI_AUTH_ISSUER}/api/accounts/deviceauth/usercode"
DEVICE_TOKEN_URL = f"{OPENAI_AUTH_ISSUER}/api/accounts/deviceauth/token"

# The official client_id used by the Codex CLI for token refresh.
# (from codex-rs/login/src/auth/manager.rs)
DEFAULT_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"

# Scopes requested by the Codex CLI.
DEFAULT_SCOPE = (
    "openid profile email offline_access "
    "api.connectors.read api.connectors.invoke"
)

# Token file paths.
CODEX_AUTH_PATH = Path.home() / ".codex" / "auth.json"
FINANCE_TOKEN_PATH = Path.home() / ".finance_oauth.json"

# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def _generate_code_verifier(length: int = 64) -> str:
    """Generate a high-entropy code_verifier (43–128 chars, URL-safe)."""
    return secrets.token_urlsafe(length)[:128]


def _generate_code_challenge(verifier: str) -> str:
    """SHA-256 → base64url-encode to produce the code_challenge."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# Token loading (supports both Codex CLI and manual token files)
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_codex_tokens() -> dict[str, Any]:
    """Load tokens from the Codex CLI auth store (~/.codex/auth.json)."""
    data = _load_json(CODEX_AUTH_PATH)
    if not data:
        return {}
    # The Codex CLI stores tokens nested under a "tokens" key.
    tokens_obj = data.get("tokens", {})
    if not tokens_obj:
        return {}
    return {
        "access_token": tokens_obj.get("access_token", ""),
        "refresh_token": tokens_obj.get("refresh_token", ""),
        "obtained_at": 0,  # We don't know exact time, but the CLI manages refresh.
        "source": "codex_cli",
    }


def _load_tokens(path: Path = FINANCE_TOKEN_PATH) -> dict[str, Any]:
    """Load tokens, preferring Codex CLI auth over manual token file."""
    codex = _load_codex_tokens()
    if codex.get("access_token"):
        return codex
    return _load_json(path)


def _save_tokens(data: dict[str, Any], path: Path = FINANCE_TOKEN_PATH) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# OAuth session state (kept in-memory per process)
# ---------------------------------------------------------------------------

@dataclass
class OAuthSession:
    """Transient session that lives between /oauth/start and /oauth/callback."""
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    code_verifier: str = field(default_factory=_generate_code_verifier)
    redirect_uri: str = ""

    @property
    def code_challenge(self) -> str:
        return _generate_code_challenge(self.code_verifier)


_current_session: OAuthSession | None = None


def start_oauth_flow(
    *,
    redirect_uri: str,
    client_id: str = DEFAULT_CLIENT_ID,
    scope: str = DEFAULT_SCOPE,
) -> dict[str, str]:
    """Begin an OAuth PKCE flow: return the authorization URL + state."""
    global _current_session
    _current_session = OAuthSession(redirect_uri=redirect_uri)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": _current_session.code_challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "state": _current_session.state,
    }
    auth_url = f"{AUTHORIZE_URL}?{httpx.QueryParams(params)}"
    return {"authorize_url": auth_url, "state": _current_session.state}


def start_device_auth_flow(client_id: str = DEFAULT_CLIENT_ID) -> dict[str, Any]:
    """Start the Device Code authorization flow."""
    resp = httpx.post(
        DEVICE_USERCODE_URL,
        json={"client_id": client_id},
        timeout=10,
        proxy=settings.openai_proxy,
    )
    resp.raise_for_status()
    data = resp.json()
    
    # data contains: device_auth_id, user_code (or usercode), interval
    user_code = data.get("user_code") or data.get("usercode")
    
    return {
        "device_auth_id": data["device_auth_id"],
        "user_code": user_code,
        "interval": int(data.get("interval", 5)),
        "verification_url": f"{OPENAI_AUTH_ISSUER}/codex/device",
    }


def poll_device_auth_token(
    *,
    device_auth_id: str,
    user_code: str,
    client_id: str = DEFAULT_CLIENT_ID,
    token_path: Path = FINANCE_TOKEN_PATH,
) -> dict[str, Any] | None:
    """Poll for the device auth token.
    
    Returns the tokens if authenticated, or None if still waiting.
    Raises exceptions on errors or timeouts.
    """
    resp = httpx.post(
        DEVICE_TOKEN_URL,
        json={
            "device_auth_id": device_auth_id,
            "user_code": user_code,
        },
        timeout=10,
        proxy=settings.openai_proxy,
    )
    
    if resp.status_code in (403, 404):
        # Still pending / not yet authorized
        return None
        
    resp.raise_for_status()
    data = resp.json()
    
    # The device endpoint returns an authorization_code and PKCE verifier!
    # We must now exchange it for the actual tokens.
    redirect_uri = f"{OPENAI_AUTH_ISSUER}/deviceauth/callback"
    
    payload = (
        f"grant_type=authorization_code"
        f"&code={data['authorization_code']}"
        f"&redirect_uri={redirect_uri}"
        f"&client_id={client_id}"
        f"&code_verifier={data['code_verifier']}"
    )
    
    token_resp = httpx.post(
        TOKEN_URL,
        content=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
        proxy=settings.openai_proxy,
    )
    token_resp.raise_for_status()
    
    tokens = token_resp.json()
    tokens["obtained_at"] = int(time.time())
    tokens["source"] = "device_auth"
    _save_tokens(tokens, token_path)
    
    return tokens


def exchange_code_for_token(
    *,
    code: str,
    state: str,
    redirect_uri: str,
    client_id: str = DEFAULT_CLIENT_ID,
    token_path: Path = FINANCE_TOKEN_PATH,
) -> dict[str, Any]:
    """Exchange the authorization code for tokens."""
    global _current_session

    if _current_session is None:
        raise RuntimeError("No OAuth flow in progress – call start_oauth_flow first.")
    if state != _current_session.state:
        raise ValueError("OAuth state mismatch – possible CSRF.")

    payload = (
        f"grant_type=authorization_code"
        f"&code={code}"
        f"&redirect_uri={redirect_uri}"
        f"&client_id={client_id}"
        f"&code_verifier={_current_session.code_verifier}"
    )
    resp = httpx.post(
        TOKEN_URL,
        content=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
        proxy=settings.openai_proxy,
    )
    resp.raise_for_status()

    tokens = resp.json()
    tokens["obtained_at"] = int(time.time())
    _save_tokens(tokens, token_path)
    _current_session = None
    return tokens


def refresh_access_token(
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    token_path: Path = FINANCE_TOKEN_PATH,
) -> dict[str, Any]:
    """Use a stored refresh_token to obtain a fresh access_token."""
    tokens = _load_tokens(token_path)
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("No refresh_token available – re-authenticate via OAuth.")

    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    resp = httpx.post(
        TOKEN_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
        proxy=settings.openai_proxy,
    )
    resp.raise_for_status()

    new_tokens = resp.json()
    new_tokens["obtained_at"] = int(time.time())
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token
    _save_tokens(new_tokens, token_path)
    return new_tokens


def get_valid_access_token(
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    token_path: Path = FINANCE_TOKEN_PATH,
) -> str | None:
    """Return a valid access_token, refreshing transparently if expired.

    Returns ``None`` if there are no stored tokens at all.
    """
    tokens = _load_tokens(token_path)
    access_token = tokens.get("access_token")
    if not access_token:
        return None

    # If the token came from Codex CLI, trust it (the CLI manages its own refresh).
    if tokens.get("source") == "codex_cli":
        return access_token

    expires_in = tokens.get("expires_in", 3600)
    obtained_at = tokens.get("obtained_at", 0)
    if time.time() > obtained_at + expires_in - 60:
        try:
            tokens = refresh_access_token(client_id=client_id, token_path=token_path)
            return tokens.get("access_token")
        except (httpx.HTTPError, RuntimeError):
            return None

    return access_token


def get_oauth_status(*, token_path: Path = FINANCE_TOKEN_PATH) -> dict[str, Any]:
    """Return a summary of the current OAuth state (for the frontend)."""
    tokens = _load_tokens(token_path)
    if not tokens.get("access_token"):
        return {"authenticated": False}

    source = tokens.get("source", "manual")
    expires_in = tokens.get("expires_in", 3600)
    obtained_at = tokens.get("obtained_at", 0)
    expires_at = obtained_at + expires_in if obtained_at else 0
    return {
        "authenticated": True,
        "expires_at": expires_at,
        "has_refresh_token": bool(tokens.get("refresh_token")),
        "source": source,
    }


def clear_tokens(*, token_path: Path = FINANCE_TOKEN_PATH) -> None:
    """Remove persisted OAuth tokens (logout). Does NOT touch Codex CLI auth."""
    if token_path.exists():
        token_path.unlink()
