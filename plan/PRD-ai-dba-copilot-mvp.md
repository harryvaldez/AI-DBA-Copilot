# Product Requirements Document: AI DBA Copilot MVP

## 1. Summary
This document defines the MVP for AI DBA Copilot, an AI-assisted platform that helps database teams detect problems, understand root causes, and act safely. The MVP combines telemetry detection, Jira deduplication, AI recommendations, and searchable history in one workflow. It focuses on reducing repeated manual work while keeping strict human approval for risky actions.

## 2. Contacts
| Name | Role | Comment |
|------|------|---------|
| AI DBA Platform Team | Product and Engineering Owner | Owns scope, delivery, and quality for MVP.
| DBA Leads | Domain Stakeholders | Validate incident quality, recommendation quality, and operational safety.
| Security and Compliance Team | Governance Stakeholders | Validate RBAC, MFA approval flow, and auditability.
| SRE and Operations Team | Reliability Stakeholders | Validate production readiness and alerting behavior.

## 3. Background
### Context
Database operations teams often use many disconnected tools to monitor metrics, investigate incidents, and write corrective actions. This slows response time and causes repeat investigation work across teams.

### Why now
The team now has two key enablers already in place: an operational SQL Server MCP service and a clear technical implementation plan for an enterprise AI DBA platform. This makes it possible to ship a practical MVP quickly without rebuilding core integration pieces.

### What recently became possible
1. A stable MCP tool layer can provide consistent, safe database diagnostics.
2. A memory layer with vector search can reuse past incidents and recommendations.
3. AI generation can produce structured RCA output with confidence and risk scoring.

## 4. Objective
### Objective statement
Build an MVP that detects high-value database issues, generates trustworthy RCA recommendations, and helps DBAs take safe actions faster with full auditability.

### Why it matters
1. Customers and internal users get faster resolution of production database issues.
2. Teams reduce duplicate tickets and repeated analysis work.
3. The company preserves operational knowledge instead of losing it in chat threads and ad hoc notes.

### Strategic alignment
This MVP directly supports the platform strategy to reduce operational toil, improve RCA quality, and enforce safe AI-assisted operations with human control on risky changes.

### Key Results (SMART)
1. Reduce duplicate Jira incidents by at least 95 percent within 90 days of MVP release.
2. Reduce mean time to resolution by at least 30 percent within 90 days of MVP release.
3. Generate first RCA recommendation in under 5 minutes for at least 90 percent of new incidents.
4. Return semantic archive search results in under 3 seconds for at least 95 percent of queries at 10,000 embedding scale.
5. Ensure 100 percent of write or configuration actions require valid approval token and are audit logged.

## 5. Market Segment(s)
### Primary segment
Enterprise DBA and SRE teams managing SQL Server and mixed database estates who need fast triage, safe remediation, and clear audit trails.

### Secondary segment
Platform engineering teams that operate shared database services and need standardized incident handling across environments.

### Jobs to be done
1. When a database issue appears, I want immediate context and likely root cause so I can act quickly.
2. When incidents repeat, I want past fixes to be easy to find so I do not start from zero.
3. When an action can change production state, I want strict approval controls so risk is managed.

### Constraints
1. Read-only diagnostics can be autonomous.
2. Write or configuration actions must require explicit DBA approval with MFA or equivalent token.
3. Recommendations below confidence 0.60 must be flagged for human validation.

## 6. Value Proposition(s)
### Customer gains
1. Faster investigation with fewer tool switches.
2. Better recommendation quality through historical context and semantic retrieval.
3. Lower alert fatigue through deterministic fingerprinting and Jira deduplication.
4. Safer operations through approval gates, RBAC, and audit logs.

### Pains avoided
1. Repeated ticket creation for the same issue.
2. Slow manual correlation of metrics, query plans, and config changes.
3. Risky remediation execution without policy checks.

### Differentiation
1. Combines detection, recommendation, ticketing, and memory in one workflow.
2. Puts safety controls in the core flow instead of as optional extras.
3. Learns from prior incidents to improve future response quality.

## 7. Solution
### 7.1 UX and Prototypes
MVP user experience has three main views:
1. Anomaly Dashboard: active incidents, severity, trend, and quick filters.
2. Incident RCA Review: root cause summary, action steps, confidence, risk, and approval status.
3. Semantic Archive Search: natural language search over historical incidents, recommendations, and linked tickets.

Primary flow:
1. Detection engine identifies incident candidate.
2. Fingerprint logic checks active incident window to deduplicate.
3. Jira mapping creates or updates ticket.
4. Recommendation engine generates structured RCA and action steps.
5. DBA reviews and approves required actions in UI.
6. System logs actions and outcomes for future retrieval.

### 7.2 Key Features
1. Metric ingestion and detection engine:
   - Rule-based and ML-based anomaly detection.
   - Domain coverage for performance, capacity, availability, maintenance, and cost.
2. Deterministic incident deduplication:
   - Fingerprint hash based on db target, issue signal, and time bucket.
   - Active incident update path increments detection count.
3. Smart Jira integration:
   - Create or update logic using memory mapping and Jira search fallback.
   - Status sync and recommendation linking.
4. RAG-powered recommendation engine:
   - Retrieves top similar incidents before generation.
   - Produces strict JSON output with RCA, actions, risk, and confidence.
   - Applies confidence gate for human validation.
5. Semantic memory search:
   - Embedding storage and cosine similarity retrieval with pgvector.
   - Search results include incident and recommendation context.
6. Safe remediation flow:
   - Read-only diagnostics are autonomous.
   - Write or configuration scripts require approval token and are fully audited.

### 7.3 Technology
1. Backend services: Python FastAPI and Celery.
2. Memory layer: PostgreSQL 16 with pgvector.
3. AI layer: OpenAI or Azure OpenAI for generation and embeddings.
4. Integration: existing mcp-sql-server service, Jira REST API.
5. Frontend: Next.js with role-aware views and approval actions.

### 7.4 Assumptions
1. Existing MCP SQL Server integration remains stable and reachable in MVP environments.
2. Jira API limits are manageable with retry and backoff.
3. Available incident volume is enough to make semantic retrieval useful early.
4. Teams can define clear severity and escalation mappings before rollout.
5. Security stakeholders accept token-based approval flow for controlled write actions.

## 8. Release
### Timeline approach
Use phased delivery in relative windows instead of fixed calendar dates.

### MVP scope (Release 1)
Estimated duration: 10 to 14 weeks.

Included:
1. Memory schema and retention jobs.
2. MCP integration client with safety wrappers.
3. Detection engine with rules plus initial anomaly model.
4. Jira deduplication and mapping.
5. Recommendation engine with confidence gating.
6. Three core UI views (dashboard, RCA review, search).
7. Audit trail for controlled write actions.

### Post-MVP scope (Release 2)
Estimated duration after Release 1: 6 to 10 weeks.

Included:
1. Expanded predictive analytics and richer forecasting.
2. Broader database platform adapters beyond initial SQL Server focus.
3. Improved recommendation quality loop from remediation outcomes.
4. Reliability hardening for larger scale and longer retention analytics.

### Launch readiness criteria
1. All critical user flows pass integration tests.
2. Security controls validated for approval-gated actions.
3. Key result instrumentation is live and visible on operational dashboards.
4. Runbooks are complete for incident handling, rollback, and service recovery.