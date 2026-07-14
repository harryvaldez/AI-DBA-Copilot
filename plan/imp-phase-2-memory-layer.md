---
goal: Implementation Plan — Phase 2: Memory Layer
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 1 (Foundation)
tags: implementation, memory-layer, postgresql, pgvector, alembic
---

# Phase 2: Memory Layer

## Overview

Implement the full PostgreSQL schema with all 10 core tables, pgvector extension, Alembic migration pipeline, SQLAlchemy ORM models, retention/pruning service, embedding service, and comprehensive REST API.

**Estimated Duration:** 2 sprints (Sprints 3–4)

**Dependencies:** Phase 1 (foundation must provide Docker Compose with postgres + memory-service skeleton)

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 2.1 | Create 10 migration SQL scripts | 2 hr | `memory-layer/migrations/001–010_*.sql` | ⬜ |
| 2.2 | Initialize Alembic | 30 min | `src/memory-service/alembic.ini`, `alembic/` | ⬜ |
| 2.3 | Create SQLAlchemy ORM models | 1.5 hr | `src/memory-service/models/*.py` | ⬜ |
| 2.4 | Implement Metric CRUD endpoints | 1 hr | `src/memory-service/main.py` | ⬜ |
| 2.5 | Implement Incident CRUD endpoints | 1 hr | `src/memory-service/main.py` | ⬜ |
| 2.6 | Implement Recommendation CRUD endpoints | 30 min | `src/memory-service/main.py` | ⬜ |
| 2.7 | Implement Audit Log integration | 30 min | `src/memory-service/audit.py` | ⬜ |
| 2.8 | Implement Embedding service | 1 hr | `src/memory-service/embedding_service.py` | ⬜ |
| 2.9 | Implement Embedding search endpoint | 1 hr | `src/memory-service/main.py` | ⬜ |
| 2.10 | Implement Retention service | 1 hr | `src/memory-service/retention.py` | ⬜ |
| 2.11 | Integration test: CRUD operations | 1 hr | `tests/integration/test_memory_crud.py` | ⬜ |
| 2.12 | Integration test: Semantic search | 1 hr | `tests/integration/test_semantic_search.py` | ⬜ |

---

## Task 2.1: Migration SQL Scripts

**Directory:** `memory-layer/migrations/`

### 001_extensions.sql
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### 002_metric_snapshots.sql
```sql
CREATE TABLE metric_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    db_target VARCHAR(255) NOT NULL,
    metric_type VARCHAR(50) NOT NULL CHECK (metric_type IN (
        'PERFORMANCE','CAPACITY','AVAILABILITY','MAINTENANCE','COST'
    )),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_metrics_target_type_ts ON metric_snapshots (db_target, metric_type, created_at DESC);
CREATE INDEX idx_metrics_created_brin ON metric_snapshots USING BRIN (created_at) WITH (pages_per_range = 32);
```

### 003_incidents.sql
```sql
CREATE TABLE incidents (
    incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fingerprint VARCHAR(64) NOT NULL,
    error_code_or_metric_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','LOW')),
    domain VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','RESOLVED','IGNORED')),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    db_target VARCHAR(255) NOT NULL,
    detection_count INT NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX idx_incidents_active_fingerprint ON incidents (fingerprint) WHERE status = 'ACTIVE';
CREATE INDEX idx_incidents_status_severity ON incidents (status, severity);
```

### 004_recommendations.sql
```sql
CREATE TABLE recommendations (
    rec_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    rca_text TEXT NOT NULL,
    action_steps JSONB NOT NULL,
    confidence_score NUMERIC(4,2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
    requires_human_validation BOOLEAN NOT NULL DEFAULT FALSE,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_recs_incident ON recommendations (incident_id);
```

### 005_jira_mapping.sql
```sql
CREATE TABLE jira_mapping (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    jira_ticket_key VARCHAR(50) NOT NULL UNIQUE,
    sync_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (sync_status IN ('PENDING','SYNCED','FAILED')),
    last_sync TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_jira_incident ON jira_mapping (incident_id);
```

### 006_remediation_history.sql
```sql
CREATE TABLE remediation_history (
    remediation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rec_id UUID NOT NULL REFERENCES recommendations(rec_id),
    action_taken TEXT NOT NULL,
    executed_by VARCHAR(255) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL,
    result_details JSONB
);
CREATE INDEX idx_rem_history_rec ON remediation_history (rec_id);
```

### 007_configuration_history.sql
```sql
CREATE TABLE configuration_history (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    db_target VARCHAR(255) NOT NULL,
    parameter_name VARCHAR(255) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by VARCHAR(255)
);
CREATE INDEX idx_config_target_ts ON configuration_history (db_target, changed_at DESC);
```

### 008_embeddings.sql
```sql
CREATE TABLE embeddings (
    vector_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('INCIDENT','RECOMMENDATION','JIRA_TICKET')),
    source_id UUID NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id)
);
-- IVFFlat index created post-backfill (Task 2.9):
-- CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 009_metric_aggregates.sql
```sql
CREATE TABLE metric_aggregates (
    aggregate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    db_target VARCHAR(255) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    metric_key VARCHAR(100) NOT NULL,
    bucket_ts TIMESTAMPTZ NOT NULL,
    avg_value NUMERIC,
    min_value NUMERIC,
    max_value NUMERIC,
    sample_count INT NOT NULL,
    UNIQUE (db_target, metric_type, metric_key, bucket_ts)
);
CREATE INDEX idx_agg_target_type_ts ON metric_aggregates (db_target, metric_type, bucket_ts DESC);
```

### 010_audit_log.sql
```sql
CREATE TABLE audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('INSERT','UPDATE','DELETE')),
    actor VARCHAR(255),
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_table_record ON audit_log (table_name, record_id);
```

---

## Task 2.2: Initialize Alembic

```bash
cd src/memory-service
alembic init alembic
```

**File:** `src/memory-service/alembic.ini`
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/aidbacopilot
```

**File:** `src/memory-service/alembic/env.py`
- Set `target_metadata` from models `Base.metadata`.
- Import all models from `models/__init__.py`.
- Use `run_async` for async engine.

---

## Task 2.3: SQLAlchemy ORM Models

**Directory:** `src/memory-service/models/`

### Base (`models/base.py`)
```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

### Model per table — Example (`models/metric_snapshot.py`)
```python
from sqlalchemy import Column, String, DateTime, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from .base import Base

class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    
    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    db_target = Column(String(255), nullable=False)
    metric_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

### Models `__init__.py`
```python
from .base import Base
from .metric_snapshot import MetricSnapshot
from .incident import Incident
from .recommendation import Recommendation
from .jira_mapping import JiraMapping
from .remediation_history import RemediationHistory
from .configuration_history import ConfigurationHistory
from .embedding import Embedding
from .metric_aggregate import MetricAggregate
from .audit_log import AuditLog

__all__ = [
    "Base", "MetricSnapshot", "Incident", "Recommendation",
    "JiraMapping", "RemediationHistory", "ConfigurationHistory",
    "Embedding", "MetricAggregate", "AuditLog"
]
```

---

## Tasks 2.4–2.6: REST API Endpoints

**File:** `src/memory-service/main.py`

### Router Structure
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

snapshots_router = APIRouter(prefix="/snapshots", tags=["snapshots"])
incidents_router = APIRouter(prefix="/incidents", tags=["incidents"])
recommendations_router = APIRouter(prefix="/recommendations", tags=["recommendations"])
jira_mappings_router = APIRouter(prefix="/jira_mappings", tags=["jira_mappings"])

def get_db() -> AsyncSession:
    """Yield async DB session."""
```

### Endpoint Table

| Router | Method | Path | SQL Operation | Audit |
|--------|--------|------|---------------|-------|
| snapshots | POST | / | INSERT | Yes |
| snapshots | GET | / | SELECT with filters (db_target, metric_type, from, to, limit) | No |
| incidents | POST | / | INSERT | Yes |
| incidents | GET | / | SELECT with filters (status, severity, db_target, fingerprint) | No |
| incidents | GET | /{id} | SELECT by PK | No |
| incidents | PATCH | /{id} | UPDATE status, detection_count, resolved_at | Yes |
| recommendations | POST | / | INSERT | Yes |
| recommendations | GET | /{incident_id} | SELECT by incident_id FK | No |
| recommendations | GET | /detail/{rec_id} | SELECT by PK | No |
| jira_mappings | POST | / | INSERT | Yes |
| jira_mappings | GET | /{incident_id} | SELECT by incident_id FK | No |
| jira_mappings | PATCH | /{incident_id} | UPDATE sync_status, last_sync | Yes |

### Audit Wrapper Pattern
```python
async def audit_log(db: AsyncSession, table_name: str, record_id: UUID,
                    action: str, actor: str, payload: dict):
    log = AuditLog(
        table_name=table_name, record_id=record_id,
        action=action, actor=actor, payload=payload
    )
    db.add(log)
    # No commit here — committed in the same transaction as the main operation
```

---

## Task 2.7: Audit Log Integration

**File:** `src/memory-service/audit.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from .models.audit_log import AuditLog

async def write_audit_entry(
    db: AsyncSession,
    table_name: str,
    record_id: str,
    action: str,       # "INSERT" | "UPDATE" | "DELETE"
    actor: str,        # Service name or user identity
    payload: dict = None
):
    """Add audit log entry. Called within same transaction as main operation."""
    entry = AuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        actor=actor,
        payload=payload or {}
    )
    db.add(entry)
```

---

## Tasks 2.8–2.9: Embedding Service & Search

**File:** `src/memory-service/embedding_service.py`

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class EmbeddingService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def embed_and_store(self, source_type: str, source_id: str, embedding: list[float]):
        """Insert or update embedding for a source record."""
        await self.db.execute(
            text("""
                INSERT INTO embeddings (source_type, source_id, embedding)
                VALUES (:source_type, :source_id, :embedding::vector)
                ON CONFLICT (source_type, source_id)
                DO UPDATE SET embedding = :embedding::vector
            """),
            {"source_type": source_type, "source_id": source_id, "embedding": embedding}
        )
    
    async def search_similar(self, query_vector: list[float], limit: int = 5, threshold: float = 0.5):
        """Cosine similarity search with source table JOIN."""
        result = await self.db.execute(
            text("""
                SELECT 
                    e.source_type,
                    e.source_id,
                    1 - (e.embedding <=> :query_vector::vector) AS similarity,
                    CASE 
                        WHEN e.source_type = 'INCIDENT' THEN 
                            CONCAT(i.error_code_or_metric_type, ' — ', i.domain, ' incident on ', i.db_target)
                        WHEN e.source_type = 'RECOMMENDATION' THEN r.rca_text
                        WHEN e.source_type = 'JIRA_TICKET' THEN j.jira_ticket_key
                        ELSE NULL 
                    END as content,
                    e.created_at
                FROM embeddings e
                LEFT JOIN recommendations r ON e.source_type = 'RECOMMENDATION' AND e.source_id::text = r.rec_id::text
                LEFT JOIN incidents i ON e.source_type = 'INCIDENT' AND e.source_id::text = i.incident_id::text
                LEFT JOIN jira_mapping j ON e.source_type = 'JIRA_TICKET' AND e.source_id::text = j.mapping_id::text
                WHERE 1 - (e.embedding <=> :query_vector::vector) > :threshold
                ORDER BY similarity DESC
                LIMIT :limit
            """),
            {"query_vector": query_vector, "limit": limit, "threshold": threshold}
        )
        return result.mappings().all()
```

---

## Task 2.10: Retention Service

**File:** `src/memory-service/retention.py`

```python
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class RetentionService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def prune_metric_snapshots(self, retention_days: int = 90):
        """Delete raw snapshots older than retention_days."""
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        result = await self.db.execute(
            text("DELETE FROM metric_snapshots WHERE created_at < :cutoff"),
            {"cutoff": cutoff}
        )
        return result.rowcount
    
    async def aggregate_metrics(self):
        """Hourly rollup into metric_aggregates."""
        await self.db.execute(text("""
            INSERT INTO metric_aggregates (db_target, metric_type, metric_key, bucket_ts,
                                           avg_value, min_value, max_value, sample_count)
            SELECT 
                db_target, metric_type,
                payload->>'metric_key' as metric_key,
                date_trunc('hour', created_at) as bucket_ts,
                AVG((payload->>'value')::numeric),
                MIN((payload->>'value')::numeric),
                MAX((payload->>'value')::numeric),
                COUNT(*)
            FROM metric_snapshots
            WHERE created_at >= date_trunc('hour', NOW()) - INTERVAL '1 hour'
              AND created_at < date_trunc('hour', NOW())
            GROUP BY db_target, metric_type, payload->>'metric_key', date_trunc('hour', created_at)
            ON CONFLICT (db_target, metric_type, metric_key, bucket_ts)
            DO UPDATE SET avg_value = EXCLUDED.avg_value,
                          min_value = EXCLUDED.min_value,
                          max_value = EXCLUDED.max_value,
                          sample_count = EXCLUDED.sample_count
        """))
    
    async def prune_aggregates(self, retention_days: int = 730):
        """Delete aggregates older than retention_days."""
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        result = await self.db.execute(
            text("DELETE FROM metric_aggregates WHERE bucket_ts < :cutoff"),
            {"cutoff": cutoff}
        )
        return result.rowcount
```

---

## Tasks 2.11–2.12: Tests

### Test File: `tests/integration/test_memory_crud.py`
```python
"""Integration tests for memory service CRUD operations."""
import pytest
from httpx import AsyncClient

BASE_URL = "http://localhost:8005"

@pytest.mark.asyncio
async def test_create_snapshot():
    async with AsyncClient(base_url=BASE_URL) as client:
        response = await client.post("/snapshots", json={
            "db_target": "test_db",
            "metric_type": "PERFORMANCE",
            "payload": {"cpu": 85, "memory": 60}
        })
        assert response.status_code == 201
        data = response.json()
        assert "snapshot_id" in data
        assert data["db_target"] == "test_db"

@pytest.mark.asyncio
async def test_create_incident():
    async with AsyncClient(base_url=BASE_URL) as client:
        response = await client.post("/incidents", json={
            "fingerprint": "abc123",
            "error_code_or_metric_type": "high_cpu",
            "severity": "HIGH",
            "domain": "PERFORMANCE",
            "db_target": "test_db"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["fingerprint"] == "abc123"
        assert data["status"] == "ACTIVE"

@pytest.mark.asyncio
async def test_duplicate_fingerprint_returns_409():
    async with AsyncClient(base_url=BASE_URL) as client:
        response = await client.post("/incidents", json={
            "fingerprint": "dup_test",
            "error_code_or_metric_type": "test",
            "severity": "LOW",
            "domain": "PERFORMANCE",
            "db_target": "test_db"
        })
        assert response.status_code == 201
        response2 = await client.post("/incidents", json={
            "fingerprint": "dup_test",
            "error_code_or_metric_type": "test",
            "severity": "LOW",
            "domain": "PERFORMANCE",
            "db_target": "test_db"
        })
        assert response2.status_code == 409
```

### Test File: `tests/integration/test_semantic_search.py`
```python
"""Integration test for semantic search."""
import pytest
from httpx import AsyncClient

BASE_URL = "http://localhost:8005"

@pytest.mark.asyncio
async def test_store_and_search_embedding():
    async with AsyncClient(base_url=BASE_URL) as client:
        # Create incident + recommendation first
        inc_resp = await client.post("/incidents", json={
            "fingerprint": "sem_test_1",
            "error_code_or_metric_type": "blocking",
            "severity": "HIGH",
            "domain": "PERFORMANCE",
            "db_target": "test_db"
        })
        inc_id = inc_resp.json()["incident_id"]
        
        rec_resp = await client.post("/recommendations", json={
            "incident_id": inc_id,
            "rca_text": "Blocking caused by long-running transaction on orders table.",
            "action_steps": [{"step": "Kill blocking session", "command": "KILL 123", "type": "APPROVAL_REQUIRED"}],
            "confidence_score": 0.85,
            "risk_level": "MEDIUM"
        })
        rec_id = rec_resp.json()["rec_id"]
        
        # Store embedding
        embed_resp = await client.post("/embeddings", json={
            "source_type": "RECOMMENDATION",
            "source_id": rec_id,
            "embedding": [0.01] * 1536  # Dummy vector
        })
        assert embed_resp.status_code == 201
        
        # Search
        search_resp = await client.post("/embeddings/search", json={
            "query_vector": [0.01] * 1536,
            "limit": 5,
            "threshold": 0.5
        })
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) > 0
        assert results[0]["source_type"] == "RECOMMENDATION"
```

## Phase 2 Completion Criteria

- [ ] All 10 migration scripts apply without errors to a fresh PostgreSQL 16 instance with pgvector
- [ ] Alembic migration produces same schema as raw SQL scripts
- [ ] Metric snapshot create and query works with all 5 metric_type values
- [ ] Incident create with unique fingerprint → 201, duplicate → 409
- [ ] Recommendation create → links to incident via FK
- [ ] Jira mapping create → unique jira_ticket_key enforced
- [ ] Embedding store → unique (source_type, source_id) enforced
- [ ] Semantic search returns ranked results with similarity scores
- [ ] Retention job prunes rows older than configured window
- [ ] Audit log captures every INSERT, UPDATE across tracked tables
