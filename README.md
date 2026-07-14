# AI DBA Copilot

An enterprise AI-powered platform that helps database teams detect problems, understand root causes, and act safely — faster and with less repeated manual work.

---

## What It Does

AI DBA Copilot combines telemetry-based detection, AI-generated root cause analysis, smart Jira deduplication, semantic memory search, and a human-approval safety layer into a single integrated workflow.

Instead of switching between dashboards, runbooks, and ticketing tools, DBAs get:

- Instant incident detection with severity classification
- AI-generated RCA with confidence scoring and risk level
- Historical context retrieved from past incidents via semantic search
- Automatic Jira ticket creation or update (no duplicates)
- Safe remediation with mandatory approval gates for write/config actions
- Full audit trail on every action taken

---

## Architecture Overview

```
Database Platforms (PostgreSQL · Oracle · RDS MySQL · Databricks)
        │
        ▼
   MCP Integration Layer  ──────────────────────────────────────────┐
        │                                                            │
        ▼                                                            │
  Memory Layer (PostgreSQL 16 + pgvector)                           │
        │                                                            │
        ▼                                                            ▼
  Detection Engine                                     Semantic Search / Embeddings
        │
        ▼
  Recommendation Engine (RAG + LLM)
        │
        ▼
  Jira Integration
        │
        ▼
  DBA Copilot UI (Next.js)
```

| Layer | Technology |
|---|---|
| Database Platforms | PostgreSQL, Oracle, RDS MySQL, Databricks |
| MCP Integration | Existing mcp-sql-server service + safety wrappers |
| Memory / Repository | PostgreSQL 16, pgvector, Alembic migrations |
| Detection Engine | Python FastAPI + Celery, rule-based + ML anomaly detection |
| Recommendation Engine | OpenAI / Azure OpenAI, RAG pipeline |
| Jira Integration | Jira REST API, deterministic fingerprint deduplication |
| Copilot UI | Next.js, role-aware views, approval action flows |
| Observability | Structured logging, audit trail, dashboards |

---

## Key Features

### Incident Detection
- Rule-based and ML-based anomaly detection
- Coverage: performance, capacity, availability, maintenance, and cost domains
- Severity levels: Critical, High, Medium, Low
- Deterministic fingerprinting to deduplicate active incidents

### AI Recommendation Engine
- Retrieves top similar past incidents before generating recommendations
- Produces structured JSON output: RCA, action steps, risk level, confidence score
- Confidence gate at 0.60 — recommendations below threshold flagged for human review

### Smart Jira Integration
- Fingerprint-based dedup prevents duplicate ticket creation
- Creates or updates existing tickets based on memory mapping + Jira search fallback
- Bidirectional status sync and recommendation linking

### Semantic Memory Search
- pgvector-backed embedding storage
- Cosine similarity retrieval over incidents, RCAs, recommendations, and Jira tickets
- Search results in under 3 seconds at 10,000+ embedding scale

### Safe Remediation
- Read-only diagnostics run autonomously
- Write or configuration changes require explicit DBA approval with MFA/token
- Every action is audit logged regardless of outcome

---

## Project Structure

```
AI-DBA-Copilot/
├── docs/
│   ├── architecture/          # Blueprint, functional design, TDD, component designs
│   └── api/                   # MCP tool contracts and integration specs
├── plan/
│   ├── PRD-*.md               # Product requirements per component
│   └── imp-phase-*.md         # Implementation phase plans (11 phases)
├── src/
│   ├── detection-engine/      # Anomaly detection service
│   ├── recommendation-engine/ # RAG + LLM recommendation service
│   ├── memory-service/        # PostgreSQL memory layer service
│   ├── mcp-layer/             # MCP integration client
│   ├── jira-integration/      # Jira dedup and lifecycle service
│   └── predictive-analytics/  # Forecasting and capacity planning
├── memory-layer/
│   └── migrations/            # Alembic database migrations
└── tests/
    ├── unit/
    └── integration/
```

---

## MVP Scope

The MVP delivers the following in 10–14 weeks:

1. Memory schema with retention policies
2. MCP integration client with safety wrappers
3. Detection engine (rules + initial anomaly model)
4. Jira deduplication and mapping
5. Recommendation engine with confidence gating
6. Three core UI views: Anomaly Dashboard · Incident RCA Review · Semantic Archive Search
7. Audit trail for all controlled write actions

---

## Implementation Phases

| Phase | Focus |
|---|---|
| 1 | Foundation — repo, CI/CD, base services |
| 2 | Memory Layer — schema, migrations, retention |
| 3 | MCP Integration Layer |
| 4 | Detection Engine |
| 5 | Jira Integration |
| 6 | Recommendation Engine |
| 7 | Semantic Search |
| 8 | Predictive Analytics |
| 9 | Copilot UI |
| 10 | Automated Remediation |
| 11 | Hardening, observability, production readiness |

---

## Key Results (MVP Targets)

| Metric | Target |
|---|---|
| Duplicate Jira ticket reduction | ≥ 95% within 90 days |
| Mean time to resolution reduction | ≥ 30% within 90 days |
| Time to first RCA recommendation | < 5 minutes for ≥ 90% of incidents |
| Semantic search response time | < 3 seconds for ≥ 95% of queries |
| Approval coverage for write actions | 100% with full audit log |

---

## Technology Stack

| Component | Stack |
|---|---|
| Backend services | Python, FastAPI, Celery |
| Memory / database | PostgreSQL 16, pgvector, Alembic |
| AI / LLM | OpenAI or Azure OpenAI |
| Frontend | Next.js |
| Integration | MCP (mcp-sql-server), Jira REST API |
| Infrastructure | Docker, CI/CD pipelines |

---

## Security and Governance

- RBAC with role-aware UI views
- MFA / token approval required for all write and configuration actions
- Full audit logging on every action
- Secrets management (env vars for MVP; Azure Key Vault / HashiCorp Vault for production)
- Data retention: raw metrics 90 days · aggregates 2 years · incidents and recommendations indefinite
- Confidence gate — recommendations below 0.60 require human validation before action

---

## Commercialization Roadmap

| Phase | Description |
|---|---|
| 1 | Internal accelerator — reduce toil for internal DBA teams |
| 2 | Consulting accelerator — ship as a delivery accelerator |
| 3 | Managed service — operate on behalf of customers |
| 4 | SaaS offering — multi-tenant hosted platform |
| 5 | Marketplace ecosystem — partner integrations and extensions |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AI hallucinations | Medium | High | Rule-based detection layer, approval gates, audits |
| pgvector index rebuild blocks queries | Medium | High | `CREATE INDEX CONCURRENTLY`, maintenance window |
| LLM context window overflow | Medium | Medium | Cap metrics to 10 snapshots; past incidents to 500 chars |
| Redis SPOF for Celery workers | Medium | High | Health alerts; Redis Sentinel post-MVP |
| API keys in env vars | High | High | Acceptable for MVP; Key Vault for production |
| False positive alerts | Medium | Medium | Feedback loop, threshold calibration |

---

## Documentation

Full architecture and design documentation is in `docs/architecture/`:

| Document | Description |
|---|---|
| `AI_DBA_Copilot_Enterprise_Blueprint.md` | Enterprise charter, business case, target architecture, MCP tool catalog |
| `AI_DBA_Copilot_Functional_Design.md` | Detailed functional design, module specs, workflows, security guardrails |
| `AI_DBA_Copilot_TDD.md` | Technical design document, component breakdown, sprint plan, success metrics |
| `Detailed_Component_Designs.md` | Deep-dive designs for Memory Layer, Detection Engine, Recommendation Engine, Jira, MCP, UI |

---

## License

See [LICENSE](LICENSE) for details.
