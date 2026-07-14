---
goal: Engineering-Grade TDD — AI DBA Copilot Blueprint (Full-Stack Implementation)
version: 1.1
date_created: 2026-06-18
last_updated: 2026-06-18
owner: AI DBA Platform Team
status: Planned
tags: feature, architecture, full-stack, tdd, enterprise
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines the end-to-end engineering implementation of the **AI DBA Copilot Platform** — an enterprise AI-powered database administration system that reduces operational toil, preserves institutional knowledge, and improves Root Cause Analysis (RCA) quality. The platform integrates an **existing MCP server** ([`mcp-sql-server`](../../mcp-sql-server)), a PostgreSQL memory layer with `pgvector` semantic search, an AI recommendation engine (OpenAI / Azure OpenAI via RAG), smart Jira deduplication, predictive analytics (isolation forests + linear regression), and a React/Next.js Copilot UI with RBAC-gated remediation approval workflows.

The plan is structured as 11 implementation phases spanning 22 sprints, aligned to the Technical Design Document (TDD) in [`docs/architecture/AI_DBA_Copilot_TDD.md`](../docs/architecture/AI_DBA_Copilot_TDD.md). Every task is atomic, independently executable, and contains exact file paths, function signatures, DDL statements, and validation criteria.

### Current Repository State

| Area | Status |
|------|--------|
| Architecture docs (`docs/architecture/`) | Present |
| `memory-layer/README.md` | Present (schema guidance only) |
| `src/` service implementations | **Not started** (directory README stubs only) |
| `tests/` | **Not started** (README only) |
| `docker-compose.yml`, root `package.json`, `pyproject.toml` | **Not present** |
| External MCP server (`mcp-sql-server`) | **Operational** (SQL Server 2019 dual-instance FastMCP service) |
| CI (`.github/workflows/ci.yml`) | Docs-structure validation only |

### Sprint Alignment (vs. TDD)

This plan's phase ordering prioritizes **data-flow dependencies** (memory → MCP client → ingestion → detection) while covering the same scope as the TDD sprint plan.

| TDD Sprints | TDD Focus | This Plan Phases |
|-------------|-----------|------------------|
| 1–2 | Foundation | Phase 1 |
| 3–4 | Memory Layer | Phase 2 |
| 5–6 | Detection Engine | Phase 4 (+ metric ingestion) |
| 7–8 | Jira Integration | Phase 5 |
| 9–10 | Recommendation Engine | Phase 6 |
| 11–12 | MCP Expansion | Phase 3 (integration client + tool mapping) |
| 13–14 | Copilot UI | Phase 9 |
| 15–16 | Semantic Search | Phase 7 |
| 17–18 | Predictive Analytics | Phase 8 |
| 19–22 | Automated Remediation | Phases 10–11 |

Phase 3 is placed before Phase 4 because the detection engine requires a working MCP client and metric-ingestion pipeline; "MCP Expansion" in the TDD maps to extending adapter coverage and controlled-write remediation paths in Phase 3 and Phase 10.

### Success Metrics (from TDD)

| Metric | Target |
|--------|--------|
| Duplicate Jira ticket reduction | ≥ 95% |
| Mean time to resolution (MTTR) reduction | ≥ 30% |
| RCA generation latency | < 5 minutes |
| Historical semantic retrieval latency | < 3 seconds |

## 1. Requirements & Constraints

### Functional Requirements
- **REQ-001**: Every section of this plan must be independently actionable by an AI agent or human.
- **REQ-002**: All PostgreSQL DDL must be copy-paste runnable against PostgreSQL 16+.
- **REQ-003**: MCP read-only operations (metrics, query plans, slow queries) must be fully autonomous.
- **REQ-004**: MCP write/configuration operations (CREATE INDEX, parameter changes, schema changes) must require explicit DBA approval via MFA/RBAC token.
- **REQ-005**: AI confidence scores below 0.60 must flag recommendations as "Draft — Needs Human Validation" and block script extraction.
- **REQ-006**: Incident/Jira deduplication must use deterministic SHA-256 fingerprinting: `SHA-256(db_target + error_code_or_metric_type + date_bucket)` with 4-hour window rounding on the hour component.
- **REQ-007**: Semantic search must use `pgvector` cosine distance (`<=>`) with OpenAI `text-embedding-ada-002` (1536-dimensional vectors). Cosine *similarity* for ranking: `1 - (embedding <=> query_vector)`.
- **REQ-008**: The Detection Engine must evaluate both rule-based thresholds AND ML-based isolation forest anomaly detection.
- **REQ-009**: The Recommendation Engine must use RAG (Retrieval-Augmented Generation) — retrieve top-3 similar past incidents before generating new RCA.
- **REQ-010**: All LLM outputs must be strictly structured JSON containing: `rca`, `actions` (array of `{step, command, type}`), `risk` (`LOW` \| `MEDIUM` \| `HIGH`), `confidence_score` (0.0–1.0). The `recommendations.risk_level` column stores the same three values (not `CRITICAL`; incident severity uses `CRITICAL`).
- **REQ-011**: The UI must provide three core views: Anomaly Dashboard, RCA & Remediation Review, Semantic Archive Search.
- **REQ-012**: The platform must **not** reimplement the MCP server. `src/mcp-layer/` is an **integration client and policy wrapper** that calls the existing [`mcp-sql-server`](../../mcp-sql-server) via `MCP_SERVER_URL`, mapping canonical tool names to runtime tool names (e.g., `db_primary_sql2019_top_queries_report`).

### Data Retention Constraints
- **RET-001**: Raw `metric_snapshots` retained for 90 days, then pruned by daily cron.
- **RET-002**: Aggregated metrics retained for 2 years in `metric_aggregates` rollup table.
- **RET-003**: Incidents and recommendations retained indefinitely.
- **RET-004**: Passwords/secrets must be explicitly scrubbed from `get_query_plan` and `get_slow_queries` payloads before storage.

### Security Constraints
- **SEC-001**: RBAC with at minimum two roles: `dba_readonly` and `dba_admin`.
- **SEC-002**: All remediation executions require MFA/SSO re-authentication token.
- **SEC-003**: Audit logging on all write operations to `incidents`, `recommendations`, `jira_mapping`, and `remediation_history` tables (via `audit_log` table or equivalent append-only log).
- **SEC-004**: Secrets management via environment variables or vault (never hardcoded).
- **SEC-005**: Input sanitization on all MCP tool parameters — reject `DROP`/`ALTER`/`TRUNCATE` in diagnostic paths; controlled writes follow `mcp-sql-server` allowlist/denylist policy.

### Architecture Constraints
- **ARC-001**: Python FastAPI + Celery for backend services (detection, recommendation, Jira, memory-service).
- **ARC-002**: React / Next.js / TailwindCSS for the Copilot UI.
- **ARC-003**: PostgreSQL 16+ with `pgvector` and `pg_stat_statements` extensions. TimescaleDB is optional (see ALT-001); not required for MVP.
- **ARC-004**: MCP integration via HTTP/SSE to existing FastMCP server — not a second MCP runtime in production.
- **ARC-005**: OIDC/SAML for UI authentication.
- **ARC-006**: All inter-service communication via async events (Celery tasks) or REST APIs.
- **ARC-007**: Containerized deployment (Docker) with CI/CD via GitHub Actions.

### Target Database Platforms
- **PLAT-001**: SQL Server 2019+ (**primary** — via existing `mcp-sql-server`)
- **PLAT-002**: PostgreSQL
- **PLAT-003**: Oracle
- **PLAT-004**: RDS MySQL
- **PLAT-005**: Databricks

Platform adapters beyond SQL Server are future MCP server extensions; Phase 1 implements the SQL Server mapping only.

## 2. Implementation Steps

### Implementation Phase 1: Foundation & Project Scaffolding (Sprints 1–2)

- **GOAL-001**: Establish the monorepo structure, build tooling, CI/CD pipelines, and base service skeletons for all backend services plus the UI. Every service must be independently buildable, testable, and containerized. The external `mcp-sql-server` runs separately (or as a linked compose service from its own repo).

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-001 | Create root `package.json` with workspace configuration for `src/copilot-ui/`. Define scripts: `install`, `test`, `build`, `lint`, `format`. Add devDependencies: `typescript`, `eslint`, `prettier`, `jest`, `ts-jest`. | ⬜ | |
| TASK-002 | Create root `pyproject.toml` (or per-service `requirements.txt` with shared `[project.optional-dependencies]` dev group). Define common dev dependencies: `pytest`, `pytest-asyncio`, `black`, `ruff`, `mypy`. Configure `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and `testpaths = ["tests"]`. | ⬜ | |
| TASK-003 | Extend `.github/workflows/ci.yml` with jobs: `lint` (eslint + ruff), `test` (jest + pytest), `build` (docker build per service), `integration` (docker-compose up + health checks). Trigger on PR to `main`. Preserve existing docs-structure validation step. | ⬜ | |
| TASK-004 | Create `docker-compose.yml` at repo root with services: `postgres` (postgres:16 + pgvector image, port 5432), `redis` (redis:7-alpine, port 6379), `detection-engine`, `recommendation-engine`, `jira-integration`, `mcp-layer` (integration client only), `memory-service`, `predictive-analytics`, `copilot-ui`. Document `MCP_SERVER_URL` pointing to external `mcp-sql-server` (default `http://host.docker.internal:8080` or compose `extends` from sibling repo). **Do not** embed a second SQL Server MCP runtime. | ⬜ | |
| TASK-005 | Create `src/detection-engine/` skeleton: `main.py` (FastAPI app), `requirements.txt`, `Dockerfile`, `celery_app.py`, `__init__.py`. Dockerfile: `FROM python:3.12-slim`, install deps, expose port 8001. | ⬜ | |
| TASK-006 | Create `src/recommendation-engine/` skeleton: same structure as detection-engine, expose port 8002. | ⬜ | |
| TASK-007 | Create `src/jira-integration/` skeleton: same structure, expose port 8003. | ⬜ | |
| TASK-008 | Create `src/mcp-layer/` skeleton: `client.py` (MCP HTTP client), `tool_mapping.yaml` (canonical → runtime tool names), `policy.py` (safety wrappers), `main.py` (optional FastAPI proxy for UI remediation calls), `requirements.txt`, `Dockerfile`. Expose port 8004. | ⬜ | |
| TASK-009 | Create `src/memory-service/` skeleton: `main.py` (FastAPI), `alembic.ini`, `models/` subdirectory, `Dockerfile`. Expose port 8005. SQL migrations live in `memory-layer/migrations/` (source of truth); Alembic revisions wrap or import those scripts. | ⬜ | |
| TASK-010 | Create `src/predictive-analytics/` skeleton: same structure, expose port 8006. | ⬜ | |
| TASK-011 | Initialize Next.js app in `src/copilot-ui/`: `npx create-next-app@latest . --typescript --tailwind --app`. Configure `tailwind.config.ts` with design tokens. Expose port 3000. | ⬜ | |
| TASK-012 | Configure shared `.env.example` at repo root: `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `JIRA_URL`, `JIRA_API_TOKEN`, `JIRA_USER_EMAIL`, `JIRA_PROJECT_KEY`, `MCP_SERVER_URL`, `MCP_INSTANCE` (e.g., `primary`), `EMBEDDING_MODEL` (`text-embedding-ada-002`), `LLM_MODEL` (`gpt-4o`). | ⬜ | |
| TASK-013 | Create `.gitignore` with entries: `node_modules/`, `__pycache__/`, `*.pyc`, `.env`, `.venv/`, `dist/`, `.next/`, `*.egg-info/`. **Do not** ignore `alembic/versions/` or `memory-layer/migrations/`. | ⬜ | |
| TASK-014 | Verify all service skeletons start via `docker-compose up --build` and respond to `GET /health` with `{"status": "ok"}`. Verify `mcp-layer` returns connectivity status to `MCP_SERVER_URL` (may be `degraded` if external server not running). | ⬜ | |

### Implementation Phase 2: Memory Layer — Core Schema & Migrations (Sprints 3–4)

- **GOAL-002**: Implement the full PostgreSQL schema with all **eight** core tables (seven domain tables + `metric_aggregates` rollup), vector extension, indexes, retention policies, and migration pipeline. Every DDL statement must be copy-paste runnable.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-015 | Initialize Alembic in `src/memory-service/`: `alembic init alembic`. Configure `alembic.ini` with `sqlalchemy.url` from `DATABASE_URL`. `env.py` imports all SQLAlchemy models. Initial revision executes scripts from `memory-layer/migrations/`. | ⬜ | |
| TASK-016 | Create `memory-layer/migrations/001_extensions.sql`. DDL: `CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_stat_statements;` | ⬜ | |
| TASK-017 | Create `memory-layer/migrations/002_metric_snapshots.sql`. Columns: `snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `db_target VARCHAR(255) NOT NULL`, `metric_type VARCHAR(50) NOT NULL CHECK (metric_type IN ('PERFORMANCE','CAPACITY','AVAILABILITY','MAINTENANCE','COST'))`, `payload JSONB NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`. Indexes: `idx_metrics_target_type_ts` on `(db_target, metric_type, created_at DESC)`; optional BRIN on `created_at` for pruning scans. | ⬜ | |
| TASK-018 | Create `memory-layer/migrations/003_incidents.sql`. Columns: `incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `fingerprint VARCHAR(64) NOT NULL`, `error_code_or_metric_type VARCHAR(100) NOT NULL`, `severity VARCHAR(20) NOT NULL CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','LOW'))`, `domain VARCHAR(50) NOT NULL`, `status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','RESOLVED','IGNORED'))`, `detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `resolved_at TIMESTAMPTZ`, `db_target VARCHAR(255) NOT NULL`, `detection_count INT NOT NULL DEFAULT 1`. Unique partial index: `idx_incidents_active_fingerprint` UNIQUE on `(fingerprint) WHERE status = 'ACTIVE'`. Index: `idx_incidents_status_severity` on `(status, severity)`. | ⬜ | |
| TASK-019 | Create `memory-layer/migrations/004_recommendations.sql`. Columns: `rec_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE`, `rca_text TEXT NOT NULL`, `action_steps JSONB NOT NULL`, `confidence_score NUMERIC(4,2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1)`, `risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH'))`, `requires_human_validation BOOLEAN NOT NULL DEFAULT FALSE`, `generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`. Index: `idx_recs_incident` on `incident_id`. | ⬜ | |
| TASK-020 | Create `memory-layer/migrations/005_jira_mapping.sql`. Columns: `mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE`, `jira_ticket_key VARCHAR(50) NOT NULL`, `sync_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (sync_status IN ('PENDING','SYNCED','FAILED'))`, `last_sync TIMESTAMPTZ`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`. Unique: `jira_ticket_key`. Index: `idx_jira_incident` on `incident_id`. | ⬜ | |
| TASK-021 | Create `memory-layer/migrations/006_remediation_history.sql`. Columns: `remediation_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `rec_id UUID NOT NULL REFERENCES recommendations(rec_id)`, `action_taken TEXT NOT NULL`, `executed_by VARCHAR(255) NOT NULL`, `executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `success BOOLEAN NOT NULL`, `result_details JSONB`. Index: `idx_rem_history_rec` on `rec_id`. | ⬜ | |
| TASK-022 | Create `memory-layer/migrations/007_configuration_history.sql`. Columns: `config_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `db_target VARCHAR(255) NOT NULL`, `parameter_name VARCHAR(255) NOT NULL`, `old_value TEXT`, `new_value TEXT`, `changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `changed_by VARCHAR(255)`. Index: `idx_config_target_ts` on `(db_target, changed_at DESC)`. | ⬜ | |
| TASK-023 | Create `memory-layer/migrations/008_embeddings.sql`. Columns: `vector_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('INCIDENT','RECOMMENDATION','JIRA_TICKET')), `source_id UUID NOT NULL`, `embedding vector(1536) NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`. Unique: `(source_type, source_id)`. Create IVFFlat index **after** initial backfill (see Phase 7): `CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);` | ⬜ | |
| TASK-024 | Create `memory-layer/migrations/009_metric_aggregates.sql`. Columns: `aggregate_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `db_target VARCHAR(255) NOT NULL`, `metric_type VARCHAR(50) NOT NULL`, `metric_key VARCHAR(100) NOT NULL`, `bucket_ts TIMESTAMPTZ NOT NULL`, `avg_value NUMERIC`, `min_value NUMERIC`, `max_value NUMERIC`, `sample_count INT NOT NULL`. Unique: `(db_target, metric_type, metric_key, bucket_ts)`. Index: `idx_agg_target_type_ts` on `(db_target, metric_type, bucket_ts DESC)`. | ⬜ | |
| TASK-025 | Create `memory-layer/migrations/010_audit_log.sql`. Columns: `audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `table_name VARCHAR(100) NOT NULL`, `record_id UUID NOT NULL`, `action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT','UPDATE','DELETE')), `actor VARCHAR(255)`, `payload JSONB`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`. Index: `idx_audit_table_record` on `(table_name, record_id)`. | ⬜ | |
| TASK-026 | Create SQLAlchemy ORM models in `src/memory-service/models/` mirroring each migration. Export from `models/__init__.py`. | ⬜ | |
| TASK-027 | Create `src/memory-service/retention.py`. Functions: `prune_metric_snapshots()` — delete rows older than 90 days; `aggregate_metrics()` — hourly rollup into `metric_aggregates`; `prune_aggregates()` — delete buckets older than 2 years. Schedule via Celery Beat or `pg_cron`. | ⬜ | |
| TASK-028 | Create `src/memory-service/main.py` FastAPI endpoints: `GET /health`; `POST /snapshots`; `GET /snapshots` (query by `db_target`, time range); `POST /incidents`; `GET /incidents` (filters: `status`, `severity`, `db_target`); `GET /incidents/{incident_id}`; `PATCH /incidents/{incident_id}` (resolve, increment `detection_count`); `POST /recommendations`; `GET /recommendations/{incident_id}`; `POST /embeddings`; `POST /embeddings/search`. All mutating endpoints write to `audit_log`. | ⬜ | |
| TASK-029 | Verify: `docker-compose up postgres memory-service`, then `curl -X POST localhost:8005/snapshots -H 'Content-Type: application/json' -d '{"db_target":"primary","metric_type":"PERFORMANCE","payload":{"cpu":85}}'` returns 201; row exists in `metric_snapshots`. | ⬜ | |

### Implementation Phase 3: MCP Integration Client & Tool Mapping (Sprints 5–6)

- **GOAL-003**: Implement the MCP **integration client** that wraps the existing `mcp-sql-server`, maps canonical TDD tool names to runtime tools, enforces read-only safety and approval-gated writes, and scrubs secrets. This is **not** a greenfield MCP server.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-030 | Create `src/mcp-layer/tool_mapping.yaml` documenting canonical → runtime mapping for SQL Server instance `primary` (and `secondary`). Example: `get_slow_queries` → `db_primary_sql2019_top_queries_report`; `get_blocking_sessions` → `db_primary_sql2019_block_report`; `get_query_plan` → `db_primary_sql2019_execute_query` (with plan capture). Reference [`mcp-sql-server/docs/mcp-tool-catalog.md`](../../mcp-sql-server/docs/mcp-tool-catalog.md). | ⬜ | |
| TASK-031 | Create `src/mcp-layer/client.py` with `MCPClient` class. Methods: `call_tool(tool_name: str, arguments: dict) -> dict` using MCP HTTP/SSE transport to `MCP_SERVER_URL`. Handle timeouts, retries, and standardized error envelopes. | ⬜ | |
| TASK-032 | Create `src/mcp-layer/tools/metrics.py` adapters: `get_database_metrics(db_name)` (compose from diagnostics/sessions DMVs), `get_host_metrics(db_name)`, `get_connection_metrics(db_name)` (map to `active_sessions_report`), `get_replication_metrics(db_name)` (AG/replica DMVs or stub with `not_supported` for non-HA). | ⬜ | |
| TASK-033 | Create `src/mcp-layer/tools/performance.py` adapters: `get_slow_queries(db_name, threshold_ms=1000)`, `get_query_plan(db_name, query_id)`, `get_blocking_sessions(db_name)`. Apply `scrub_secrets()` to all text fields. | ⬜ | |
| TASK-034 | Create `src/mcp-layer/tools/storage.py` adapters: `get_storage_growth(db_name)`, `get_tablespace_usage(db_name)` (SQL Server filegroup/space DMVs). | ⬜ | |
| TASK-035 | Create `src/mcp-layer/tools/operations.py` adapters: `get_database_configuration(db_name)`, `get_parameter_changes(db_name, since)` (from `configuration_history` or server trace), `search_incidents(query_text, limit)` (delegates to memory-service `/embeddings/search`), `get_recommendations(incident_id)` (delegates to memory-service). | ⬜ | |
| TASK-036 | Create `src/mcp-layer/safety.py` with `SafetyWrapper`: `validate_read_only(sql: str) -> bool` rejects `DROP`, `ALTER`, `TRUNCATE`, `INSERT`, `UPDATE`, `DELETE`, `CREATE` in diagnostic paths; `scrub_secrets(text: str) -> str` redacts `password=`, `IDENTIFIED BY`, `secret=` patterns. | ⬜ | |
| TASK-037 | Create `src/mcp-layer/auth.py` with `ApprovalGate`: `validate_approval_token(token: str, action: str) -> bool`; `require_approval(action_type: str)` raises `ApprovalRequiredError` for write operations without valid JWT scope. | ⬜ | |
| TASK-038 | Create `src/mcp-layer/tools/remediation.py`: `db_remediation_execution(database_id, action_script, authorization_token)` — validates token, routes to `exec_proc` or controlled-write path per `mcp-sql-server` policy, returns `{success, output, error}`. | ⬜ | |
| TASK-039 | Create `src/mcp-layer/main.py` FastAPI proxy (for UI/backend): `GET /health`, `GET /mcp/status`, `POST /tools/{canonical_name}` (internal use). Optional: expose `mcp_search_memory` as `POST /memory/search` wrapping memory-service semantic search. | ⬜ | |
| TASK-040 | Write unit tests in `tests/unit/mcp-layer/`: `test_safety_wrapper.py`, `test_approval_gate.py`, `test_tool_mapping.py` (verify YAML covers all TDD catalog tools), `test_client.py` (mock MCP responses). | ⬜ | |

### Implementation Phase 4: Metric Ingestion & Detection Engine (Sprints 7–8)

- **GOAL-004**: Implement metric collection from MCP into the memory layer, rule-based and ML-based detection, deterministic fingerprinting, and incident creation pipeline covering all TDD detection domains.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-041 | Create `src/detection-engine/collector.py` with `MetricCollector`. Celery Beat task `collect_metrics` every 60s: for each configured `db_target`, call MCP adapters (`get_database_metrics`, `get_host_metrics`, `get_connection_metrics`, `get_replication_metrics`, `get_storage_growth`), scrub secrets, `POST` to memory-service `/snapshots`. | ⬜ | |
| TASK-042 | Create `src/detection-engine/rules.py` with `RuleEvaluator` and `DetectionRule` dataclass: `{name, domain, metric_type, error_code, threshold, operator, duration_minutes, severity}`. Seed rules covering TDD domains: Performance (slow queries, blocking, deadlocks), Capacity (storage, connections), Availability (replication lag, backup age), Maintenance (vacuum/statistics staleness via `analyze_tab_health` signals), Cost (daily spend spike). | ⬜ | |
| TASK-043 | Create `src/detection-engine/ml_detector.py` with `IsolationForestDetector` (`sklearn`, `contamination=0.1`): `train_baseline(metric_data)`, `detect_anomalies(current_data) -> list[dict]`. | ⬜ | |
| TASK-044 | Create `src/detection-engine/fingerprint.py`: `generate_fingerprint(db_target: str, error_code_or_metric_type: str, timestamp: datetime) -> str` computes `SHA-256(f"{db_target}:{error_code_or_metric_type}:{date_bucket}")` where `date_bucket = timestamp.strftime('%Y-%m-%d-{hour}')` and `hour = (timestamp.hour // 4) * 4`. | ⬜ | |
| TASK-045 | Create `src/detection-engine/evaluator.py` with `DetectionOrchestrator.evaluate_cycle()`: fetch recent snapshots from memory-service; run rules + ML; merge; fingerprint; upsert incident (new `POST /incidents` or `PATCH` to increment `detection_count` on active match); emit `process_new_incident` Celery task only for new incidents. | ⬜ | |
| TASK-046 | Create `src/detection-engine/celery_app.py` and `tasks.py`: `process_new_incident(incident_id)` chains Jira sync + recommendation generation. | ⬜ | |
| TASK-047 | Create `src/detection-engine/main.py`: `GET /health`, `POST /evaluate`, `GET /rules`, `POST /rules`, `DELETE /rules/{name}`. | ⬜ | |
| TASK-048 | Create `src/detection-engine/scheduler.py`: Celery Beat `evaluate_cycle` every 60 seconds. | ⬜ | |
| TASK-049 | Write tests: `tests/unit/detection-engine/test_fingerprint.py`, `test_rules.py`, `test_ml_detector.py`; `tests/integration/test_detection_pipeline.py` (seed snapshots → evaluate → incident created). | ⬜ | |

### Implementation Phase 5: Jira Integration — Smart Ticket Management (Sprints 9–10)

- **GOAL-005**: Implement Jira integration with fingerprint-based deduplication (repository first, Jira second), create-vs-update logic, and lifecycle tracking via `jira_mapping`.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-050 | Create `src/jira-integration/client.py` with `JiraClient` (REST API v3): `create_issue`, `update_issue`, `search_issues`, `get_issue`, `add_comment`, `transition_issue`. Env: `JIRA_URL`, `JIRA_API_TOKEN`, `JIRA_USER_EMAIL`, `JIRA_PROJECT_KEY`. Exponential backoff on rate limits. | ⬜ | |
| TASK-051 | Create `src/jira-integration/dedup.py` with `DeduplicationService.process_incident(incident)`: 1) Query memory-service `GET /incidents?fingerprint={fp}&status=ACTIVE`. 2) If `jira_mapping` exists for that `incident_id` and `sync_status != 'FAILED'`, update ticket. 3) Else JQL search for fingerprint label. 4) Else create ticket + insert mapping. | ⬜ | |
| TASK-052 | Create `src/jira-integration/ticket_builder.py`: `format_incident_for_jira(incident) -> dict` with summary, markdown description, priority map (`CRITICAL→Highest`, etc.), labels `[fingerprint, domain, db_target]`. | ⬜ | |
| TASK-053 | Create `src/jira-integration/updater.py`: `update_existing_ticket(jira_key, incident)` — append comment with updated metrics and `detection_count`, escalate priority if needed. | ⬜ | |
| TASK-054 | Create `src/jira-integration/sync.py`: `sync_recommendation_to_jira`, `sync_resolution` (transition to Resolved). | ⬜ | |
| TASK-055 | Create `src/jira-integration/celery_app.py` and `tasks.py`: `process_jira_for_incident`, `sync_recommendation`. | ⬜ | |
| TASK-056 | Create `src/jira-integration/main.py`: `GET /health`, `POST /incidents/{id}/sync`, `GET /mappings`, `GET /mappings/{incident_id}`. | ⬜ | |
| TASK-057 | Write unit tests: `tests/unit/jira-integration/test_dedup.py`, `test_ticket_builder.py`, `test_client.py`. | ⬜ | |

### Implementation Phase 6: AI Recommendation Engine — RAG-Powered RCA (Sprints 11–12)

- **GOAL-006**: Implement RAG-powered RCA with pgvector retrieval, structured JSON enforcement, and confidence gating.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-058 | Create `src/recommendation-engine/llm_client.py` with `LLMClient` supporting OpenAI and Azure OpenAI (`response_format=json_object`). Env: `OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `LLM_MODEL`, `LLM_TEMPERATURE=0.1`. Retry up to 3 times on schema mismatch. | ⬜ | |
| TASK-059 | Create `src/recommendation-engine/embedding_client.py`: `embed(text)`, `embed_batch(texts)` via `text-embedding-ada-002`. | ⬜ | |
| TASK-060 | Create `src/recommendation-engine/context_assembler.py`: fetch incident, ±30min snapshots, `configuration_history`, and query plan via MCP when performance domain. | ⬜ | |
| TASK-061 | Create `src/recommendation-engine/rag_retriever.py`: `retrieve_similar(incident_text, top_k=3)` via memory-service `/embeddings/search`. | ⬜ | |
| TASK-062 | Create `src/recommendation-engine/prompt_templates.py` enforcing JSON schema per REQ-010. | ⬜ | |
| TASK-063 | Create `src/recommendation-engine/generator.py`: assemble → retrieve → prompt → LLM → validate JSON → set `requires_human_validation = confidence_score < 0.60` → `POST /recommendations` + `POST /embeddings` → return. | ⬜ | |
| TASK-064 | Create `src/recommendation-engine/celery_app.py` and `tasks.py`: `generate_recommendation(incident_id)`. | ⬜ | |
| TASK-065 | Create `src/recommendation-engine/main.py`: `GET /health`, `POST /generate/{incident_id}`, `GET /recommendations/{rec_id}`, `GET /recommendations/incident/{incident_id}`. | ⬜ | |
| TASK-066 | Write unit tests: `test_rag_retriever.py`, `test_context_assembler.py`, `test_generator.py` (confidence 0.59 vs 0.61 gating). | ⬜ | |

### Implementation Phase 7: Semantic Search & Knowledge Graph (Sprints 13–14)

- **GOAL-007**: Full semantic search pipeline — embedding generation, pgvector indexing, natural language query, historical pattern recognition.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-067 | Create `src/memory-service/embedding_service.py`: `embed_and_store(source_type, source_id, text)`, `search_similar(query_text, limit)` using `1 - (embedding <=> query_vector)`. | ⬜ | |
| TASK-068 | Enhance `POST /embeddings/search` to JOIN source tables and return incident/recommendation/jira details with similarity scores. | ⬜ | |
| TASK-069 | Create `src/memory-service/semantic_index.py`: `build_initial_index()` backfill; `rebuild_ivfflat_index()` only after ≥1000 rows (IVFFlat requires sufficient training data). | ⬜ | |
| TASK-070 | Celery Beat task `sync_missing_embeddings`: backfill incidents/recommendations/jira summaries without embedding rows. | ⬜ | |
| TASK-071 | Integration test `tests/integration/test_semantic_search.py`: seed 3 incidents, verify ranking. Target latency < 3s at 10k embeddings (benchmark in Phase 11). | ⬜ | |

### Implementation Phase 8: Predictive Analytics — Forecasting Models (Sprints 15–16)

- **GOAL-008**: Linear regression forecasting for storage/connection exhaustion; isolation forest for cost anomalies; predictive incident creation when exhaustion < 14 days.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-072 | Create `src/predictive-analytics/forecaster.py` — `StorageForecaster.forecast_storage(db_target)` from `metric_aggregates` (30-day window). | ⬜ | |
| TASK-073 | Create `src/predictive-analytics/connection_forecaster.py` — connection pool saturation forecast. | ⬜ | |
| TASK-074 | Create `src/predictive-analytics/replication_forecaster.py` — replication lag SLA breach prediction. | ⬜ | |
| TASK-075 | Create `src/predictive-analytics/cost_anomaly.py` — isolation forest on daily `COST` metrics. | ⬜ | |
| TASK-076 | Create `src/predictive-analytics/orchestrator.py` — `run_forecast_cycle()` creates predictive incidents via memory-service when thresholds breached. | ⬜ | |
| TASK-077 | Create `src/predictive-analytics/scheduler.py` — daily Celery Beat at 00:00 UTC. | ⬜ | |
| TASK-078 | Create `src/predictive-analytics/main.py` forecast endpoints. | ⬜ | |
| TASK-079 | Unit tests: `test_storage_forecaster.py`, `test_cost_anomaly.py`. | ⬜ | |

### Implementation Phase 9: Copilot UI — React/Next.js Frontend (Sprints 17–18)

- **GOAL-009**: Three core views with RBAC, MFA-gated remediation, and API routes proxying to backend services.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-080 | Create `src/copilot-ui/src/app/layout.tsx`, `Sidebar.tsx` (Dashboard, Incidents, Search, Settings). | ⬜ | |
| TASK-081 | Create `src/copilot-ui/src/app/dashboard/page.tsx` — Anomaly Dashboard (`IncidentStream`, `IncidentCard`, `SeverityFilter`, `StatsBar`; poll every 10s). | ⬜ | |
| TASK-082 | Create `src/copilot-ui/src/app/incidents/[id]/page.tsx` — RCA view (`RCAPanel`, `ActionStepsList`, `ApprovalButton`, confidence bar: green ≥0.80, yellow ≥0.60, red <0.60; block script copy when `requires_human_validation`). | ⬜ | |
| TASK-083 | Create `src/copilot-ui/src/app/search/page.tsx` — Semantic Archive Search calling memory-service. | ⬜ | |
| TASK-084 | Create `src/copilot-ui/src/lib/api.ts` and Next.js API routes in `src/app/api/`: `incidents` → **memory-service**; `recommendations` → memory-service; `search` → memory-service `/embeddings/search`; `forecast` → predictive-analytics; `approve` → mcp-layer remediation (admin only). | ⬜ | |
| TASK-085 | Implement `src/copilot-ui/src/lib/auth.ts` with NextAuth.js (OIDC/SAML), roles `dba_readonly` / `dba_admin`. | ⬜ | |
| TASK-086 | Component tests: `tests/unit/copilot-ui/IncidentCard.test.tsx`, `RCAPanel.test.tsx`, `ApprovalButton.test.tsx`. | ⬜ | |

### Implementation Phase 10: Automated Remediation — Safe Auto-Fixes (Sprints 19–20)

- **GOAL-010**: Auto-execute low-risk operations; approval-gated medium/high-risk; never auto-execute blocked operations.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-087 | Create `src/mcp-layer/tools/auto_remediation.py` — `AUTO` types: `ANALYZE`, `VACUUM`, `STATISTICS_REFRESH` (map to SQL Server equivalents: `UPDATE STATISTICS`, etc.). | ⬜ | |
| TASK-088 | Create `src/mcp-layer/tools/approved_remediation.py` — `CREATE INDEX`, parameter changes via controlled-write path. | ⬜ | |
| TASK-089 | Create `src/recommendation-engine/remediation_classifier.py` — tag actions `AUTO`, `APPROVAL_REQUIRED`, or `BLOCKED` (`DROP`, `TRUNCATE`). | ⬜ | |
| TASK-090 | Create `src/mcp-layer/remediation_orchestrator.py` — classify, execute AUTO, queue APPROVAL, log BLOCKED to `remediation_history`. | ⬜ | |
| TASK-091 | Add `POST /remediation/execute` to mcp-layer: `{rec_id, auth_token?}` → `{auto_results, pending_approval, blocked}`. | ⬜ | |
| TASK-092 | Integration test `tests/integration/test_remediation_pipeline.py`. | ⬜ | |

### Implementation Phase 11: Integration, Hardening & Production Readiness (Sprints 21–22)

- **GOAL-011**: E2E tests, security hardening, benchmarks, docs, deployment.

| Task     | Description           | Completed | Date       |
| -------- | --------------------- | --------- | ---------- |
| TASK-093 | `tests/integration/test_e2e_pipeline.py`: seed high CPU → detect → Jira → recommend → embed → search → remediate classify. | ⬜ | |
| TASK-094 | `tests/integration/test_dedup_e2e.py`: duplicate snapshots in 4-hour window → single active incident, `detection_count` incremented. | ⬜ | |
| TASK-095 | `tests/integration/test_approval_gate.py`: no token → 403; readonly → 403; admin → 200. | ⬜ | |
| TASK-096 | Security: input validation on all endpoints; rate limiting (100 req/min/IP via `slowapi` or NGINX); CORS restricted to UI origin. | ⬜ | |
| TASK-097 | Benchmarks in `tests/benchmark/`: detection < 5s @ 1000 snapshots; search < 3s @ 10k embeddings; RCA < 60s (target < 5 min per TDD KPI). | ⬜ | |
| TASK-098 | `docs/operations/runbook.md` — startup, health URLs, failures, backup/restore. | ⬜ | |
| TASK-099 | `docs/api/openapi.yaml` — all service endpoints including mcp-layer proxy. | ⬜ | |
| TASK-100 | `.github/workflows/deploy.yml` + `k8s/` manifests; smoke tests; tag `v1.0.0` after full E2E pass. | ⬜ | |

## 3. Alternatives

- **ALT-001**: **TimescaleDB for metric storage** — Optional per Detailed Component Designs. Rejected for MVP; use PostgreSQL + BRIN on `metric_snapshots.created_at` and `metric_aggregates` rollups. Revisit if >10M raw rows degrade prune/scan performance.
- **ALT-002**: **LangChain for RAG** — Rejected; custom lightweight RAG for prompt/JSON control.
- **ALT-003**: **Elasticsearch for semantic search** — Rejected; `pgvector` sufficient at expected scale (<1M embeddings).
- **ALT-004**: **Kafka for event streaming** — Rejected for MVP; Celery + Redis. Adopt if throughput exceeds Redis limits.
- **ALT-005**: **GraphQL API gateway** — Rejected; REST per service aligns with MCP contracts and agent consumption.
- **ALT-006**: **Rebuild MCP server in-repo** — Rejected; integrate existing [`mcp-sql-server`](../../mcp-sql-server) per TDD architecture.

## 4. Dependencies

- **DEP-001**: PostgreSQL 16+ with `pgvector` (0.5.0+) and `pg_stat_statements`.
- **DEP-002**: Redis 7+ for Celery broker and result backend.
- **DEP-003**: OpenAI or Azure OpenAI (`gpt-4o` recommended; `text-embedding-ada-002` for 1536-dim compatibility).
- **DEP-004**: Jira Cloud or Data Center with REST API v3 and API token.
- **DEP-005**: Python 3.12+: `fastapi`, `uvicorn`, `celery`, `sqlalchemy`, `asyncpg`, `pgvector`, `openai`, `scikit-learn`, `pandas`, `numpy`, `httpx`, `pyjwt`, `ruff`, `pytest`.
- **DEP-006**: Node.js 20+, Next.js 14+, React 18+, TailwindCSS 3+, `next-auth`.
- **DEP-007**: Docker 24+ and Docker Compose v2.
- **DEP-008**: GitHub Actions secrets: `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`, `JIRA_*`, `MCP_SERVER_URL`.
- **DEP-009**: External [`mcp-sql-server`](../../mcp-sql-server) deployed and reachable; SQL Server 2019 instances configured per its `config/instances.yaml`.

## 5. Files

- **FILE-001**: `src/detection-engine/` — Collector, rules, ML detector, fingerprint, orchestrator, Celery tasks.
- **FILE-002**: `src/recommendation-engine/` — LLM/embedding clients, RAG, generator, remediation classifier.
- **FILE-003**: `src/jira-integration/` — Jira client, dedup, ticket builder, sync.
- **FILE-004**: `src/mcp-layer/` — MCP client, tool mapping, safety/auth, remediation orchestrator (**not** a standalone MCP server).
- **FILE-005**: `src/memory-service/` — FastAPI, ORM models, embedding service, retention.
- **FILE-006**: `src/predictive-analytics/` — Forecasters and cost anomaly detector.
- **FILE-007**: `src/copilot-ui/` — Next.js frontend and API routes.
- **FILE-008**: `memory-layer/migrations/` — Versioned SQL migrations (source of truth for schema).
- **FILE-009**: `tests/unit/` — Unit tests mirroring `src/`.
- **FILE-010**: `tests/integration/` — Cross-service pipeline tests.
- **FILE-011**: `docker-compose.yml` — Local orchestration (links to external MCP).
- **FILE-012**: `.github/workflows/ci.yml` — CI pipeline.
- **FILE-013**: `.github/workflows/deploy.yml` — Deployment pipeline.
- **FILE-014**: `k8s/` — Kubernetes manifests.
- **FILE-015**: `docs/api/openapi.yaml` — OpenAPI specification.
- **FILE-016**: `docs/operations/runbook.md` — Operational runbook.
- **FILE-017**: `../../mcp-sql-server/` — External MCP server (separate repository).

## 6. Testing

- **TEST-001**: Fingerprint — deterministic output, 4-hour window, includes `error_code_or_metric_type`.
- **TEST-002**: Rule evaluator — threshold breaches, sustained duration, boundary values, all five domains.
- **TEST-003**: ML anomaly detector — isolation forest on synthetic data.
- **TEST-004**: Safety wrapper — destructive SQL rejected; secrets scrubbed.
- **TEST-005**: Approval gate — JWT scope validation.
- **TEST-006**: Jira dedup — repository-first, then Jira; no duplicate tickets.
- **TEST-007**: RAG retriever — top-3 cosine ranking.
- **TEST-008**: Generator — JSON schema validation; confidence gating at 0.60.
- **TEST-009**: Metric collector — MCP → memory-service ingestion with redaction.
- **TEST-010**: Tool mapping — all TDD catalog tools mapped for SQL Server.
- **TEST-011**: E2E pipeline — metric → incident → Jira → recommendation → embedding → search.
- **TEST-012**: Dedup E2E — single incident per fingerprint window.
- **TEST-013**: Approval gate E2E — role enforcement.
- **TEST-014**: Detection latency < 5s @ 1000 snapshots.
- **TEST-015**: Search latency < 3s @ 10k embeddings.
- **TEST-016**: RCA latency < 60s (KPI: < 5 min).

## 7. Risks & Assumptions

- **RISK-001**: **LLM API availability** — Mitigation: optional Ollama fallback for degraded RCA.
- **RISK-002**: **LLM output schema drift** — Mitigation: JSON schema validation + 3 retries.
- **RISK-003**: **pgvector IVFFlat at scale** — Mitigation: HNSW index option; benchmark at 100K/500K/1M; build index post-backfill.
- **RISK-004**: **Jira API rate limits** — Mitigation: exponential backoff; Celery retry queue.
- **RISK-005**: **Detection false positives** — Mitigation: sustained-duration rules; 4-hour fingerprint coalescing; `detection_count` on updates.
- **RISK-006**: **MCP tool name drift** — Mitigation: `tool_mapping.yaml` contract tests against `mcp-sql-server` catalog; pin server version in deploy manifests.
- **ASSUMPTION-001**: [`mcp-sql-server`](../../mcp-sql-server) is operational with stable tool contracts documented in its catalog.
- **ASSUMPTION-002**: SQL Server instances are reachable from the MCP server; additional platforms (Postgres, Oracle, etc.) require future MCP adapters.
- **ASSUMPTION-003**: DBAs interact primarily through the Copilot UI.
- **ASSUMPTION-004**: Single-region deployment for MVP.
- **ASSUMPTION-005**: Jira REST API v3 with API token auth.
- **ASSUMPTION-006**: CI runner has Docker and ≥8GB RAM.

## 8. Related Specifications / Further Reading

- [AI DBA Copilot Enterprise Blueprint](../docs/architecture/AI_DBA_Copilot_Enterprise_Blueprint.md)
- [AI DBA Copilot Technical Design Document (TDD)](../docs/architecture/AI_DBA_Copilot_TDD.md)
- [AI DBA Copilot Functional Design](../docs/architecture/AI_DBA_Copilot_Functional_Design.md)
- [Detailed Component Designs](../docs/architecture/Detailed_Component_Designs.md)
- [MCP SQL Server Tool Catalog](../../mcp-sql-server/docs/mcp-tool-catalog.md)
- [PostgreSQL pgvector Documentation](https://github.com/pgvector/pgvector)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Jira REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
