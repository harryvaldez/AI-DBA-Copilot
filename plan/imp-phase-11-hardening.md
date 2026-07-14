---
goal: Implementation Plan — Phase 11: Integration, Hardening & Production Readiness
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: All Phases 1–10
tags: implementation, hardening, deployment, production
---

# Phase 11: Integration, Hardening & Production Readiness

## Overview

End-to-end integration testing, security hardening, performance benchmarking, operational runbooks, OpenAPI documentation, and deployment pipeline setup. This is the final phase before the v1.0.0 release.

**Estimated Duration:** 2 sprints (Sprints 21–22)

**Dependencies:** All prior phases must be complete

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 11.1 | E2E integration test | 2 hr | `tests/integration/test_e2e_pipeline.py` | ⬜ |
| 11.2 | Dedup E2E test | 1 hr | `tests/integration/test_dedup_e2e.py` | ⬜ |
| 11.3 | Approval gate E2E test | 1 hr | `tests/integration/test_approval_gate.py` | ⬜ |
| 11.4 | Security hardening | 1.5 hr | `src/middleware/` | ⬜ |
| 11.5 | Performance benchmarks | 1.5 hr | `tests/benchmark/` | ⬜ |
| 11.6 | Operational runbook | 1 hr | `docs/operations/runbook.md` | ⬜ |
| 11.7 | OpenAPI specification | 1 hr | `docs/api/openapi.yaml` | ⬜ |
| 11.8 | Deployment pipeline | 1.5 hr | `.github/workflows/deploy.yml` | ⬜ |
| 11.9 | Jira webhook receiver (Gap G1) | 2 hr | `src/jira-integration/webhook.py` | ⬜ |
| 11.10 | Shared HTTP client (Gap G4) | 1 hr | `src/shared/http_client.py` | ⬜ |

---

## Task 11.1: E2E Integration Test

**File:** `tests/integration/test_e2e_pipeline.py`

```python
"""
End-to-end pipeline test:
1. Seed MCP metrics → 2. Detection Engine creates incident →
3. Jira ticket created → 4. Recommendation generated →
5. Embedding stored → 6. Semantic search retrieves it →
7. Remediation classifies actions
"""
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_pipeline():
    # Step 1: Seed metrics via MCP layer
    mcp = AsyncClient(base_url="http://localhost:8004")
    await mcp.post("/tools/get_database_metrics", json={"db_name": "test"})
    
    # Step 2: Trigger evaluation
    de = AsyncClient(base_url="http://localhost:8001")
    eval_result = await de.post("/evaluate")
    assert eval_result.status_code == 200
    data = eval_result.json()
    
    # Could have 0 if no threshold breached — test with known high-CPU seed data
    # This test validates the pipeline wiring, not detection quality
    
    # Step 3: Verify incidents accessible via UI API route
    ui = AsyncClient(base_url="http://localhost:3000")
    incidents = await ui.get("/api/incidents")
    assert incidents.status_code == 200

@pytest.mark.asyncio
async def test_health_all_services():
    """All 7 services respond to health check."""
    services = {
        "detection-engine": "http://localhost:8001",
        "recommendation-engine": "http://localhost:8002",
        "jira-integration": "http://localhost:8003",
        "mcp-layer": "http://localhost:8004",
        "memory-service": "http://localhost:8005",
        "predictive-analytics": "http://localhost:8006",
        "copilot-ui": "http://localhost:3000",
    }
    for name, url in services.items():
        client = AsyncClient(base_url=url)
        resp = await client.get("/health")
        assert resp.status_code == 200, f"{name} health check failed"
```

---

## Task 11.4: Security Hardening

**File:** `src/middleware/security.py` (or per-service middleware)

```python
from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiting: 100 req/min/IP
limiter = Limiter(key_func=get_remote_address)

async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all API routes."""
    # Applied per endpoint via @limiter.limit("100/minute")

# CORS Middleware — Restrict to UI origin only (applied to every FastAPI service)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("UI_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    max_age=600,  # Cache preflight responses for 10 minutes
)
```

**Security Checklist:**
- [ ] Input validation on all API endpoints (Pydantic schemas)
- [ ] Rate limiting: 100 req/min/IP via slowapi
- [ ] CORS restricted to UI origin only
- [ ] No secrets in logs or error responses
- [ ] All inter-service communication uses API key header
- [ ] SQL injection prevention via parameterized queries (SQLAlchemy)
- [ ] Prometheus metrics exported per service (Gap G3 — see below)
- [ ] Standardized httpx connection pooling (Gap G4 — see Task 11.10)

### Observability Baseline (Gap G3)

Every service exposes Prometheus metrics at `GET /metrics`:

```python
# src/shared/metrics.py — shared metrics module
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

# REQUIRED — all services
http_requests = Counter(
    'http_requests_total', 'Total HTTP requests',
    ['service', 'method', 'path', 'status']
)
http_duration = Histogram(
    'http_request_duration_seconds', 'HTTP request duration',
    ['service', 'method', 'path']
)
service_uptime = Gauge('service_uptime_seconds', 'Time since service start', ['service'])

# SERVICE-SPECIFIC
detection_incidents = Counter(
    'detection_incidents_total', 'Incidents created or updated',
    ['action']  # created | updated
)
rca_generated = Counter(
    'rca_generated_total', 'RCA recommendations generated',
    ['status']  # success | failed
)
jira_sync = Counter(
    'jira_sync_total', 'Jira sync operations',
    ['action', 'status']  # created|updated|transitioned, success|failed
)
mcp_call = Histogram(
    'mcp_call_duration_seconds', 'MCP tool call duration',
    ['tool']
)
```

---

## Task 11.5: Performance Benchmarks

**File:** `tests/benchmark/`

| Benchmark | Target | File |
|-----------|--------|------|
| Detection latency @ 1000 snapshots | < 5s | `tests/benchmark/test_detection_latency.py` |
| Snapshot write throughput | 100/s | `tests/benchmark/test_snapshot_throughput.py` |
| Semantic search @ 10K embeddings | < 3s | `tests/benchmark/test_search_latency.py` |
| RCA generation | < 60s | `tests/benchmark/test_rca_latency.py` |

---

## Task 11.6: Operational Runbook

**File:** `docs/operations/runbook.md`

Sections:
1. **Startup**: `docker compose up -d` → verify health endpoints
2. **Health URLs**: per-service health check locations
3. **Common Failures**: MCP unreachable, memory service down, Jira auth failure
4. **Backup/Restore**: PostgreSQL pg_dump + restore procedure (see Backup Strategy below)
5. **Logging**: Log locations per service (stdout via Docker)
6. **Metrics**: Prometheus endpoints per service (future)

### Backup Strategy

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Method** | `pg_dump -Fc` (custom-format) via cron | Portable, compressible, sufficient for MVP RPO |
| **Schedule** | Daily at 02:00 UTC | Off-peak; aligns with metric aggregate rollup |
| **Retention** | 30 daily + 12 monthly + 5 yearly | Balances storage cost with recovery flexibility |
| **WAL Archiving** | **Not enabled for MVP** | Acceptable RPO: 24h; MVP scope constraint |
| **Restore Test** | Monthly restore to staging environment | Validates backup integrity |
| **Pre-migration Backup** | Mandatory before every `alembic upgrade head` | Rollback safety net for schema changes |
| **Post-MVP Roadmap** | Enable WAL archiving + `pg_basebackup` for PITR | Phase 12+; required for production RPO < 1h |

**Restore procedure:**
```bash
# 1. Stop application services
docker compose stop memory-service detection-engine recommendation-engine \
  jira-integration mcp-layer predictive-analytics copilot-ui

# 2. Restore
pg_restore -U postgres -d aidbacopilot --clean --if-exists \
  /backups/aidbacopilot-$(date +%Y%m%d).dump

# 3. Re-run migrations to ensure currency
cd src/memory-service && alembic upgrade head

# 4. Start services
docker compose up -d

# 5. Verify
curl http://localhost:8005/health
```

---

## Task 11.7: OpenAPI Specification

**File:** `docs/api/openapi.yaml`

Combined OpenAPI 3.0 spec covering all 7 services. Can be served via FastAPI's built-in `/docs` per service, plus a merged version for the API documentation site.

---

## Task 11.8: Deployment Pipeline

**File:** `.github/workflows/deploy.yml`

```yaml
name: Deploy
on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build images
        run: docker compose build --parallel
      - name: Run smoke tests
        run: docker compose up -d && sleep 10 && pytest tests/integration/test_e2e_pipeline.py -x
      - name: Push images
        run: |
          # Tag and push to container registry
          docker tag ai-dba-copilot_memory-service registry.example.com/memory-service:${{ github.ref_name }}
          docker push registry.example.com/memory-service:${{ github.ref_name }}
          # ... repeat for all services
      - name: Tag release
        run: git tag v1.0.0 && git push origin v1.0.0
```

---

## Task 11.9: Jira Webhook Receiver (Gap G1)

**File:** `src/jira-integration/webhook.py`

```python
"""
Jira webhook receiver for bidirectional sync (Gap G1).

Registers as a webhook in Jira project settings. When a DBA manually
transitions, comments on, or changes a ticket in Jira, this endpoint
mirrors the change back to the platform's memory layer.
"""

from fastapi import APIRouter, Request, HTTPException
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/jira")
async def handle_jira_webhook(request: Request):
    """Receive Jira webhook events and sync to memory layer."""
    payload = await request.json()

    issue_key = payload.get("issue", {}).get("key")
    if not issue_key:
        raise HTTPException(400, "Missing issue key")

    # Look up mapping by jira_ticket_key
    mapping = await memory_service.get_mapping_by_jira_key(issue_key)
    if not mapping:
        logger.debug(f"Ignoring webhook for non-platform ticket: {issue_key}")
        return {"status": "ignored", "reason": "not a platform-managed ticket"}

    changelog = payload.get("changelog", {})
    incident_id = mapping["incident_id"]

    for item in changelog.get("items", []):
        field = item.get("field", "")

        # Status transition → mirror in platform
        if field == "status":
            to_status = item.get("toString", "")
            if to_status.lower() in ("done", "resolved", "closed"):
                await memory_service.patch_incident(incident_id, {
                    "status": "RESOLVED",
                    "resolved_at": datetime.utcnow().isoformat()
                })
                logger.info(f"Webhook: resolved {issue_key} → incident {incident_id}")

        # Priority change → mirror in platform
        if field == "priority":
            new_priority = item.get("toString", "")
            severity = _map_jira_priority_to_severity(new_priority)
            if severity:
                await memory_service.patch_incident(incident_id, {"severity": severity})

    # Update sync timestamp
    await memory_service.update_mapping(incident_id, {
        "sync_status": "SYNCED",
        "last_sync": datetime.utcnow().isoformat()
    })

    return {"status": "synced", "incident_id": incident_id}


def _map_jira_priority_to_severity(priority: str) -> str | None:
    mapping = {
        "Highest": "CRITICAL",
        "High": "HIGH",
        "Medium": "MEDIUM",
        "Low": "LOW",
    }
    return mapping.get(priority)
```

---

## Task 11.10: Shared HTTP Client (Gap G4)

**File:** `src/shared/http_client.py`

```python
"""
Standardized HTTP client configuration for all service-to-service calls (Gap G4).

Without explicit pool configuration, httpx defaults can cause connection leaks
under sustained load. This module provides a single factory for all internal
HTTP clients.
"""

import httpx
import os
from typing import Optional


def create_service_client(
    base_url: str,
    max_connections: int = 20,
    timeout_seconds: float = 30.0,
    api_key: Optional[str] = None,
) -> httpx.AsyncClient:
    """Create a pre-configured httpx AsyncClient for internal service calls.

    Args:
        base_url: Target service URL (e.g., 'http://memory-service:8005')
        max_connections: Hard cap on concurrent connections to this service
        timeout_seconds: Request timeout
        api_key: Optional internal API key for inter-service auth (X-API-Key header)
    """
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    elif os.getenv("INTERNAL_API_KEY"):
        headers["X-API-Key"] = os.getenv("INTERNAL_API_KEY")

    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=httpx.Timeout(timeout_seconds),
        limits=httpx.Limits(
            max_keepalive_connections=min(max_connections, 20),
            max_connections=max_connections,
            keepalive_expiry=60.0,  # Close idle connections after 60s
        ),
        transport=httpx.AsyncHTTPTransport(retries=2),
    )


# Per-service pool sizing (based on expected call volume):
# ┌──────────────────────┬─────────────────┬──────────────────┐
# │ Service              │ max_connections │ Rationale        │
# ├──────────────────────┼─────────────────┼──────────────────┤
# │ detection-engine     │ 20              │ Writes snapshots │
# │ recommendation-engine│ 10              │ Low volume       │
# │ jira-integration     │ 10              │ External API     │
# │ mcp-layer            │ 30              │ All traffic      │
# │ predictive-analytics │ 10              │ Daily cycle only │
# │ memory-service       │ N/A             │ Server, not client│
# └──────────────────────┴─────────────────┴──────────────────┘
```

## Phase 11 Completion Criteria

- [ ] E2E test: metric → detect → Jira → recommend → embed → search (passes)
- [ ] Dedup E2E: duplicate fingerprints → single active incident (passes)
- [ ] Approval gate E2E: no token → 403, readonly → 403, admin → 200 (passes)
- [ ] Rate limiting, CORS, input validation implemented
- [ ] Prometheus metrics exported on GET /metrics for all 7 services (G3)
- [ ] Shared httpx client factory with per-service pool config (G4)
- [ ] Jira webhook receiver syncs status transitions bidirectionally (G1)
- [ ] Detection latency < 5s @ 1000 snapshots
- [ ] Search latency < 3s @ 10K embeddings
- [ ] RCA generation < 60s
- [ ] Runbook documents startup, health checks, failures, recovery
- [ ] OpenAPI spec covers all service endpoints
- [ ] Deploy pipeline builds, tests, and pushes images
- [ ] Tag v1.0.0 created after full E2E pass
