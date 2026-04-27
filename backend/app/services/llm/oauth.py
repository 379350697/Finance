"""OAuth 2.0 PKCE flow for OpenAI Codex authentication.

Implements the Authorization Code Flow with PKCE so users can authenticate
via their ChatGPT subscription instead of requiring a raw API key.
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

# ---------------------------------------------------------------------------
# OpenAI OAuth well-known endpoints (Codex / ChatGPT)
# ---------------------------------------------------------------------------
OPENAI_AUTH_DOMAIN = "https://auth.openai.com"
AUTHORIZE_URL = f"{OPENAI_AUTH_DOMAIN}/authorize"
TOKEN_URL = f"{OPENAI_AUTH_DOMAIN}/oauth/token"
AUDIENCE = "https://api.openai.com/v1"

# Public client – no client_secret needed with PKCE.
DEFAULT_CLIENT_ID = "DRivsnm2Mu42T3KOpqdtwB3NYkfbp1"

# Where to persist tokens locally.
DEFAULT_TOKEN_PATH = Path.home() / ".finance_oauth.json"

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
# Token persistence
# ---------------------------------------------------------------------------

def _load_tokens(path: Path = DEFAULT_TOKEN_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_tokens(data: dict[str, Any], path: Path = DEFAULT_TOKEN_PATH) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Restrict to owner-only on Unix.
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

    @property
    def code_challenge(self) -> str:
        return _generate_code_challenge(self.code_verifier)


# Singleton – only one login flow at a time.
_current_session: OAuthSession | None = None


def start_oauth_flow(
    *,
    redirect_uri: str,
    client_id: str = DEFAULT_CLIENT_ID,
    scope: str = "openai.chat openai.responses",
) -> dict[str, str]:
    """Begin an OAuth PKCE flow: return the authorization URL + state."""
    global _current_session
    _current_session = OAuthSession()

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "audience": AUDIENCE,
        "state": _current_session.state,
        "code_challenge": _current_session.code_challenge,
        "code_challenge_method": "S256",
    }
    qs = "&".join(f"{k}={httpx.QueryParams({k: v})}" for k, v in params.items())
    # Build a clean URL.
    auth_url = f"{AUTHORIZE_URL}?{httpx.QueryParams(params)}"
    return {"authorize_url": auth_url, "state": _current_session.state}


def exchange_code_for_token(
    *,
    code: str,
    state: str,
    redirect_uri: str,
    client_id: str = DEFAULT_CLIENT_ID,
    token_path: Path = DEFAULT_TOKEN_PATH,
) -> dict[str, Any]:
    """Exchange the authorization code for tokens.

    Validates *state*, posts to the token endpoint with the code_verifier,
    persists the resulting tokens, and returns them.
    """
    global _current_session

    if _current_session is None:
        raise RuntimeError("No OAuth flow in progress – call start_oauth_flow first.")
    if state != _current_session.state:
        raise ValueError("OAuth state mismatch – possible CSRF.")

    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": _current_session.code_verifier,
    }
    resp = httpx.post(TOKEN_URL, data=payload, timeout=30)
    resp.raise_for_status()

    tokens = resp.json()
    # Compute absolute expiry so we can check freshness later.
    tokens["obtained_at"] = int(time.time())
    _save_tokens(tokens, token_path)

    # Clear the transient session.
    _current_session = None
    return tokens


def refresh_access_token(
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    token_path: Path = DEFAULT_TOKEN_PATH,
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
    resp = httpx.post(TOKEN_URL, data=payload, timeout=30)
    resp.raise_for_status()

    new_tokens = resp.json()
    new_tokens["obtained_at"] = int(time.time())
    # Preserve the refresh_token if the server didn't rotate it.
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = refresh_token
    _save_tokens(new_tokens, token_path)
    return new_tokens


def get_valid_access_token(
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    token_path: Path = DEFAULT_TOKEN_PATH,
) -> str | None:
    """Return a valid access_token, refreshing transparently if expired.

    Returns ``None`` if there are no stored tokens at all (user never logged in).
    """
    tokens = _load_tokens(token_path)
    access_token = tokens.get("access_token")
    if not access_token:
        return None

    expires_in = tokens.get("expires_in", 3600)
    obtained_at = tokens.get("obtained_at", 0)
    # Refresh 60 s before actual expiry.
    if time.time() > obtained_at + expires_in - 60:
        try:
            tokens = refresh_access_token(client_id=client_id, token_path=token_path)
            return tokens.get("access_token")
        except (httpx.HTTPError, RuntimeError):
            return None

    return access_token


def get_oauth_status(*, token_path: Path = DEFAULT_TOKEN_PATH) -> dict[str, Any]:
    """Return a summary of the current OAuth state (for the frontend)."""
    tokens = _load_tokens(token_path)
    if not tokens.get("access_token"):
        return {"authenticated": False}

    expires_in = tokens.get("expires_in", 3600)
    obtained_at = tokens.get("obtained_at", 0)
    expires_at = obtained_at + expires_in
    return {
        "authenticated": True,
        "expires_at": expires_at,
        "has_refresh_token": bool(tokens.get("refresh_token")),
    }


def clear_tokens(*, token_path: Path = DEFAULT_TOKEN_PATH) -> None:
    """Remove persisted OAuth tokens (logout)."""
    if token_path.exists():
        token_path.unlink()
