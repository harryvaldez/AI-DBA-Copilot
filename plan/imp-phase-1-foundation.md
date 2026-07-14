---
goal: Implementation Plan — Phase 1: Foundation & Project Scaffolding
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Complete
depends_on: None (start here)
tags: implementation, foundation, scaffolding, docker, ci
---

# Phase 1: Foundation & Project Scaffolding

## Overview

Establish the monorepo structure, build tooling, CI/CD pipeline, Docker Compose orchestration, and service skeletons for all 8 backend services plus the Copilot UI. Every service must be independently buildable, testable, and containerized.

**Estimated Duration:** 2 sprints (Sprints 1–2)

**Dependencies:** None — this is the starting point.

## Task Inventory

| Task | Description | Est. Effort | File | Status |
|------|-------------|-------------|------|--------|
| 1.1 | Create root package.json | 30 min | `package.json` | ✅ |
| 1.2 | Create root pyproject.toml | 30 min | `pyproject.toml` | ✅ |
| 1.3 | Extend CI pipeline | 1 hr | `.github/workflows/ci.yml` | ✅ |
| 1.4 | Create Docker Compose | 1.5 hr | `docker-compose.yml` | ✅ |
| 1.5 | Detection Engine skeleton | 30 min | `src/detection-engine/` | ✅ |
| 1.6 | Recommendation Engine skeleton | 30 min | `src/recommendation-engine/` | ✅ |
| 1.7 | Jira Integration skeleton | 30 min | `src/jira-integration/` | ✅ |
| 1.8 | MCP Layer skeleton | 30 min | `src/mcp-layer/` | ✅ |
| 1.9 | Memory Service skeleton | 30 min | `src/memory-service/` | ✅ |
| 1.10 | Predictive Analytics skeleton | 30 min | `src/predictive-analytics/` | ✅ |
| 1.11 | Copilot UI initialization | 1 hr | `src/copilot-ui/` | ✅ |
| 1.12 | Shared env.example | 15 min | `.env.example` | ✅ |
| 1.13 | .gitignore | 15 min | `.gitignore` | ✅ |
| 1.14 | Verify all services start | 1 hr | — | ✅ |

---

## Task 1.1: Create root package.json

**File:** `package.json`

**Details:**
- Workspace config for `src/copilot-ui/`
- Scripts: `install` (npm install), `test` (jest), `build` (next build), `lint` (eslint), `format` (prettier)
- DevDependencies: typescript, eslint, prettier, jest, ts-jest, @types/jest

**Implementation:**

```json
{
  "name": "ai-dba-copilot",
  "version": "0.1.0",
  "private": true,
  "workspaces": ["src/copilot-ui"],
  "scripts": {
    "install": "npm install --workspaces",
    "test": "npm run test --workspace=src/copilot-ui",
    "build": "npm run build --workspace=src/copilot-ui",
    "lint": "eslint 'src/copilot-ui/src/**/*.{ts,tsx}'",
    "format": "prettier --write 'src/copilot-ui/src/**/*.{ts,tsx}'"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "eslint": "^8.57.0",
    "prettier": "^3.2.0",
    "jest": "^29.7.0",
    "ts-jest": "^29.1.0",
    "@types/jest": "^29.5.0"
  }
}
```

**Validation:** `npm install` succeeds. `npm test` runs (even if 0 tests). `npm run lint` completes.

---

## Task 1.2: Create root pyproject.toml

**File:** `pyproject.toml`

**Details:**
- Shared dev dependencies: pytest, pytest-asyncio, ruff, mypy
- `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths = ["tests"]`
- Each service has its own `requirements.txt` for runtime deps

**Implementation:**

```toml
[project]
name = "ai-dba-copilot"
version = "0.1.0"
requires-python = ">=3.12"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "ruff>=0.3.0",
    "mypy>=1.9.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
```

**Validation:** `pip install -e ".[dev]"` succeeds. `ruff check .` runs (no errors expected on empty codebase).

---

## Task 1.3: Extend CI Pipeline

**File:** `.github/workflows/ci.yml`

**Details:**
- Preserve existing docs-structure validation step.
- Add jobs: `lint` (eslint + ruff), `test` (jest + pytest), `build` (docker build per service), `integration` (docker-compose up + health checks).
- Trigger on PR to `main`.

**Implementation (key additions):**

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm install
      - run: npm run lint

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: pytest -q
      - run: npm install
      - run: npm test

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build --parallel

  integration:
    needs: [lint, test, build]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d --wait
      - run: |
          for svc in detection-engine recommendation-engine jira-integration mcp-layer memory-service predictive-analytics copilot-ui; do
            curl -f http://localhost:$PORT/health || exit 1
          done
      - run: docker compose down
```

**Validation:** Push to PR → `lint`, `test`, `build`, `integration` all pass.

---

## Task 1.4: Create Docker Compose

**File:** `docker-compose.yml`

**Details:**
- Services: postgres (pgvector:pg16), redis (redis:7-alpine), detection-engine, recommendation-engine, jira-integration, mcp-layer, memory-service, predictive-analytics, copilot-ui
- Shared network: `aidba-network`
- Environment variables via `.env` file

**Implementation:**

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: aidbacopilot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  memory-service:
    build: ./src/memory-service
    ports:
      - "8005:8005"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/aidbacopilot
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  mcp-layer:
    build: ./src/mcp-layer
    ports:
      - "8004:8004"
    environment:
      - MCP_SERVER_URL=http://host.docker.internal:8080
      - MEMORY_SERVICE_URL=http://memory-service:8005
    depends_on:
      - memory-service

  detection-engine:
    build: ./src/detection-engine
    ports:
      - "8001:8001"
    environment:
      - MEMORY_SERVICE_URL=http://memory-service:8005
      - MCP_LAYER_URL=http://mcp-layer:8004
    depends_on:
      - redis
      - mcp-layer

  recommendation-engine:
    build: ./src/recommendation-engine
    ports:
      - "8002:8002"
    environment:
      - MEMORY_SERVICE_URL=http://memory-service:8005
      - MCP_LAYER_URL=http://mcp-layer:8004
    depends_on:
      - redis
      - mcp-layer

  jira-integration:
    build: ./src/jira-integration
    ports:
      - "8003:8003"
    environment:
      - MEMORY_SERVICE_URL=http://memory-service:8005
    depends_on:
      - redis

  predictive-analytics:
    build: ./src/predictive-analytics
    ports:
      - "8006:8006"
    environment:
      - MEMORY_SERVICE_URL=http://memory-service:8005
    depends_on:
      - redis

  copilot-ui:
    build: ./src/copilot-ui
    ports:
      - "3000:3000"
    environment:
      - MEMORY_SERVICE_URL=http://memory-service:8005
      - PREDICTIVE_ANALYTICS_URL=http://predictive-analytics:8006
      - MCP_LAYER_URL=http://mcp-layer:8004
    depends_on:
      - memory-service

volumes:
  pgdata:
```

---

## Tasks 1.5–1.10: Service Skeletons

Each service skeleton has the same structure:

```
src/{service-name}/
├── __init__.py
├── main.py          # FastAPI app with GET /health
├── requirements.txt # Python dependencies
└── Dockerfile       # Container build
```

### Main Template (`main.py`)
```python
"""AI DBA Copilot - {Service Name} Service"""

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="AI DBA Copilot - {Service Name}", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "{service-name}", "version": "0.1.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port={PORT})
```

### Dockerfile Template
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE {PORT}
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{PORT}"]
```

### Requirements Template
```
fastapi>=0.110.0
uvicorn>=0.27.0
```

### Per-Service Ports and Additions

| Service | Port | Extra Dependencies |
|---------|------|-------------------|
| detection-engine | 8001 | `celery[redis]`, `scikit-learn`, `pandas`, `httpx` |
| recommendation-engine | 8002 | `celery[redis]`, `openai`, `httpx` |
| jira-integration | 8003 | `celery[redis]`, `httpx` |
| mcp-layer | 8004 | `httpx`, `pyjwt`, `pyyaml` |
| memory-service | 8005 | `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pgvector` |
| predictive-analytics | 8006 | `celery[redis]`, `scikit-learn`, `pandas`, `numpy`, `httpx` |

---

## Task 1.11: Initialize Next.js App

**Directory:** `src/copilot-ui/`

**Steps:**
```bash
cd src/copilot-ui
npx create-next-app@latest . --typescript --tailwind --app --src-dir --no-git
npm install next-auth@beta
```

**Required file updates:**

`tailwind.config.ts` — Add custom colors from TSD theme tokens.

`src/app/layout.tsx` — Root layout with metadata title "AI DBA Copilot".

**Dockerfile:** (multi-stage build)
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./
EXPOSE 3000
CMD ["npm", "start"]
```

---

## Task 1.12: Shared env.example

**File:** `.env.example`

```
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/aidbacopilot

# Redis / Celery
REDIS_URL=redis://redis:6379/0

# OpenAI / Azure OpenAI
OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
LLM_MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-ada-002

# Jira
JIRA_URL=
JIRA_API_TOKEN=
JIRA_USER_EMAIL=
JIRA_PROJECT_KEY=DBA

# MCP
MCP_SERVER_URL=http://host.docker.internal:8080
MCP_INSTANCE=primary

# JWT for approval tokens
JWT_PUBLIC_KEY=
JWT_ALGORITHM=RS256

# Service URLs (internal)
MEMORY_SERVICE_URL=http://memory-service:8005
MCP_LAYER_URL=http://mcp-layer:8004
PREDICTIVE_ANALYTICS_URL=http://predictive-analytics:8006

# Internal API auth
INTERNAL_API_KEY=
```

---

## Task 1.13: .gitignore

**File:** `.gitignore`

```
node_modules/
__pycache__/
*.pyc
.env
.venv/
dist/
.next/
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/
*.db
*.sqlite
```

**Do NOT ignore:**
- `memory-layer/migrations/`
- `alembic/versions/`
- `docs/`
- `config/` (except secrets)

---

## Task 1.14: Verify All Services Start

**Validation Script:**
```bash
# 1. Build all images
docker compose build --parallel

# 2. Start all services
docker compose up -d

# 3. Wait for health
for port in 3000 8001 8002 8003 8004 8005 8006; do
    echo "Waiting for service on port $port..."
    for i in {1..30}; do
        if curl -sf http://localhost:$port/health > /dev/null 2>&1; then
            echo "  ✓ Port $port healthy"
            break
        fi
        sleep 2
    done
done

# 4. Stop
docker compose down
```

**Expected output:**
```
✓ Port 3000 healthy  (copilot-ui)
✓ Port 8001 healthy  (detection-engine)
✓ Port 8002 healthy  (recommendation-engine)
✓ Port 8003 healthy  (jira-integration)
✓ Port 8004 healthy  (mcp-layer — may report degraded MCP)
✓ Port 8005 healthy  (memory-service)
✓ Port 8006 healthy  (predictive-analytics)
```

## Phase 1 Completion Criteria

- [x] `npm install` runs successfully from root
- [x] `pip install -e ".[dev]"` runs successfully from root
- [x] All 7 service containers build via `docker compose build --parallel`
- [x] All 7 services respond to `GET /health` with `{"status": "ok"}` (mcp-layer may return `"status": "degraded"` when MCP unreachable)
- [x] Copilot UI loads at `http://localhost:3000`
- [x] mcp-layer reports connectivity status to MCP_SERVER_URL (may show "degraded")
- [x] CI pipeline includes lint, test, build, and integration jobs (plus preserved docs validate)
- [x] `.env.example` documents all configuration variables
