---
goal: Implementation Plan — Phase 7: Semantic Search
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 2 (Memory Layer), Phase 6 (Recommendation Engine)
tags: implementation, semantic-search, pgvector, embeddings
---

# Phase 7: Semantic Search

## Overview

Enhance the memory layer's embedding service with index management, backfill tasks, natural language query support, and performance benchmarking. Enables DBAs to search historical incidents using natural language queries.

**Estimated Duration:** 2 sprints (Sprints 13–14)

**Dependencies:** Phase 2 (embeddings table, search endpoint), Phase 6 (embeddings are being stored)

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 7.1 | Implement index management | 1 hr | `src/memory-service/semantic_index.py` | ⬜ |
| 7.2 | Implement embedding backfill task | 1 hr | `src/memory-service/tasks.py` | ⬜ |
| 7.3 | Enhance search with source table JOIN | 45 min | `src/memory-service/embedding_service.py` | ⬜ |
| 7.4 | Benchmark test | 1 hr | `tests/benchmark/test_search_latency.py` | ⬜ |
| 7.5 | Integration test: semantic search | 30 min | `tests/integration/test_semantic_search.py` | ⬜ |
| 7.6 | JIRA_TICKET embedding generation | 1.5 hr | `src/memory-service/embedding_service.py` | ⬜ |

---

## Task 7.1: Index Management

**File:** `src/memory-service/semantic_index.py`

```python
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class SemanticIndexManager:
    """Manages pgvector IVFFlat index lifecycle."""
    
    IVFFLAT_INDEX_NAME = "idx_embeddings_vector"
    IVFFLAT_INDEX_DDL = (
        f"CREATE INDEX IF NOT EXISTS {IVFFLAT_INDEX_NAME} "
        f"ON embeddings USING ivfflat (embedding vector_cosine_ops) "
        f"WITH (lists = 100)"
    )
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_embedding_count(self) -> int:
        result = await self.db.execute(text("SELECT COUNT(*) FROM embeddings"))
        return result.scalar()
    
    async def index_exists(self) -> bool:
        result = await self.db.execute(text("""
            SELECT 1 FROM pg_indexes 
            WHERE indexname = :name
        """), {"name": self.IVFFLAT_INDEX_NAME})
        return result.scalar() is not None
    
    async def build_index(self):
        """Build IVFFlat index. Requires ≥ 1000 rows for training."""
        count = await self.get_embedding_count()
        if count < 1000:
            logger.info(f"Not enough embeddings for index: {count} < 1000")
            return False
        
        logger.info(f"Building IVFFlat index with {count} embeddings...")
        await self.db.execute(text(self.IVFFLAT_INDEX_DDL))
        await self.db.commit()
        logger.info("IVFFlat index created")
        return True
    
    async def rebuild_index(self):
        """Drop and recreate index. For use after large backfill."""
        if await self.index_exists():
            await self.db.execute(text(f"DROP INDEX IF EXISTS {self.IVFFLAT_INDEX_NAME}"))
            await self.db.commit()
        return await self.build_index()
```

---

## Task 7.2: Embedding Backfill

**File:** `src/memory-service/tasks.py`

```python
import logging
from celery import Celery
from httpx import AsyncClient

logger = logging.getLogger(__name__)
app = Celery("memory_service")

@app.task
def sync_missing_embeddings():
    """Find records without embeddings and generate/store them."""
    import asyncio
    asyncio.run(_sync_embeddings())

async def _sync_embeddings():
    client = AsyncClient(timeout=60)
    memory_url = "http://localhost:8005"  # Configured via env
    
    # Find incidents without embeddings
    resp = await client.get(f"{memory_url}/incidents", params={"limit": 1000})
    incidents = resp.json()
    
    for incident in incidents:
        # Check if embedding exists
        check = await client.get(f"{memory_url}/embeddings/search", json={
            "query_vector": [0.0] * 1536,  # Dummy — just checking existence
            "limit": 1,
            "source_type": "INCIDENT",
            "source_id": incident["incident_id"]
        })
        
        if len(check.json()) == 0:
            # Generate and store embedding
            # (Would call recommendation engine's embedding service)
            logger.info(f"Missing embedding for incident {incident['incident_id']}")
    
    await client.aclose()
```

---

## Task 7.3: Enhanced Search

Extend `embedding_service.py` to JOIN source tables and return full context:

```python
async def search_similar(self, query_vector: list[float], limit: int = 5, 
                          threshold: float = 0.5) -> list[dict]:
    """Enhanced search with JOIN to source tables."""
    query = text("""
        SELECT 
            e.source_type,
            e.source_id,
            e.created_at AS embedding_created_at,
            1 - (e.embedding <=> :query_vector::vector) AS similarity,
            CASE 
                WHEN e.source_type = 'INCIDENT' THEN 
                    jsonb_build_object(
                        'incident_id', i.incident_id,
                        'severity', i.severity,
                        'domain', i.domain,
                        'db_target', i.db_target,
                        'status', i.status,
                        'detected_at', i.detected_at
                    )
                WHEN e.source_type = 'RECOMMENDATION' THEN
                    jsonb_build_object(
                        'rec_id', r.rec_id,
                        'incident_id', r.incident_id,
                        'confidence', r.confidence_score,
                        'risk', r.risk_level,
                        'rca_preview', LEFT(r.rca_text, 200)
                    )
                WHEN e.source_type = 'JIRA_TICKET' THEN
                    jsonb_build_object(
                        'mapping_id', j.mapping_id,
                        'incident_id', j.incident_id,
                        'jira_ticket_key', j.jira_ticket_key,
                        'sync_status', j.sync_status
                    )
                ELSE NULL
            END AS source_data
        FROM embeddings e
        LEFT JOIN incidents i ON e.source_type = 'INCIDENT' AND e.source_id::text = i.incident_id::text
        LEFT JOIN recommendations r ON e.source_type = 'RECOMMENDATION' AND e.source_id::text = r.rec_id::text
        LEFT JOIN jira_mapping j ON e.source_type = 'JIRA_TICKET' AND e.source_id::text = j.mapping_id::text
        WHERE 1 - (e.embedding <=> :query_vector::vector) > :threshold
        ORDER BY similarity DESC
        LIMIT :limit
    """)
    result = await self.db.execute(query, {
        "query_vector": query_vector, "limit": limit, "threshold": threshold
    })
    return [dict(row) for row in result.mappings()]
```

---

## Task 7.4: Benchmark Test

**File:** `tests/benchmark/test_search_latency.py`

```python
"""Benchmark semantic search latency at various embedding counts."""
import pytest
import time
from httpx import AsyncClient

BASE_URL = "http://localhost:8005"

@pytest.mark.benchmark
@pytest.mark.parametrize("embedding_count", [100, 1000, 10000])
async def test_search_latency(embedding_count):
    async with AsyncClient(base_url=BASE_URL) as client:
        # Seed embeddings (would use test fixture)
        # ...
        
        query = [0.01] * 1536
        start = time.time()
        response = await client.post("/embeddings/search", json={
            "query_vector": query,
            "limit": 5,
            "threshold": 0.5
        })
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 3.0, f"Search took {elapsed:.2f}s at {embedding_count} embeddings"
```

## Phase 7 Completion Criteria

- [ ] IVFFlat index builds only after ≥ 1000 embeddings exist
- [ ] IVFFlat index drops and rebuilds correctly
- [ ] Backfill task finds records without embeddings (no-op if all synced)
- [ ] Backfill task generates embeddings for JIRA_TICKET source type (G2)
- [ ] Search results include source data (incident details, RCA preview)
- [ ] Search latency < 3s at 10K embeddings
- [ ] Integration test: seed 3 incidents → search returns ranked results

---

## Task 7.6: JIRA_TICKET Embedding Generation (Gap G2)

**File:** `src/memory-service/embedding_service.py`

```python
async def embed_jira_tickets(batch_size: int = 100):
    """Generate embeddings for Jira ticket summaries not yet embedded.
    
    Addresses Gap G2 from plan audit. The embeddings table supports
    source_type='JIRA_TICKET' and the search SQL already JOINs jira_mapping,
    but no code generates embeddings for ticket content.
    """
    # Find jira_mappings without embeddings
    result = await db.execute(text("""
        SELECT jm.mapping_id, jm.jira_ticket_key, jm.incident_id
        FROM jira_mapping jm
        LEFT JOIN embeddings e 
            ON e.source_type = 'JIRA_TICKET' AND e.source_id = jm.mapping_id
        WHERE e.vector_id IS NULL
        LIMIT :limit
    """), {"limit": batch_size})
    
    rows = result.fetchall()
    if not rows:
        logger.info("All Jira tickets have embeddings")
        return
    
    for row in rows:
        try:
            # Fetch ticket summary from Jira API
            ticket = await jira_client.get_issue(row.jira_ticket_key)
            summary = ticket.get("fields", {}).get("summary", "")
            text = f"Jira {row.jira_ticket_key}: {summary}"
            
            # Generate and store embedding
            embedding = await embedding_client.embed(text)
            await store_embedding("JIRA_TICKET", row.mapping_id, embedding)
            logger.info(f"Embedded Jira ticket {row.jira_ticket_key}")
        except Exception as e:
            logger.warning(f"Failed to embed {row.jira_ticket_key}: {e}")
            continue
```

**Add to `sync_missing_embeddings` Celery task:**
```python
@celery.task
def sync_missing_embeddings():
    await embed_incidents()
    await embed_recommendations()
    await embed_jira_tickets()  # NEW — Gap G2
```
