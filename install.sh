#!/bin/bash
set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}gmail-mcp installer${RESET}"
echo "────────────────────────────────────────"
echo ""

# ── Resolve script directory ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/server"

# ── Install uv if missing ─────────────────────────────────────────────────────
if ! command -v uv &>/dev/null && ! [ -f "$HOME/.local/bin/uv" ]; then
  echo -e "${YELLOW}Installing uv package manager...${RESET}"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  source "$HOME/.local/bin/env" 2>/dev/null || true
fi

UV="$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")"

# ── Install Python dependencies ───────────────────────────────────────────────
echo -e "${YELLOW}Installing dependencies...${RESET}"
"$UV" sync --directory "$SERVER_DIR" --quiet
echo -e "${GREEN}✓ Dependencies installed${RESET}"
echo ""

# ── Collect credentials ───────────────────────────────────────────────────────
echo -e "${BOLD}Enter your Google OAuth credentials.${RESET}"
echo "  (Get them from console.cloud.google.com > APIs & Services > Credentials)"
echo ""
read -p "  Google Client ID:     " CLIENT_ID
read -p "  Google Client Secret: " CLIENT_SECRET
echo ""

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
  echo -e "${RED}Error: both credentials are required.${RESET}"
  exit 1
fi

# ── Build the server config block ────────────────────────────────────────────
MCP_BLOCK=$(cat <<EOF
{
  "mcpServers": {
    "gmail-mcp": {
      "command": "$UV",
      "args": [
        "run",
        "--directory",
        "$SERVER_DIR",
        "python",
        "server.py"
      ],
      "env": {
        "GOOGLE_CLIENT_ID": "$CLIENT_ID",
        "GOOGLE_CLIENT_SECRET": "$CLIENT_SECRET"
      }
    }
  }
}
EOF
)

# ── Helper: merge mcpServers into an existing JSON config ────────────────────
merge_config() {
  local config_path="$1"
  local dir
  dir="$(dirname "$config_path")"
  mkdir -p "$dir"

  if [ ! -f "$config_path" ]; then
    echo "$MCP_BLOCK" > "$config_path"
    return
  fi

  # Use Python to merge — available on every macOS
  python3 - "$config_path" "$CLIENT_ID" "$CLIENT_SECRET" "$UV" "$SERVER_DIR" <<'PYEOF'
import sys, json, pathlib

config_path = sys.argv[1]
client_id   = sys.argv[2]
client_secret = sys.argv[3]
uv_path     = sys.argv[4]
server_dir  = sys.argv[5]

config = json.loads(pathlib.Path(config_path).read_text())
config.setdefault("mcpServers", {})
config["mcpServers"]["gmail-mcp"] = {
    "command": uv_path,
    "args": ["run", "--directory", server_dir, "python", "server.py"],
    "env": {
        "GOOGLE_CLIENT_ID": client_id,
        "GOOGLE_CLIENT_SECRET": client_secret,
    },
}
pathlib.Path(config_path).write_text(json.dumps(config, indent=2) + "\n")
PYEOF
}

# ── Claude Desktop ────────────────────────────────────────────────────────────
DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [ -d "$HOME/Library/Application Support/Claude" ] || [ ! -d "$HOME/Library/Application Support/Claude" ]; then
  merge_config "$DESKTOP_CONFIG"
  echo -e "${GREEN}✓ Claude Desktop configured${RESET}"
fi

# ── Claude Code CLI ───────────────────────────────────────────────────────────
CODE_CONFIG="$HOME/.claude/claude_code_config.json"
if [ -d "$HOME/.claude" ]; then
  merge_config "$CODE_CONFIG"
  echo -e "${GREEN}✓ Claude Code configured${RESET}"
fi

# ── Project .mcp.json (for Claude Code in this folder) ───────────────────────
merge_config "$SCRIPT_DIR/.mcp.json"
echo -e "${GREEN}✓ Project .mcp.json configured${RESET}"

echo ""
echo -e "${BOLD}All done!${RESET}"
echo ""
echo "Next steps:"
echo "  1. Restart Claude Desktop and/or Claude Code"
echo "  2. In chat, say: \"Add my Gmail account you@gmail.com\""
echo "  3. Sign in when the browser opens — repeat for each account"
echo ""
echo "  To add multiple accounts, first add each email as a test user at:"
echo "  console.cloud.google.com > OAuth consent screen > Test users"
echo ""
