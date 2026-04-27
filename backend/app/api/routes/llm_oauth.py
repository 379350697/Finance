"""API routes for the OpenAI Codex OAuth PKCE login flow.

The flow uses a local callback server on port 1455, matching the official
Codex CLI behaviour.  In the web-app scenario we run a lightweight callback
endpoint on that port (or proxy from 8000) so that OpenAI's registered
redirect_uri is satisfied.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.services.llm.oauth import (
    clear_tokens,
    exchange_code_for_token,
    get_oauth_status,
    start_oauth_flow,
)
from app.services.llm.oauth_callback_page import OAUTH_CALLBACK_HTML

router = APIRouter(prefix="/llm/oauth", tags=["llm-oauth"])


class OAuthStartResponse(BaseModel):
    authorize_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class OAuthStatusResponse(BaseModel):
    authenticated: bool
    expires_at: int | None = None
    has_refresh_token: bool | None = None


# ── Start the OAuth flow ───────────────────────────────────────────────────

@router.post("/start", response_model=OAuthStartResponse)
def oauth_start(request: Request) -> OAuthStartResponse:
    """Return the OpenAI authorization URL that the frontend should redirect to."""
    # Use the same redirect_uri format as the Codex CLI:
    #   http://localhost:1455/auth/callback
    # Our FastAPI app listens on /api/llm/oauth/callback, so we mount
    # `/auth/callback` as a convenience alias (see below).
    origin = str(request.base_url).rstrip("/")
    redirect_uri = f"{origin}/api/llm/oauth/callback"

    result = start_oauth_flow(redirect_uri=redirect_uri)
    return OAuthStartResponse(**result)


# ── Callback from OpenAI ──────────────────────────────────────────────────

@router.get("/callback", response_class=HTMLResponse)
def oauth_callback(code: str, state: str) -> HTMLResponse:
    """Browser redirect target – returns HTML that relays the code to the opener."""
    return HTMLResponse(content=OAUTH_CALLBACK_HTML)


# POST variant – the frontend captures ?code=&state= and sends them here.
@router.post("/callback")
def oauth_callback_post(body: OAuthCallbackRequest, request: Request) -> dict:
    """POST variant – the frontend posts code+state after receiving postMessage."""
    origin = str(request.base_url).rstrip("/")
    redirect_uri = f"{origin}/api/llm/oauth/callback"
    try:
        tokens = exchange_code_for_token(
            code=body.code,
            state=body.state,
            redirect_uri=redirect_uri,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "authenticated",
        "expires_in": tokens.get("expires_in"),
        "token_type": tokens.get("token_type", "Bearer"),
    }


# ── Status / Logout ──────────────────────────────────────────────────────

@router.get("/status", response_model=OAuthStatusResponse)
def oauth_status() -> OAuthStatusResponse:
    """Check whether the backend holds a valid OAuth token."""
    info = get_oauth_status()
    return OAuthStatusResponse(**info)


@router.post("/logout")
def oauth_logout() -> dict:
    """Clear stored OAuth tokens."""
    clear_tokens()
    return {"status": "logged_out"}
