#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "[worker] npm is required but was not found in PATH" >&2
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "[worker] installing npm dependencies"
  npm install
else
  echo "[worker] npm dependencies already installed"
fi

if [ -f wrangler.toml ] && [ ! -f .dev.vars ]; then
  cat <<'VARS' > .dev.vars
# Local-only defaults for wrangler dev
GITHUB_WEBHOOK_SECRET=
API_BASE_URL=http://localhost:8000
VARS
  echo "[worker] created .dev.vars; update it with your webhook secret before running wrangler dev"
fi

echo "\n[worker] next steps"
echo "  1. Authenticate with Cloudflare: npx wrangler login"
echo "  2. Set required secrets:"
echo "       npx wrangler secret put GITHUB_WEBHOOK_SECRET"
echo "       npx wrangler secret put CF_ACCOUNT_ID"
echo "       npx wrangler secret put CF_API_TOKEN"
echo "  3. Run locally: npx wrangler dev"
echo "  4. Deploy: npx wrangler deploy"
