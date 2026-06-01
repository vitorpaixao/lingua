# Testing

Tests currently run **on your host** (Node + Python). They are not part of the Docker stack. This doc covers how to run them locally and how to run them in Docker if you prefer not to install Node/Python on your host.

---

## Test Suites

| Suite          | Tool                              | Location          | Count                        |
| -------------- | --------------------------------- | ----------------- | ---------------------------- |
| Frontend       | Vitest + Testing Library          | `web/tests/`      | 6 tests                      |
| Backend        | pytest + respx + fakeredis         | `orchestrator/tests/` | 37 tests (4 skipped on Windows for symlinks) |

Coverage targets the **deep modules** that have non-trivial logic:

**Backend:**
- `SelectionFormatter` — pure unit tests
- `RedisStore` — integration via fakeredis
- `OpenCodeClient` — integration via respx (mocks SSE streams)
- `WorkspaceManager` — integration via temp dirs + real git
- `ProjectStore` — SQLite CRUD

**Frontend:**
- Session ID helper (`getSessionId`, `resetSessionId`)
- SSE client parser + reconnect with `Last-Event-ID` replay

UI components (`ChatPanel`, `WorkspacePage`, etc.) are NOT unit tested — they're tested manually + via end-to-end usage. Adding component tests is a future task.

---

## Local — On Your Host

### Frontend tests

Needs Node 22+.

```bash
cd web
npm install
npm test            # vitest run
npm run test:watch  # interactive watch mode
```

Expected output: `6 passed`.

### Backend tests

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd orchestrator
uv sync
uv run pytest
```

Expected output:

```
.....................................ssss..   [100%]
37 passed, 4 skipped in 1.4s
```

Run a single test file:

```bash
uv run pytest tests/test_redis_store.py -v
```

Run a single test:

```bash
uv run pytest tests/test_opencode_client.py::test_send_prompt_aggregates_text_and_files -v
```

### Skipped tests on Windows

Four `WorkspaceManager` tests that exercise symlink ops (`test_switch_*`, `test_is_dirty_*`) are skipped on Windows because `os.symlink` requires admin/Developer Mode. They DO run on Linux + macOS (and in the Docker test runner below).

---

## In Docker (no host Node / Python required)

If you don't want Node or Python on your host, run each suite inside its own container.

### Backend tests

The orchestrator image already has uv + the codebase. The `tests/` directory is excluded from the prod image (`.dockerignore`), so we need a one-off build that includes them.

Run ad-hoc with a bind-mount that pulls in `tests/`:

```bash
docker run --rm -it \
  -v "$PWD/orchestrator:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install --quiet uv && uv sync && uv run pytest -q"
```

(Use `${PWD}` on PowerShell or `%cd%` on cmd.)

All 37 tests + 4 previously-skipped symlink tests should pass under Linux — total **41 passed**.

For a faster repeat workflow, build a dedicated test image once:

```dockerfile
# orchestrator/Dockerfile.test
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync
COPY . .
CMD ["uv", "run", "pytest", "-q"]
```

```bash
docker build -f orchestrator/Dockerfile.test -t lingua-orchestrator-tests orchestrator/
docker run --rm lingua-orchestrator-tests
```

### Frontend tests

The `web` image is built with `npm install --omit=dev` in some configurations. Run tests from a stock Node image with a bind mount:

```bash
docker run --rm -it \
  -v "$PWD/web:/app" \
  -w /app \
  node:22-slim \
  sh -c "npm install --no-audit --no-fund --silent && npm test"
```

Expected output: `6 passed`.

### Combined CI-style script

Run both suites and fail loud if either does:

```bash
#!/bin/sh
set -e
docker run --rm -v "$PWD/orchestrator:/app" -w /app python:3.12-slim \
  sh -c "pip install --quiet uv && uv sync && uv run pytest -q"
docker run --rm -v "$PWD/web:/app" -w /app node:22-slim \
  sh -c "npm install --silent --no-audit --no-fund && npm test"
```

Drop in `scripts/test.sh` if you want a single command.

---

## Writing New Tests

### Backend (pytest + asyncio + respx)

`pyproject.toml` has `asyncio_mode = "auto"` so `async def test_*` functions are awaited automatically.

```python
# orchestrator/tests/test_my_feature.py
import pytest
from lingua.my_module import do_thing

async def test_do_thing_returns_expected():
    result = await do_thing("input")
    assert result == "expected"
```

For HTTP-mocking (OpenCode, etc.), use `respx`:

```python
import httpx, respx
from lingua.opencode_client import OpenCodeClient

@respx.mock
async def test_send_prompt(client: OpenCodeClient):
    respx.post("http://workspace:4096/session/x/prompt_async").mock(
        return_value=httpx.Response(204),
    )
    ...
```

For Redis, `fakeredis.aioredis.FakeRedis` is a drop-in replacement — see `tests/conftest.py` and `tests/test_redis_store.py`.

### Frontend (vitest + happy-dom)

Tests run in a simulated DOM (`happy-dom`). Place files under `web/tests/`.

```typescript
// web/tests/my_feature.test.ts
import { describe, it, expect } from 'vitest';
import { myFunction } from '@/lib/my_module';

describe('myFunction', () => {
  it('does what it should', () => {
    expect(myFunction('input')).toBe('expected');
  });
});
```

To test React components, use `@testing-library/react`:

```typescript
import { render, screen } from '@testing-library/react';
import { MyComponent } from '@/components/MyComponent';

it('renders the title', () => {
  render(<MyComponent title="Hi" />);
  expect(screen.getByText('Hi')).toBeInTheDocument();
});
```

---

## End-to-End

There's no automated e2e test suite yet. End-to-end verification is currently manual:

1. `docker compose down -v && docker compose up -d --build`
2. Open `http://localhost:5173`
3. Create a project with a real bootstrap repo
4. Open it → wait for npm install + Vite ready
5. Send a chat prompt → verify steps stream + final response renders
6. Click Publish → verify branch + commit + push

For a future e2e suite, Playwright is the natural fit and would slot into the `web/tests/` directory with a separate config.
