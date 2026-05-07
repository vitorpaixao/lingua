#!/bin/bash
set -e

if [ ! -f /project/package.json ]; then
  echo "==> First boot detected. Initializing project from template..."
  cp -a /template/. /project/
  echo "==> Template copied to /project"
fi

if [ ! -d /project/node_modules ]; then
  echo "==> Installing dependencies..."
  cd /project && npm install
fi

echo "==> Starting OpenCode server on :4096..."
cd /project
opencode serve --hostname 0.0.0.0 --port 4096 &
OPENCODE_PID=$!

sleep 2

trap "kill $OPENCODE_PID; exit 0" SIGTERM SIGINT

echo "==> Starting Vite dev server on :3000..."
exec npm run dev
