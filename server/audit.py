"""Append-only local audit log of every mutation Claude makes to email."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("GMAIL_MCP_DATA_DIR", str(Path.home() / ".gmail-mcp")))
AUDIT_LOG = DATA_DIR / "audit.log"


def log(action: str, account: str, **details):
    """Append a JSON line to the audit log. Never throws."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "account": account,
            **details,
        }
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Audit log is best-effort. Do not break the caller if it fails.
        pass


def tail(n: int = 50) -> list[dict]:
    """Return the last n audit entries as parsed dicts."""
    if not AUDIT_LOG.exists():
        return []
    lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-n:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
