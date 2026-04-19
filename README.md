# gmail-mcp

Multi-account Gmail control for Claude. Search, read, draft, send, archive, label, and manage email across any number of Gmail accounts, with hardened defaults.

## What makes this different from the tutorial version

- Tokens stored in OS keychain (macOS Keychain / Windows Credential Manager / Linux Secret Service), not a plain file
- Draft-then-confirm sending: Claude creates a Gmail draft, you approve, then send
- Attachment read and send support
- Full thread context for smart replies
- Local audit log of every mutation
- Identity verification on account add (rejects sign-in under the wrong email)
- Retry on transient Gmail API errors

## Prerequisites

1. Python 3.10 or newer
2. [uv](https://docs.astral.sh/uv/) package manager
3. A Google Cloud project with the Gmail API enabled
4. OAuth 2.0 Desktop client credentials (`client_id` and `client_secret`)

### Google Cloud setup (one-time)

1. Go to https://console.cloud.google.com/ and create or pick a project
2. APIs & Services > Library > enable **Gmail API**
3. APIs & Services > OAuth consent screen:
   - User type: External
   - Fill in app name + your email
   - Add scopes: `gmail.readonly`, `gmail.send`, `gmail.modify`, `gmail.labels`, `userinfo.email`, `openid`
   - Add your Gmail addresses as test users (required while the app is in Testing status)
4. APIs & Services > Credentials > Create Credentials > OAuth client ID:
   - Application type: Desktop app
   - Download the JSON or copy `client_id` + `client_secret`

**Testing-mode warning.** Apps in Testing status cap at 100 test users and refresh tokens expire every 7 days. You will re-authenticate weekly until you either publish the app or mark it Internal (Google Workspace only).

## Install (Cowork)

1. In Cowork, install the `gmail-mcp.plugin` file.
2. When prompted, paste your `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
3. In chat, say "add my gmail account you@gmail.com" — a browser window opens, you sign in, done.
4. Repeat for each account.

## Install (Claude Desktop)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS (or the equivalent on Windows/Linux):

```json
{
  "mcpServers": {
    "gmail-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/gmail-mcp/server",
        "python",
        "server.py"
      ],
      "env": {
        "GOOGLE_CLIENT_ID": "your-client-id-here",
        "GOOGLE_CLIENT_SECRET": "your-client-secret-here"
      }
    }
  }
}
```

Restart Claude Desktop. Then add accounts in chat as above.

## Install (Claude Code CLI)

Add to `~/.claude/claude_code_config.json` with the same structure as above.

## CLI (optional, pre-auth without Claude)

```bash
cd /path/to/gmail-mcp/server
export GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET="..."
uv sync
uv run python cli.py add you@gmail.com
uv run python cli.py list
uv run python cli.py audit 50
```

## Tools exposed to Claude

Account management: `list_accounts`, `add_account`, `remove_account`
Reading: `search_emails`, `read_email`, `get_thread`, `save_attachment`
Drafting and sending: `draft_email`, `draft_reply`, `send_draft`, `discard_draft`, `list_drafts`
Organization: `get_labels`, `archive_email`, `trash_email`, `mark_as_read`, `mark_as_unread`, `apply_label`, `remove_label`
Safety: `view_audit_log`

## Data locations

- Tokens: OS keychain under service name `gmail-mcp`
- Account index: `~/.gmail-mcp/accounts.json` (emails only, no secrets)
- Audit log: `~/.gmail-mcp/audit.log` (JSON lines)
- Downloaded attachments: `~/Downloads/gmail-mcp/` by default

Override the data directory by setting `GMAIL_MCP_DATA_DIR`.

## Revoking access

To fully disconnect Claude from a Gmail account:

1. `remove_account(email)` in chat (removes local tokens)
2. Visit https://myaccount.google.com/connections and remove the OAuth grant on Google's side
