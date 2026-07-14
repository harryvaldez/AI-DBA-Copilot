# Memory Layer

PostgreSQL-based persistent repository for the AI DBA Copilot platform.

## Migrations

Versioned SQL migration scripts go in `migrations/`. Each migration should be:
- Numbered sequentially (e.g., `001_initial_schema.sql`)
- Reversible (include `-- DOWN` comments)
- Idempotent where possible

## Core Schema

| Table | Purpose | Retention |
|-------|---------|-----------|
| `metric_snapshots` | Point-in-time database metrics | 90 days |
| `incidents` | Detected issues with fingerprints | Indefinite |
| `recommendations` | AI-generated RCAs and action steps | Indefinite |
| `jira_mapping` | Incident-to-Jira ticket linkage | Indefinite |
| `embeddings` | pgvector embeddings for semantic search | Indefinite |
| `remediation_history` | Audit trail of remediation actions | Indefinite |
| `configuration_history` | Database configuration change snapshots | Indefinite |
