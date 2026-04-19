#!/usr/bin/env python3
"""Terminal CLI for managing Gmail MCP accounts before connecting to Claude."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import auth
import storage


def main():
    if len(sys.argv) < 2:
        print("Gmail MCP CLI\n")
        print("Usage:")
        print("  python cli.py list              List authenticated accounts")
        print("  python cli.py add EMAIL         Authenticate an account")
        print("  python cli.py remove EMAIL      Remove an account (local only)")
        print("  python cli.py audit [N]         Show last N audit entries (default 25)")
        print("\nBefore running `add`, set env vars:")
        print("  export GOOGLE_CLIENT_ID='...'")
        print("  export GOOGLE_CLIENT_SECRET='...'")
        return

    cmd = sys.argv[1]

    if cmd == "list":
        accounts = storage.list_accounts()
        if not accounts:
            print("No accounts authenticated.")
        else:
            print("Authenticated accounts:")
            for a in accounts:
                print(f"  - {a}")

    elif cmd == "add":
        if len(sys.argv) < 3:
            print("Error: specify an email. Example: python cli.py add you@gmail.com")
            return
        email = sys.argv[2]
        print(f"Authenticating {email}...")
        print("A browser window will open. Sign in with the correct Google account.")
        try:
            saved = auth.authenticate_account(email)
            print(f"Authenticated {saved}")
        except auth.IdentityMismatch as e:
            print(f"Identity mismatch: {e}")
        except auth.OAuthConfigMissing as e:
            print(f"OAuth setup missing: {e}")
        except Exception as e:
            print(f"Authentication failed: {type(e).__name__}: {e}")

    elif cmd == "remove":
        if len(sys.argv) < 3:
            print("Error: specify an email.")
            return
        email = sys.argv[2]
        if storage.remove_account(email):
            print(f"Removed {email}")
        else:
            print(f"Account {email} not found.")

    elif cmd == "audit":
        import audit as audit_mod
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 25
        for entry in audit_mod.tail(n):
            print(entry)

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
