<!--
  Document Structure: This file contains three stacked specification layers.
    § TSD — Technical Specification Document (requirements, API contracts, DDL, configs)
    § SDD — Software Design Document (architecture diagrams, component specs, data models)
    § PRD — Product Requirements Document (business context, objectives, market, release)
  The filename prefix "PRD-" is retained for discoverability.
  Last reviewed: 2026-07-13 (see plan/PLAN-AUDIT-2026-07-13.md)
-->

# Technical Specification Document: Memory Layer

## 1. Technical Requirements

### 1.1 Mandatory Requirements
| ID | Requirement | Verification |
|----|-------------|-------------|
| ML-TR-001 | All 10 migration scripts must apply without errors on PostgreSQL 16 with pgvector | Integration test |
| ML-TR-002 | pgvector extension must be installed (version >= 0.5.0) | Static config |
| ML-TR-003 | Embedding dimension must be exactly 1536 | DDL constraint |
| ML-TR-004 | Audit log must capture INSERT, UPDATE, DELETE for all tracked tables | Integration test |
| ML-TR-005 | Metric snapshot pruning must remove rows older than 90 days | Integration test |
| ML-TR-006 | Metric aggregation rollup must produce correct AVG/MIN/MAX/SAMPLE_COUNT | Integration test |
| ML-TR-007 | IVFFlat index must be created only after sufficient rows exist (>1000) | Implementation |
| ML-TR-008 | Semantic search must use cosine similarity (<=>) | Integration test |
| ML-TR-009 | All API endpoints must validate input payloads against schemas | Integration test |
| ML-TR-010 | Embedding upsert must use (source_type, source_id) unique constraint | Integration test |

### 1.2 Performance Targets
| Metric | Target | Measurement |
|--------|--------|-------------|
| Metric snapshot insert | < 100ms P95 | Request timer |
| Incident create | < 200ms P95 | Request timer |
| Incident query (filtered) | < 500ms P95 at 100K rows | Benchmark |
| Semantic search (10K embeddings) | < 3s P95 | Benchmark |
| Retention prune (1M rows) | < 60s | Timer |
| Aggregate rollup (24h of data) | < 30s | Timer |
| Embedding search with JOIN | < 5s P95 at 100K embeddings | Benchmark |

## 2. API Specification

### 2.1 OpenAPI Contract

**Service:** `memory-service` on port 8005

```yaml
openapi: 3.0.3
info:
  title: AI DBA Copilot - Memory Service
  version: 1.0.0

paths:
  /health:
    get:
      operationId: healthCheck
      responses:
        '200':
          description: Service healthy

  /snapshots:
    post:
      operationId: createSnapshot
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/MetricSnapshot'
      responses:
        '201':
          description: Snapshot created
    get:
      operationId: listSnapshots
      parameters:
        - name: db_target
          in: query
          schema:
            type: string
        - name: metric_type
          in: query
          schema:
            type: string
            enum: [PERFORMANCE, CAPACITY, AVAILABILITY, MAINTENANCE, COST]
        - name: from
          in: query
          schema:
            type: string
            format: date-time
        - name: to
          in: query
          schema:
            type: string
            format: date-time
        - name: limit
          in: query
          schema:
            type: integer
            default: 100
      responses:
        '200':
          description: List of snapshots

  /incidents:
    post:
      operationId: createIncident
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/IncidentCreate'
      responses:
        '201':
          description: Incident created
        '409':
          description: Active incident with same fingerprint exists
    get:
      operationId: listIncidents
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [ACTIVE, RESOLVED, IGNORED]
        - name: severity
          in: query
          schema:
            type: string
            enum: [CRITICAL, HIGH, MEDIUM, LOW]
        - name: db_target
          in: query
          schema:
            type: string
        - name: fingerprint
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
      responses:
        '200':
          description: List of incidents

  /incidents/{incident_id}:
    get:
      operationId: getIncident
      parameters:
        - name: incident_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Incident detail
        '404':
          description: Incident not found
    patch:
      operationId: updateIncident
      parameters:
        - name: incident_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/IncidentUpdate'
      responses:
        '200':
          description: Incident updated

  /recommendations:
    post:
      operationId: createRecommendation
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RecommendationCreate'
      responses:
        '201':
          description: Recommendation created

  /recommendations/{incident_id}:
    get:
      operationId: getRecommendationsForIncident
      parameters:
        - name: incident_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: List of recommendations

  /recommendations/detail/{rec_id}:
    get:
      operationId: getRecommendation
      parameters:
        - name: rec_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Recommendation details
        '404':
          description: Recommendation not found

  /jira_mappings:
    post:
      operationId: createJiraMapping
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JiraMappingCreate'
      responses:
        '201':
          description: Mapping created

  /jira_mappings/{incident_id}:
    get:
      operationId: getJiraMappingByIncident
      parameters:
        - name: incident_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Jira mapping details
        '404':
          description: Mapping not found
    patch:
      operationId: updateJiraMapping
      parameters:
        - name: incident_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/JiraMappingUpdate'
      responses:
        '200':
          description: Mapping updated

  /embeddings:
    post:
      operationId: storeEmbedding
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/EmbeddingStore'
      responses:
        '201':
          description: Embedding stored
        '409':
          description: Embedding already exists for this source

  /embeddings/search:
    post:
      operationId: searchEmbeddings
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                query_vector:
                  type: array
                  items:
                    type: number
                  minItems: 1536
                  maxItems: 1536
                limit:
                  type: integer
                  default: 5
                threshold:
                  type: number
                  default: 0.5
      responses:
        '200':
          description: Search results ranked by similarity

components:
  schemas:
    MetricSnapshot:
      type: object
      required: [db_target, metric_type, payload]
      properties:
        db_target:
          type: string
          maxLength: 255
        metric_type:
          type: string
          enum: [PERFORMANCE, CAPACITY, AVAILABILITY, MAINTENANCE, COST]
        payload:
          type: object

    IncidentCreate:
      type: object
      required: [fingerprint, error_code_or_metric_type, severity, domain, db_target]
      properties:
        fingerprint:
          type: string
          maxLength: 64
        error_code_or_metric_type:
          type: string
          maxLength: 100
        severity:
          type: string
          enum: [CRITICAL, HIGH, MEDIUM, LOW]
        domain:
          type: string
        status:
          type: string
          default: ACTIVE
        db_target:
          type: string
        detection_count:
          type: integer
          default: 1

    IncidentUpdate:
      type: object
      properties:
        status:
          type: string
          enum: [ACTIVE, RESOLVED, IGNORED]
        detection_count:
          type: integer
        severity:
          type: string
          enum: [CRITICAL, HIGH, MEDIUM, LOW]
        resolved_at:
          type: string
          format: date-time
          nullable: true

    RecommendationCreate:
      type: object
      required: [incident_id, rca_text, action_steps, confidence_score, risk_level]
      properties:
        incident_id:
          type: string
          format: uuid
        rca_text:
          type: string
        action_steps:
          type: array
        confidence_score:
          type: number
          minimum: 0
          maximum: 1
        risk_level:
          type: string
          enum: [LOW, MEDIUM, HIGH]
        requires_human_validation:
          type: boolean
          default: false

    EmbeddingStore:
      type: object
      required: [source_type, source_id, embedding]
      properties:
        source_type:
          type: string
          enum: [INCIDENT, RECOMMENDATION, JIRA_TICKET]
        source_id:
          type: string
          format: uuid
        embedding:
          type: array
          items:
            type: number
          minItems: 1536
          maxItems: 1536

    JiraMappingCreate:
      type: object
      required: [incident_id, jira_ticket_key]
      properties:
        incident_id:
          type: string
          format: uuid
        jira_ticket_key:
          type: string
          maxLength: 50
        sync_status:
          type: string
          default: PENDING

    JiraMappingUpdate:
      type: object
      properties:
        sync_status:
          type: string
          enum: [PENDING, SYNCED, FAILED]
```

## 3. Complete DDL Reference

### 3.1 Extensions
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### 3.2 Core Tables
```sql
-- metric_snapshots
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
CREATE INDEX idx_metrics_created_brin ON metric_snapshots USING BRIN (created_at);

-- incidents
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

-- recommendations
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

-- jira_mapping
CREATE TABLE jira_mapping (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
    jira_ticket_key VARCHAR(50) NOT NULL UNIQUE,
    sync_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (sync_status IN ('PENDING','SYNCED','FAILED')),
    last_sync TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_jira_incident ON jira_mapping (incident_id);

-- remediation_history
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

-- configuration_history
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

-- embeddings
CREATE TABLE embeddings (
    vector_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('INCIDENT','RECOMMENDATION','JIRA_TICKET')),
    source_id UUID NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_type, source_id)
);
-- IVFFlat index created after backfill:
-- CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- metric_aggregates
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

-- audit_log
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

## 4. Configuration Specification

```yaml
# config/memory-service.yaml
service:
  name: memory-service
  port: 8005
  log_level: INFO

database:
  url: ${DATABASE_URL}
  pool_size: 10
  max_overflow: 20
  pool_timeout_seconds: 30
  pool_recycle_seconds: 3600
  echo: false  # SQL logging

retention:
  snapshot_retention_days: 90
  aggregate_retention_days: 730
  prune_schedule: "0 1 * * *"      # Daily 01:00 UTC
  aggregate_schedule: "0 * * * *"  # Hourly

embedding:
  dimension: 1536
  index_type: ivfflat          # ivfflat | hnsw (future)
  ivfflat_lists: 100
  rebuild_threshold: 1000       # Minimum rows before index creation
  search_limit_default: 5
  search_threshold_default: 0.5
```

## 5. Audit Log Specification

Every mutating API endpoint must write to the audit_log table within the same transaction:

| Endpoint | Table | Action | Actor Source |
|----------|-------|--------|-------------|
| POST /snapshots | metric_snapshots | INSERT | Internal API key or service name |
| POST /incidents | incidents | INSERT | Detection Engine service name |
| PATCH /incidents/{id} | incidents | UPDATE | Detection Engine service name |
| POST /recommendations | recommendations | INSERT | Recommendation Engine service name |
| POST /embeddings | embeddings | INSERT | Recommendation Engine service name |
| POST /jira_mapping | jira_mapping | INSERT | Jira Integration service name |
| POST /remediation_history | remediation_history | INSERT | Remediation Orchestrator service name |

> **Exception:** `POST /embeddings` does **not** write to `audit_log`. Embeddings are derived data (machine-generated vectors), not business data. If audit compliance requires full coverage in the future, this exception can be removed.

## 6. Performance Specification

| Scenario | Target | Measurement |
|----------|--------|-------------|
| Snapshot insert throughput | 100/s | Load test |
| Incident query (active, filtered) | < 500ms at 10K incidents | Benchmark |
| Semantic search (10K embeddings) | < 3s P95 | Benchmark |
| Semantic search (100K embeddings) | < 10s P95 | Benchmark |
| Retention prune (1M snapshots) | < 60s | Timer |
| Aggregate rollup (24h, 50 targets) | < 30s | Timer |
| Audit log insert overhead | < 10ms per mutation | Timer |

## 7. Error Handling Specification

| Error Scenario | HTTP Status | Log Level | Details |
|----------------|-------------|-----------|---------|
| Fingerprint uniqueness violation | 409 | INFO | Existing incident_id returned in body |
| Invalid metric_type CHECK | 400 | WARNING | Allowed values returned |
| Embedding dimension mismatch | 400 | WARNING | Expected 1536, got N |
| Source uniqueness violation | 409 | INFO | Embedding already exists |
| Database connection failure | 503 | CRITICAL | Retry with pool recycle |

## 8. Implementation Notes

### 8.1 Semantic Search Query
```sql
SELECT 
    e.source_type,
    e.source_id,
    e.created_at,
    1 - (e.embedding <=> :query_vector) AS similarity,
    CASE 
        WHEN e.source_type = 'INCIDENT' THEN 
            CONCAT(i.error_code_or_metric_type, ' — ', i.domain, ' incident on ', i.db_target)
        WHEN e.source_type = 'RECOMMENDATION' THEN r.rca_text
        WHEN e.source_type = 'JIRA_TICKET' THEN j.jira_ticket_key
        ELSE NULL 
    END as content
FROM embeddings e
LEFT JOIN incidents i ON e.source_type = 'INCIDENT' AND e.source_id = i.incident_id
LEFT JOIN recommendations r ON e.source_type = 'RECOMMENDATION' AND e.source_id = r.rec_id
LEFT JOIN jira_mapping j ON e.source_type = 'JIRA_TICKET' AND e.source_id = j.mapping_id
WHERE 1 - (e.embedding <=> :query_vector) > :threshold
ORDER BY similarity DESC
LIMIT :limit;
```

### 8.2 IVFFlat Index Strategy
- Create index only after backfill inserts > 1000 rows (IVFFlat requires training data).
- Use `lists = 100` for up to 100K embeddings.
- Rebuild index if INSERT volume exceeds 50% of existing count.

### 8.3 Retention Job Implementation
```python
async def prune_metric_snapshots():
    cutoff = datetime.now() - timedelta(days=90)
    result = await db.execute(
        "DELETE FROM metric_snapshots WHERE created_at < :cutoff",
        {"cutoff": cutoff}
    )
    logger.info(f"Pruned {result.rowcount} metric_snapshots")
```

---

# Software Design Document: Memory Layer

## 1. Overview

This SDD describes the detailed technical design of the Memory Layer — the platform's persistent PostgreSQL data store. It defines ten core tables, pgvector-based semantic search, automated data retention, full audit logging, and a comprehensive REST API consumed by all platform services.

## 2. Architecture

### 2.1 Entity Relationship Diagram

```mermaid
erDiagram
    metric_snapshots {
        uuid snapshot_id PK
        varchar db_target
        varchar metric_type
        jsonb payload
        timestamptz created_at
    }
    
    incidents {
        uuid incident_id PK
        varchar fingerprint UK
        varchar error_code_or_metric_type
        varchar severity
        varchar domain
        varchar status
        int detection_count
        timestamptz detected_at
        timestamptz resolved_at
        varchar db_target
    }
    
    recommendations {
        uuid rec_id PK
        uuid incident_id FK
        text rca_text
        jsonb action_steps
        numeric confidence_score
        varchar risk_level
        boolean requires_human_validation
        timestamptz generated_at
    }
    
    jira_mapping {
        uuid mapping_id PK
        uuid incident_id FK
        varchar jira_ticket_key UK
        varchar sync_status
        timestamptz last_sync
        timestamptz created_at
    }
    
    remediation_history {
        uuid remediation_id PK
        uuid rec_id FK
        text action_taken
        varchar executed_by
        boolean success
        jsonb result_details
        timestamptz executed_at
    }
    
    configuration_history {
        uuid config_id PK
        varchar db_target
        varchar parameter_name
        text old_value
        text new_value
        varchar changed_by
        timestamptz changed_at
    }
    
    embeddings {
        uuid vector_id PK
        varchar source_type
        uuid source_id
        vector embedding
        timestamptz created_at
    }
    
    metric_aggregates {
        uuid aggregate_id PK
        varchar db_target
        varchar metric_type
        varchar metric_key
        timestamptz bucket_ts
        numeric avg_value
        numeric min_value
        numeric max_value
        int sample_count
    }
    
    audit_log {
        uuid audit_id PK
        varchar table_name
        uuid record_id
        varchar action
        varchar actor
        jsonb payload
        timestamptz created_at
    }
    
    incidents ||--o{ recommendations : "has"
    incidents ||--o| jira_mapping : "maps to"
    recommendations ||--o{ remediation_history : "triggers"
    incidents ||--o{ embeddings : "embedded as"
    recommendations ||--o{ embeddings : "embedded as"
```

### 2.2 Migration Strategy

```mermaid
graph LR
    A[memory-layer/migrations/] -->|Alembic revision| B[src/memory-service/alembic/]
    B -->|alembic upgrade head| C[(PostgreSQL 16)]
    
    subgraph "Migration Files"
        M1[001_extensions.sql]
        M2[002_metric_snapshots.sql]
        M3[003_incidents.sql]
        M4[004_recommendations.sql]
        M5[005_jira_mapping.sql]
        M6[006_remediation_history.sql]
        M7[007_configuration_history.sql]
        M8[008_embeddings.sql]
        M9[009_metric_aggregates.sql]
        M10[010_audit_log.sql]
    end
    
    M1 --> M2 --> M3 --> M4 --> M5 --> M6 --> M7 --> M8 --> M9 --> M10
```

## 3. Complete DDL Reference

### 3.1 Extensions
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### 3.2 metric_snapshots
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

CREATE INDEX idx_metrics_target_type_ts 
    ON metric_snapshots (db_target, metric_type, created_at DESC);
CREATE INDEX idx_metrics_created_at_brin 
    ON metric_snapshots USING BRIN (created_at) WITH (pages_per_range = 32);
```

### 3.3 incidents
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

CREATE UNIQUE INDEX idx_incidents_active_fingerprint 
    ON incidents (fingerprint) WHERE status = 'ACTIVE';
CREATE INDEX idx_incidents_status_severity 
    ON incidents (status, severity);
```

### 3.4 recommendations
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

### 3.5 jira_mapping
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

### 3.6 remediation_history through 3.10 audit_log

[Full DDL for tables 006–010 follows the same pattern as detailed in the implementation plan TASK-021 through TASK-025.]

## 4. Component Specifications

### 4.1 SQLAlchemy ORM Models

**File:** `src/memory-service/models/`

Each migration has a corresponding SQLAlchemy model class:

```python
# models/metric_snapshot.py
class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    snapshot_id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    db_target = Column(String(255), nullable=False)
    metric_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

# models/incident.py (similar pattern for each table)
```

### 4.2 Retention Service

**File:** `src/memory-service/retention.py`

**Class: RetentionService**

| Method | Description | Schedule |
|--------|-------------|----------|
| prune_metric_snapshots() | DELETE FROM metric_snapshots WHERE created_at < NOW() - INTERVAL '90 days' | Daily 01:00 UTC |
| aggregate_metrics() | Hourly rollup: AVG, MIN, MAX, COUNT per (db_target, metric_type, metric_key, bucket) | Hourly |
| prune_aggregates() | DELETE FROM metric_aggregates WHERE bucket_ts < NOW() - INTERVAL '2 years' | Daily 01:30 UTC |
| rebuild_ivfflat_index() | DROP/CREATE INDEX idx_embeddings_vector WITH (lists=100) | After insert count exceeds threshold |

### 4.3 Embedding Service

**File:** `src/memory-service/embedding_service.py`

**Class: EmbeddingService**

| Method | Description |
|--------|-------------|
| embed_and_store(source_type, source_id, text) | Generate embedding via EmbeddingClient, upsert into embeddings table |
| search_similar(query_text, limit=5) | Embed query, cosine similarity search, JOIN source tables |
| sync_missing_embeddings() | Find records without embeddings, generate and store |

**Search Query:**
```sql
SELECT 
    e.source_type,
    e.source_id,
    e.created_at as embedding_created,
    1 - (e.embedding <=> :query_vector) AS similarity,
    CASE 
        WHEN e.source_type = 'INCIDENT' THEN 
            CONCAT(i.error_code_or_metric_type, ' — ', i.domain, ' incident on ', i.db_target)
        WHEN e.source_type = 'RECOMMENDATION' THEN r.rca_text
        WHEN e.source_type = 'JIRA_TICKET' THEN j.jira_ticket_key
        ELSE NULL 
    END as content
FROM embeddings e
LEFT JOIN incidents i ON e.source_type = 'INCIDENT' AND e.source_id = i.incident_id
LEFT JOIN recommendations r ON e.source_type = 'RECOMMENDATION' AND e.source_id = r.rec_id
LEFT JOIN jira_mapping j ON e.source_type = 'JIRA_TICKET' AND e.source_id = j.mapping_id
WHERE 1 - (e.embedding <=> :query_vector) > :threshold
ORDER BY similarity DESC
LIMIT :limit;
```

## 5. REST API Contract

**Service:** `src/memory-service/main.py` (port 8005)

| Method | Path | Request | Response | Audit |
|--------|------|---------|----------|-------|
| GET | /health | — | `{"status": "ok"}` | No |
| POST | /snapshots | MetricSnapshot | 201 Created | Yes |
| GET | /snapshots | ?db_target&from&to | `[snapshots]` | No |
| POST | /incidents | Incident | 201 Created | Yes |
| GET | /incidents | ?status&severity&db_target | `[incidents]` | No |
| GET | /incidents/{id} | — | Incident detail | No |
| PATCH | /incidents/{id} | Partial update | 200 OK | Yes |
| POST | /recommendations | Recommendation | 201 Created | Yes |
| GET | /recommendations/{incident_id} | — | `[recommendations]` | No |
| POST | /embeddings | Embedding | 201 Created | No |
| POST | /embeddings/search | `{"query", "limit"}` | `[{source, content, similarity}]` | No |

## 6. Error Handling

| Scenario | Behavior | Error Code |
|----------|----------|------------|
| Unique fingerprint violation | Return 409 with existing incident_id | DB_001 |
| Invalid metric_type CHECK | Return 400 with allowed values | VAL_001 |
| Embedding dimension mismatch | Return 400 with expected dimension | EMB_001 |
| Retention job partial failure | Log error, continue with next operation | RET_001 |
| Audit log write failure | Log critical, proceed with main operation | AUD_001 |

## 7. Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | postgresql+asyncpg://postgres:postgres@postgres:5432/aidbacopilot | PostgreSQL connection string |
| EMBEDDING_SERVICE_URL | http://recommendation-engine:8002 | Embedding client endpoint |
| VECTOR_DIMENSION | 1536 | Embedding vector dimension |
| SNAPSHOT_RETENTION_DAYS | 90 | Raw snapshot retention period |
| AGGREGATE_RETENTION_DAYS | 730 | Aggregated metric retention period |

## 8. Testing

| Test ID | Description | Type |
|---------|-------------|------|
| T-DDL-001 | All migrations apply cleanly to fresh PG 16 instance | Integration |
| T-DDL-002 | Extensions vector and pg_stat_statements installed | Integration |
| T-CRUD-001 | Insert and query metric_snapshot | Integration |
| T-CRUD-002 | Insert incident, verify fingerprint uniqueness | Integration |
| T-CRUD-003 | Create recommendation linked to incident | Integration |
| T-RET-001 | Retention prunes rows older than 90 days | Integration |
| T-RET-002 | Aggregate rollup produces correct AVG/MIN/MAX | Integration |
| T-SRCH-001 | Semantic search returns correct similarity ranking | Integration |
| T-SRCH-002 | Search latency < 3s at 10K embeddings | Benchmark |
| T-AUD-001 | INSERT produces audit_log entry | Integration |
| T-AUD-002 | UPDATE produces audit_log entry with old/new values | Integration |

---

# Product Requirements Document: Memory Layer

## 1. Summary
The Memory Layer is the platform's permanent data store. Built on PostgreSQL 16 with pgvector, it stores metric snapshots, incidents, recommendations, Jira mappings, remediation history, configuration history, embeddings, metric aggregates, and an audit log. It provides the data foundation for detection, recommendation, semantic search, and predictive analytics.

## 2. Contacts
| Name | Role | Comment |
|------|------|---------|
| AI DBA Platform Team | Product and Engineering Owner | Owns schema correctness, migration management, and data retention compliance. |
| DBA Leads | Domain Stakeholders | Validate retention requirements and query patterns. |
| SRE Team | Operations Stakeholder | Validates backup strategy, performance at scale, and pruning reliability. |

## 3. Background
### Context
Every platform component (detection engine, recommendation engine, Jira integration, predictive analytics, UI) needs structured, queryable storage. Without a shared memory layer, each service would maintain its own store with inconsistent schemas and no cross-service query capability.

### Why now
All downstream components depend on the memory layer schema. It must be defined and deployed before any other service can store or retrieve data.

### What recently became possible
1. PostgreSQL 16 with pgvector 0.5+ provides both relational storage and vector search in one database.
2. Alembic provides versioned, reversible schema migrations.
3. JSONB columns enable flexible metric payload storage without rigid schema for every metric type.

## 4. Objective
### Objective statement
Build a PostgreSQL-based memory layer with ten core tables, vector search capability, automated retention, full audit logging, and a comprehensive REST API for all platform services.

### Why it matters
1. Every platform component depends on the memory layer for reads and writes — it is the single source of truth.
2. Data retention compliance (90 days raw, 2 years aggregated) requires automated pruning and rollup.
3. Semantic search quality depends on proper pgvector indexing and embedding storage.

### Strategic alignment
The memory layer implements the data retention, security (audit logging), and performance constraints defined in the platform architecture.

### Key Results (SMART)
1. All ten migration scripts execute successfully against a fresh PostgreSQL 16 instance with pgvector.
2. Metric snapshot pruning deletes rows older than 90 days within one daily cycle.
3. Metric aggregation produces correct hourly rollups into metric_aggregates.
4. Semantic search returns results in under 3 seconds at 10,000 embedding scale.
5. Every mutating API call produces an audit log entry within the same transaction.
6. Embedding index (IVFFlat or HNSW) effectively accelerates vector search queries.

## 5. Market Segment(s)
### Primary segment
Platform services that need to store, query, and search across incidents, metrics, recommendations, and audit data.

### Secondary segment
DBA teams that want to query historical incident data directly via SQL or through the semantic search interface.

### Jobs to be done
1. When a detection engine evaluates metrics, I want snapshots stored and available for threshold analysis.
2. When an incident is created, I want it persisted with fingerprint, severity, and domain.
3. When a recommendation is generated, I want it linked to its incident and retrievable by similarity.
4. When an audit event happens, I want an immutable log entry with actor and payload.

### Constraints
1. Metric snapshots older than 90 days must be pruned (raw data) and rolled up to aggregates (retained 2 years).
2. Embedding index must be rebuilt after initial backfill (IVFFlat requires training data).
3. All mutating operations must produce audit log entries.

## 6. Value Proposition(s)
### Customer gains
1. Single, well-defined schema for all platform data — no cross-service consistency problems.
2. Vector search enables natural language querying of historical incidents.
3. Automated retention and pruning eliminate manual cleanup.

### Pains avoided
1. Data loss from missing retention policies.
2. Performance degradation from unbounded table growth.
3. Compliance gaps from missing audit trails.

### Differentiation
1. pgvector integration in the same database as relational data — no separate vector store.
2. Full audit logging with per-table, per-record tracking.
3. Dual retention strategy: raw snapshots (90 days) + aggregated rollups (2 years).

## 7. Solution
### 7.1 UX and Prototypes
No direct user interface. The memory layer exposes a REST API consumed by all platform services. SQL migration scripts are the source of truth for schema definition.

### 7.2 Key Features
1. Database extensions (001_extensions.sql):
   - CREATE EXTENSION IF NOT EXISTS vector.
   - CREATE EXTENSION IF NOT EXISTS pg_stat_statements.

2. Metric snapshots (002_metric_snapshots.sql):
   - Columns: snapshot_id UUID PK, db_target VARCHAR, metric_type VARCHAR with CHECK constraint covering PERFORMANCE, CAPACITY, AVAILABILITY, MAINTENANCE, COST.
   - Payload JSONB for flexible metric storage.
   - Indexes: B-tree on (db_target, metric_type, created_at DESC); optional BRIN on created_at.

3. Incidents (003_incidents.sql):
   - Columns: incident_id UUID PK, fingerprint VARCHAR(64) UNIQUE partial (only ACTIVE), severity with CHECK, domain, status (ACTIVE/RESOLVED/IGNORED), detection_count.
   - Unique partial index on (fingerprint) WHERE status = ACTIVE prevents duplicate active incidents.

4. Recommendations (004_recommendations.sql):
   - Columns: rec_id UUID PK, incident_id FK, rca_text TEXT, action_steps JSONB, confidence_score NUMERIC(4,2) with CHECK, risk_level with CHECK.
   - Foreign key cascades delete from incidents.

5. Jira mapping (005_jira_mapping.sql):
   - Columns: mapping_id UUID PK, incident_id FK, jira_ticket_key UNIQUE, sync_status (PENDING/SYNCED/FAILED).
   - Index on incident_id for lookup performance.

6. Remediation history (006_remediation_history.sql):
   - Columns: remediation_id UUID PK, rec_id FK, action_taken TEXT, executed_by VARCHAR, success BOOLEAN, result_details JSONB.

7. Configuration history (007_configuration_history.sql):
   - Columns: config_id UUID PK, db_target VARCHAR, parameter_name, old_value, new_value, changed_by.

8. Embeddings (008_embeddings.sql):
   - Columns: vector_id UUID PK, source_type (INCIDENT/RECOMMENDATION/JIRA_TICKET), source_id UUID, embedding vector(1536).
   - Unique constraint on (source_type, source_id).
   - IVFFlat index created after initial backfill (requires training data).

9. Metric aggregates (009_metric_aggregates.sql):
   - Columns: aggregate_id UUID PK, db_target, metric_type, metric_key, bucket_ts, avg/min/max_value, sample_count.
   - Unique on (db_target, metric_type, metric_key, bucket_ts).

10. Audit log (010_audit_log.sql):
    - Columns: audit_id UUID PK, table_name, record_id, action (INSERT/UPDATE/DELETE), actor, payload JSONB.
    - Index on (table_name, record_id) for record-level audit queries.

11. SQLAlchemy ORM models:
    - Mirror each migration in src/memory-service/models/.
    - Export from models/__init__.py for Alembic autogenerate support.

12. Retention service (retention.py):
    - prune_metric_snapshots: DELETE rows older than 90 days.
    - aggregate_metrics: hourly rollup into metric_aggregates.
    - prune_aggregates: DELETE buckets older than 2 years.
    - Scheduled via Celery Beat daily.

13. Embedding service (embedding_service.py):
    - embed_and_store: generate and persist embedding for source records.
    - search_similar: cosine similarity search using 1 - (embedding <=> query_vector).
    - Backfill and index rebuild tasks.

14. REST API (main.py):
    - GET /health — service health.
    - POST /snapshots — store metric snapshot.
    - GET /snapshots — query by db_target, time range.
    - POST /incidents — create incident.
    - GET /incidents — filter by status, severity, db_target.
    - GET /incidents/{incident_id} — single incident detail.
    - PATCH /incidents/{incident_id} — resolve or increment detection_count.
    - POST /recommendations — store recommendation.
    - GET /recommendations/{incident_id} — recommendations for incident.
    - POST /embeddings — store embedding.
    - POST /embeddings/search — semantic search with similarity scores.
    - All mutating endpoints write to audit_log.

### 7.3 Technology
- PostgreSQL 16+ with pgvector 0.5+.
- Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic.
- asyncpg for async database access.

### 7.4 Assumptions
1. PostgreSQL 16 is available with pgvector extension installed.
2. IVFFlat index with 100 lists is appropriate for initial embedding volume (<100K vectors).
3. Alembic is the sole migration tool — no raw SQL migrations outside its control.
4. BRIN index on metric_snapshots.created_at provides adequate pruning performance at MVP scale.

## 8. Release
### Timeline approach
Delivered as part of MVP Phase 2 (Sprints 3–4), estimated 3–4 weeks.

### Release 1 scope
- All ten migration SQL scripts.
- Alembic configuration and initial revision.
- SQLAlchemy ORM models for all tables.
- REST API endpoints for all CRUD operations.
- Retention service with daily Celery Beat scheduling.
- Embedding service with store and search operations.
- Audit logging on all mutating endpoints.

### Post-MVP scope
- HNSW index for vector search (benchmark at 100K/500K/1M embeddings).
- Read replicas for search workload isolation.
- Table partitioning by time range for metric_snapshots.
- Prometheus metrics export for monitoring.
- Point-in-time recovery testing documentation.

### Launch readiness criteria
1. All migrations apply cleanly to a fresh PostgreSQL 16 instance.
2. Seed data for all table types can be inserted and queried.
3. Retention job correctly prunes test data older than the retention window.
4. Semantic search returns correct cosine similarity ranking for test embeddings.
5. Audit log captures every INSERT, UPDATE, DELETE across tracked tables.
