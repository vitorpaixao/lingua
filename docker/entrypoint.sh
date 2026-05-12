#!/bin/bash
set -e

auth_url() {
  if [ -n "$GITHUB_TOKEN" ]; then
    echo "$1" | sed -E "s#https://#https://oauth2:${GITHUB_TOKEN}@#"
  else
    echo "$1"
  fi
}

git config --global user.name  "${GIT_USER_NAME:-Lingua}"
git config --global user.email "${GIT_USER_EMAIL:-lingua@local}"
git config --global --add safe.directory /project
git config --global init.defaultBranch main

if [ -n "$GITHUB_TOKEN" ]; then
  git config --global credential.helper "!f() { echo username=oauth2; echo password=${GITHUB_TOKEN}; }; f"
fi

if [ -d /project/.git ] && [ -f /project/package.json ]; then
  echo "==> /project already a git repo with package.json, reusing"
elif [ -n "$BOOTSTRAP_REPO_URL" ]; then
  if [ -d /project/.git ] && [ ! -f /project/package.json ]; then
    echo "==> /project has stale .git but no package.json, wiping and re-cloning"
  fi
  echo "==> Cloning bootstrap repo $BOOTSTRAP_REPO_URL into /project"
  rm -rf /project/* /project/.[!.]* 2>/dev/null || true
  git clone "$(auth_url "$BOOTSTRAP_REPO_URL")" /project
  cd /project
  git remote set-url origin "$BOOTSTRAP_REPO_URL"
  git remote rename origin bootstrap
  git remote set-url --push bootstrap DISABLED_NO_PUSH
  if [ -n "$TARGET_REPO_URL" ]; then
    git remote add origin "$TARGET_REPO_URL"
    echo "==> Remotes: bootstrap (read-only) + origin (target)"
  else
    echo "==> Remotes: bootstrap (read-only). origin not set — push will fail until configured"
  fi
else
  echo "==> ERROR: BOOTSTRAP_REPO_URL not set and /project is empty." >&2
  echo "==> Set BOOTSTRAP_REPO_URL in .env to a git repo containing a Vite scaffold + .opencode/." >&2
  echo "==> See plan/ligua--bootstrap/readme.md for the expected layout." >&2
  exit 1
fi

cd /project

if [ ! -f /project/package.json ]; then
  echo "==> ERROR: /project/package.json missing after clone." >&2
  echo "==> Bootstrap repo ($BOOTSTRAP_REPO_URL) has no package.json. Add a Vite scaffold." >&2
  echo "==> Starting OpenCode anyway so you can fix it via chat. Vite will not run." >&2
  opencode serve --hostname 0.0.0.0 --port 4096 &
  OPENCODE_PID=$!
  trap "kill $OPENCODE_PID; exit 0" SIGTERM SIGINT
  wait $OPENCODE_PID
  exit $?
fi

npm config set fetch-retries 5
npm config set fetch-retry-mintimeout 20000
npm config set fetch-retry-maxtimeout 120000
npm config set fetch-timeout 600000

if [ ! -d node_modules ] || [ ! -f node_modules/.package-lock.json ]; then
  echo "==> Installing dependencies"
  attempt=1
  max_attempts=4
  delay=5
  until npm install; do
    if [ $attempt -ge $max_attempts ]; then
      echo "==> npm install failed after $attempt attempts, giving up" >&2
      exit 1
    fi
    echo "==> npm install failed (attempt $attempt/$max_attempts), retrying in ${delay}s" >&2
    rm -rf node_modules
    sleep $delay
    attempt=$((attempt + 1))
    delay=$((delay * 2))
  done
fi

echo "==> Starting OpenCode server on :4096"
opencode serve --hostname 0.0.0.0 --port 4096 &
OPENCODE_PID=$!

sleep 2

trap "kill $OPENCODE_PID; exit 0" SIGTERM SIGINT

cp /lingua-vite.config.mjs /project/lingua-vite.config.mjs

echo "==> Starting Vite dev server on :3000 with lingua shim config"
exec npx vite --config lingua-vite.config.mjs
