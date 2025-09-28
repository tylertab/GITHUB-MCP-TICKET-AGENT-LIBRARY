#!/usr/bin/env bash
set -euo pipefail

REPO_URL=${REPO_URL:-https://github.com/VickramC07/GITHUB-MCP-TICKET-AGENT-LIBRARY.git}
BRANCH=${BRANCH:-main}
CLONE_DIR=${1:-GITHUB-MCP-TICKET-AGENT-LIBRARY}
VENV_DIR=${VENV_DIR:-.venv}

if ! command -v python3 >/dev/null 2>&1; then
  echo "[bootstrap] python3 is required but was not found in PATH" >&2
  exit 1
fi

if [ ! -d "$CLONE_DIR" ]; then
  echo "[bootstrap] cloning $REPO_URL@$BRANCH into $CLONE_DIR"
  git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$CLONE_DIR"
else
  echo "[bootstrap] updating existing clone in $CLONE_DIR"
  git -C "$CLONE_DIR" pull --ff-only
fi

cd "$CLONE_DIR"

if [ ! -d "$VENV_DIR" ]; then
  echo "[bootstrap] creating virtualenv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip

if [ "${INSTALL_MODE:-editable}" = "editable" ]; then
  echo "[bootstrap] installing ticketwatcher in editable mode"
  pip install -e .
else
  echo "[bootstrap] installing ticketwatcher from git"
  pip install "git+${REPO_URL}@${BRANCH}#egg=ticketwatcher"
fi

if [ -f .env.example ] && [ ! -f .env ]; then
  echo "[bootstrap] creating .env from .env.example"
  cp .env.example .env
fi

echo "\n[bootstrap] setup complete!"
echo "[bootstrap] activate the environment with: source $CLONE_DIR/$VENV_DIR/bin/activate"
echo "[bootstrap] update .env with your OPENAI_API_KEY and other secrets before running the agent."
