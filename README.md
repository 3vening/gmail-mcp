# gmail-mcp

Multi-account Gmail control for Claude. Search, read, draft, send, archive, label, and manage email across any number of Gmail accounts, with hardened defaults.

## What makes this different

- Connect **multiple Gmail accounts** — talk to all of them from one Claude conversation
- Tokens stored in **OS keychain** (macOS Keychain / Windows Credential Manager / Linux Secret Service), never in a plain file
- **Draft-then-confirm sending** — Claude creates a draft, you approve, then it sends
- Attachment support for reading and sending
- Full thread context for smart replies
- Local audit log of every action Claude takes
- Identity verification on account add (rejects sign-in under the wrong email)
- Retry on transient Gmail API errors

## Security model

**You bring your own Google credentials.** This plugin never sees your tokens — each user creates their own Google Cloud project and OAuth client. Your emails and credentials stay on your machine only.

Attachments Claude can save are restricted to `~/Downloads/gmail-mcp/`.
Files Claude can attach to emails must be placed in `~/Downloads/gmail-mcp-uploads/`.

---

## Setup

### Step 1 — Create your own Google Cloud credentials (one-time)

> **Quick install:** Once you have your credentials (Step 1), just run:
> ```bash
> git clone https://github.com/3vening/gmail-mcp.git
> cd gmail-mcp
> bash install.sh
> ```
> The installer sets up Claude Desktop and Claude Code automatically. Skip to Step 4 when done.

> You need your own credentials so Google knows it's your app accessing your email. This is free and takes about 5 minutes.

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) and create a new project (or use an existing one)
2. **APIs & Services > Library** — search for and enable **Gmail API**
3. **APIs & Services > OAuth consent screen:**
   - User type: **External**
   - Fill in any app name (e.g. "My Gmail MCP") and your email
   - Add these scopes: `gmail.readonly`, `gmail.send`, `gmail.modify`, `gmail.labels`, `userinfo.email`, `openid`
   - Under **Test users**, add every Gmail address you want to connect
   - Save and continue
4. **APIs & Services > Credentials > Create Credentials > OAuth client ID:**
   - Application type: **Desktop app**
   - Copy the `Client ID` and `Client Secret` — you'll need these in Step 3

> **Note:** Leave the app in **Testing** mode. You do not need to publish it. Each person who uses this plugin creates their own project, so there is no shared app to review.

### Step 2 — Install prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

Clone this repo:

```bash
git clone https://github.com/3vening/gmail-mcp.git
cd gmail-mcp/server
uv sync
```

### Step 3 — Configure Claude

Copy the example config:

```bash
cp .mcp.json.example .mcp.json
```

Open `.mcp.json` and fill in your credentials and the absolute path to the server:

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

**For Claude Desktop**, add the same block to:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**For Claude Code CLI**, add it to `~/.claude/claude_code_config.json`.

### Step 4 — Add your Gmail accounts

Restart Claude, then in chat say:

> "Add my Gmail account you@gmail.com"

A browser window opens, you sign in, done. Repeat for each account — all accounts share the same OAuth client as long as they are listed as test users on your consent screen.

---

## Using it

Just talk to Claude naturally:

- "Search my emails for anything from my bank this week"
- "Read the latest email from john@example.com"
- "Draft a reply to that thread and send it once I approve"
- "Archive everything older than 30 days labeled newsletters"
- "Show me the audit log"

Claude will always create a **draft first** before sending — you confirm before anything goes out.

## Adding a second Gmail account

1. Go back to your Google Cloud Console > OAuth consent screen > Test users
2. Add the second email address
3. In chat: "Add my Gmail account second@gmail.com"

## Tools available to Claude

| Category | Tools |
|---|---|
| Accounts | `list_accounts`, `add_account`, `remove_account` |
| Reading | `search_emails`, `read_email`, `get_thread`, `save_attachment` |
| Drafting & sending | `draft_email`, `draft_reply`, `send_draft`, `discard_draft`, `list_drafts` |
| Organization | `get_labels`, `archive_email`, `trash_email`, `mark_as_read`, `mark_as_unread`, `apply_label`, `remove_label` |
| Safety | `view_audit_log` |

## Data locations

| Data | Location |
|---|---|
| Tokens | OS keychain (service name `gmail-mcp`) |
| Account index | `~/.gmail-mcp/accounts.json` (emails only, no secrets) |
| Audit log | `~/.gmail-mcp/audit.log` |
| Downloaded attachments | `~/Downloads/gmail-mcp/` |
| Outgoing attachments | `~/Downloads/gmail-mcp-uploads/` |

Override the data directory with the `GMAIL_MCP_DATA_DIR` environment variable.

## Revoking access

To fully disconnect an account:

1. In chat: "Remove account you@gmail.com"
2. Visit [myaccount.google.com/connections](https://myaccount.google.com/connections) and remove the OAuth grant on Google's side
