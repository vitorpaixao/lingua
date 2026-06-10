#!/bin/bash
set -e

PROJECT_DATA_DIR=${PROJECT_DATA_DIR:-/project-data}
AGENT_CONFIG_DIR=${AGENT_CONFIG_DIR:-/lingua-agent-config}
PROJECT_SYMLINK=${PROJECT_SYMLINK:-/project}

# ---------- git config ----------

git config --global user.name "${GIT_USER_NAME:-Lingua}"
git config --global user.email "${GIT_USER_EMAIL:-lingua@local}"
git config --global --add safe.directory '*'
git config --global init.defaultBranch main

if [ -n "$GITHUB_TOKEN" ]; then
  git config --global credential.helper \
    "!f() { echo username=oauth2; echo password=${GITHUB_TOKEN}; }; f"
fi

# ---------- agent-config repo ----------

if [ -n "$AGENT_CONFIG_REPO_URL" ]; then
  if [ ! -d "$AGENT_CONFIG_DIR/.git" ]; then
    echo "==> Cloning agent-config repo into $AGENT_CONFIG_DIR"
    rm -rf "$AGENT_CONFIG_DIR"
    git clone --depth=1 \
      ${AGENT_CONFIG_BRANCH:+--branch "$AGENT_CONFIG_BRANCH"} \
      "$AGENT_CONFIG_REPO_URL" "$AGENT_CONFIG_DIR"
  elif [ "${AGENT_CONFIG_PULL_ALWAYS:-false}" = "true" ]; then
    echo "==> Pulling latest agent-config"
    git -C "$AGENT_CONFIG_DIR" pull --ff-only || true
  fi
else
  echo "==> AGENT_CONFIG_REPO_URL not set; expecting bind-mount at $AGENT_CONFIG_DIR"
fi

mkdir -p "$PROJECT_DATA_DIR"

# ---------- wait for first workspace switch ----------

# The orchestrator creates per-project subdirs under $PROJECT_DATA_DIR and
# manages the $PROJECT_SYMLINK. We boot OpenCode + Vite once the symlink
# exists. Until then, idle.

echo "==> Waiting for $PROJECT_SYMLINK to be created by orchestrator..."
while [ ! -L "$PROJECT_SYMLINK" ] && [ ! -d "$PROJECT_SYMLINK" ]; do
  sleep 2
done
echo "==> $PROJECT_SYMLINK ready: $(readlink "$PROJECT_SYMLINK" 2>/dev/null || echo dir)"

cd "$PROJECT_SYMLINK"

# ---------- start OpenCode + Vite ----------

if [ ! -f package.json ]; then
  echo "==> ERROR: no package.json in $PROJECT_SYMLINK; bootstrap repo must include Vite scaffold" >&2
fi

# Install deps if missing
if [ -f package.json ] && [ ! -d node_modules ]; then
  echo "==> Installing dependencies"
  npm install
fi

echo "==> Starting OpenCode server on :4096"
opencode serve --hostname 0.0.0.0 --port 4096 &
OPENCODE_PID=$!

# Exec bridge: lets the deepagents engine (running in the orchestrator) run shell commands
# here, co-located with node/npm/node_modules. Harmless when AGENT_ENGINE=opencode.
echo "==> Starting exec bridge on :4097"
PROJECT_SYMLINK="$PROJECT_SYMLINK" node /exec_server.mjs &
EXEC_PID=$!

trap "kill $OPENCODE_PID $EXEC_PID 2>/dev/null; exit 0" SIGTERM SIGINT

if [ -f package.json ]; then
  echo "==> Copying Lingua Vite override into project"
  cp /lingua-vite.config.mjs "$PROJECT_SYMLINK/lingua-vite.config.mjs"
  # Keep the override out of git
  if ! grep -qE '^lingua-vite\.config\.mjs$' "$PROJECT_SYMLINK/.gitignore" 2>/dev/null; then
    echo "lingua-vite.config.mjs" >> "$PROJECT_SYMLINK/.gitignore"
  fi

  echo "==> Starting Vite dev server on :3000 with /preview/ base"
  exec npx vite \
    --host 0.0.0.0 \
    --port 3000 \
    --strictPort \
    --config "$PROJECT_SYMLINK/lingua-vite.config.mjs" \
    --clearScreen=false
else
  echo "==> No package.json; waiting (OpenCode will run, Vite will not)"
  wait $OPENCODE_PID
fi
