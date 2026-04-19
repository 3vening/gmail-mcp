"""OAuth2 auth for Gmail API. Credentials in env vars, tokens in keychain."""
import json
import os
from functools import lru_cache
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

import storage

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

OAUTH_CREDENTIALS_FILE = Path.home() / ".gmail-mcp-oauth.json"


class IdentityMismatch(Exception):
    """Raised when the signed-in email doesn't match the expected one."""


class OAuthConfigMissing(Exception):
    """Raised when no OAuth client credentials are found."""


@lru_cache(maxsize=1)
def get_oauth_config() -> dict:
    """Load OAuth client config from env vars first, then fallback file."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if client_id and client_secret:
        return {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

    if OAUTH_CREDENTIALS_FILE.exists():
        return json.loads(OAUTH_CREDENTIALS_FILE.read_text())

    raise OAuthConfigMissing(
        "No Google OAuth credentials found. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, "
        f"or create {OAUTH_CREDENTIALS_FILE}."
    )


def _fetch_authenticated_email(creds: Credentials) -> str:
    """Ask Google which account just signed in, using the userinfo endpoint."""
    from googleapiclient.discovery import build
    oauth2 = build("oauth2", "v2", credentials=creds)
    info = oauth2.userinfo().get().execute()
    return (info.get("email") or "").lower()


def authenticate_account(expected_email: str) -> str:
    """
    Run OAuth flow. Opens browser. Verifies the signed-in email matches expected_email.
    Returns the authenticated email on success. Raises IdentityMismatch if wrong account.
    """
    expected = expected_email.strip().lower()
    config = get_oauth_config()

    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    creds = flow.run_local_server(
        port=0,
        prompt="consent",  # load-bearing: ensures refresh_token is returned
        authorization_prompt_message=f"Sign in with: {expected_email}",
    )

    actual = _fetch_authenticated_email(creds)
    if actual != expected:
        raise IdentityMismatch(
            f"Expected sign-in as {expected_email}, but got {actual}. Tokens not saved."
        )

    storage.save_tokens(
        email=actual,
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        expiry=creds.expiry,
        scopes=list(creds.scopes) if creds.scopes else SCOPES,
    )
    return actual


def get_credentials(email: str) -> Credentials | None:
    """Return valid creds for an account, refreshing if expired. None if not authenticated."""
    tokens = storage.get_tokens(email)
    if not tokens:
        return None

    config = get_oauth_config()
    creds = Credentials(
        token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config["installed"]["client_id"],
        client_secret=config["installed"]["client_secret"],
        scopes=tokens["scopes"] or SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        storage.save_tokens(
            email=email,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            expiry=creds.expiry,
            scopes=list(creds.scopes) if creds.scopes else SCOPES,
        )

    return creds
