"""Token storage using OS keychain. Plain file holds only the account index (no secrets)."""
import json
import os
from datetime import datetime
from pathlib import Path

import keyring

KEYRING_SERVICE = "gmail-mcp"
DATA_DIR = Path(os.environ.get("GMAIL_MCP_DATA_DIR", str(Path.home() / ".gmail-mcp")))
ACCOUNTS_INDEX = DATA_DIR / "accounts.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ACCOUNTS_INDEX.exists():
        ACCOUNTS_INDEX.write_text("[]")


def _read_index() -> list[str]:
    _ensure_data_dir()
    try:
        return json.loads(ACCOUNTS_INDEX.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _write_index(emails: list[str]):
    _ensure_data_dir()
    ACCOUNTS_INDEX.write_text(json.dumps(sorted(set(emails)), indent=2))


def save_tokens(email: str, access_token: str, refresh_token: str,
                expiry: datetime | None = None, scopes: list[str] | None = None):
    """Save tokens to keychain. Index file gets the email, keychain gets the secrets."""
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expiry": expiry.isoformat() if expiry else None,
        "scopes": scopes or [],
    }
    keyring.set_password(KEYRING_SERVICE, email, json.dumps(payload))

    index = _read_index()
    if email not in index:
        index.append(email)
        _write_index(index)


def get_tokens(email: str) -> dict | None:
    raw = keyring.get_password(KEYRING_SERVICE, email)
    if not raw:
        return None
    data = json.loads(raw)
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expiry": datetime.fromisoformat(data["expiry"]) if data.get("expiry") else None,
        "scopes": data.get("scopes") or [],
    }


def list_accounts() -> list[str]:
    return _read_index()


def remove_account(email: str) -> bool:
    index = _read_index()
    if email not in index:
        return False
    index.remove(email)
    _write_index(index)
    try:
        keyring.delete_password(KEYRING_SERVICE, email)
    except keyring.errors.PasswordDeleteError:
        pass
    return True
