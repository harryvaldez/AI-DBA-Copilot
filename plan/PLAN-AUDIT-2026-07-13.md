---
title: Plan Document Audit
date: 2026-07-13
auditor: AI DBA Platform Team
scope: All documents in plan/
---

# Plan Document Audit — 2026-07-13

## Executive Summary

Comprehensive review of 20 plan documents found 4 critical issues, 6 inconsistencies, and 5 risks. All critical and high-severity issues have been resolved in the source files.

---

## Issues Resolved

| ID | Severity | Description | Resolution |
|----|----------|-------------|------------|
| I1 | 🔴 Critical | DROP INDEX classified as BLOCKED in SDD tree but APPROVAL_REQUIRED in code | Aligned tree to code; documented DROP INDEX as reversible |
| I2 | 🔴 Critical | Semantic search SQL referenced nonexistent incidents.rca_text column | Replaced with CONCAT of incident metadata; added JIRA_TICKET join |
| I3 | 🔴 Critical | LLMClient.embed() conflated LLM and embedding concerns | Extracted standalone EmbeddingClient class |
| I4 | 🟡 Medium | PRD-*.md files contain TSD+SDD+PRD stacked without indication | Added document-structure header to all 8 files |
| I5 | 🟡 Medium | Audit log spec missing jira_mapping and remediation_history | Added both endpoints; documented embeddings audit exception |
| I6 | 🟡 Medium | CORS config was placeholder only | Added concrete CORSMiddleware with origin, headers, preflight |
| I7 | 🟡 Medium | No PostgreSQL backup strategy defined | Added backup method, schedule, retention, restore procedure |
| I8 | 🟡 Medium | Endpoint naming mismatch (/jira_mapping vs /jira_mappings vs /mappings) | Aligned all endpoints across Memory and Jira PRDs/phases to `/jira_mappings` |
| I9 | 🟡 Medium | Recommendation detail endpoint path collision | Added dedicated `GET /recommendations/detail/{rec_id}` endpoint |
| I10 | 🔴 Critical | Synchronous execution of async MCP client calls in Automated Remediation | Converted Auto/Approved executors to async and awaited them in orchestrator |

## Open Gaps

| ID | Gap | Target Phase | Status |
|----|-----|-------------|--------|
| G1 | No Jira webhook receiver for bidirectional sync | Phase 11 (Task 11.9) | ✅ Solved |
| G2 | No embedding generation for JIRA_TICKET source type | Phase 7 (Task 7.6) | ✅ Solved |
| G3 | No standardized observability pattern across services | Phase 11 (Task 11.4) | ✅ Solved |
| G4 | No database connection pooling config for non-memory services | Phase 11 (Task 11.10) | ✅ Solved |
| G5 | No MCP server circuit breaker | Phase 10 (Task 10.7) | ✅ Solved |

## Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | pgvector IVFFlat rebuild blocks queries | Medium | High | Use CREATE INDEX CONCURRENTLY; schedule during maintenance |
| R2 | LLM context window overflow | Medium | Medium | Truncate metrics to 10 snapshots; cap past incidents at 500 chars |
| R3 | Redis SPOF for Celery | Medium | High | Add health alert; Redis Sentinel for post-MVP |
| R4 | No secrets vault — API keys in env vars | High | High | Acceptable for MVP; Azure KV / Vault for production |
| R5 | 4-hour fingerprint merges distinct issues | Low | Medium | UI badge when detection_count > 10 |

## Cross-Reference Validation

| Check | Status |
|-------|--------|
| Fingerprint formula (detection) ← → TDD REQ-006 | ✅ Consistent |
| Port assignments (8001–8006) across all docs | ✅ Consistent |
| Confidence gate (0.60) across all docs | ✅ Consistent |
| DDL ← → ORM models ← → migration scripts | ✅ Consistent |
| API route paths: memory-service ← → Copilot UI proxy | ✅ Consistent |
| Classification rules: recommendation ← → remediation | ✅ Consistent (post-fix) |

## Document Health

| Component | Status |
|-----------|--------|
| Detection Engine | ✅ Clean |
| Recommendation Engine | ✅ Clean |
| Jira Integration | ✅ Clean |
| MCP Integration Layer | ✅ Clean |
| Memory Layer | ✅ Clean |
| Predictive Analytics | ✅ Clean |
| Copilot UI | ✅ Clean |
| Automated Remediation | ✅ Clean |
| Master MVP | ✅ Clean |

## Next Review

- **Next full audit:** After Phase 6 completion
- **Pre-release audit:** Before Phase 11 sign-off (v1.0.0 tag)
