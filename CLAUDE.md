# AI DBA Copilot — Agent Instructions

## Project Overview
Enterprise AI-powered DBA platform. Reduces operational toil, preserves institutional knowledge, and improves RCA quality via MCP server integration, PostgreSQL memory layer, AI recommendation engine, Jira integration, and predictive analytics.

## Repository Structure

```
├── src/                          # Source code by component
│   ├── detection-engine/         # Rule/ML-based issue detection
│   ├── recommendation-engine/    # LLM-powered RCA generation
│   ├── jira-integration/         # Smart ticket management
│   ├── mcp-layer/                # MCP tool interfaces
│   ├── memory-service/           # PostgreSQL repository
│   └── predictive-analytics/     # Forecasting models
├── memory-layer/
│   └── migrations/               # Versioned SQL migrations
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   ├── architecture/             # Design documents
│   ├── api/                      # MCP tool contracts
│   └── operations/               # Runbooks
├── .github/
│   ├── workflows/                # CI/CD pipelines
│   └── templates/                # Issue/PR templates
└── .claude/
    ├── commands/                 # Agent commands
    └── templates/                # Agent templates
```

## Key Technologies
- **Memory Layer:** PostgreSQL 16+, pgvector, TimescaleDB
- **Detection:** Python (FastAPI / Celery), isolation forests
- **Recommendation:** OpenAI / Azure OpenAI, RAG with pgvector
- **Integration:** Jira REST API, FastMCP / MCP SDK
- **UI:** React / Next.js / TailwindCSS

## Build & Run Commands
- `npm install` — Install dependencies
- `npm test` — Run test suite
- `npm run build` — Build for production

## Architecture Constraints
- Read-only MCP operations are fully autonomous
- Write/config operations require explicit DBA approval via MFA/RBAC
- AI confidence < 0.60 requires human validation
- metric_snapshots retention: 90 days (raw), 2 years (aggregated)
