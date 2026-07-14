---
goal: Implementation Plan — Phase 6: Recommendation Engine
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 2 (Memory Layer), Phase 3 (MCP Integration), Phase 4 (Detection Engine)
tags: implementation, recommendation-engine, rag, llm
---

# Phase 6: Recommendation Engine

## Overview

Implement the RAG-powered RCA generation pipeline: context assembly from incident + metrics, semantic retrieval of similar past incidents, LLM-based structured JSON generation with confidence scoring, remediation action classification, and embedding storage for future retrieval.

**Estimated Duration:** 2 sprints (Sprints 11–12)

**Dependencies:** Phase 2 (embeddings table, /embeddings/search), Phase 3 (MCP query plan adapter), Phase 4 (process_new_incident task chain)

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 6.1 | Implement LLMClient | 1 hr | `src/recommendation-engine/llm_client.py` | ⬜ |
| 6.2 | Implement EmbeddingClient | 45 min | `src/recommendation-engine/embedding_client.py` | ⬜ |
| 6.3 | Implement ContextAssembler | 1 hr | `src/recommendation-engine/context_assembler.py` | ⬜ |
| 6.4 | Implement RAGRetriever | 45 min | `src/recommendation-engine/rag_retriever.py` | ⬜ |
| 6.5 | Implement PromptTemplates | 1 hr | `src/recommendation-engine/prompt_templates.py` | ⬜ |
| 6.6 | Implement Generator + Validator | 1.5 hr | `src/recommendation-engine/generator.py` | ⬜ |
| 6.7 | Implement RemediationClassifier | 30 min | `src/recommendation-engine/remediation_classifier.py` | ⬜ |
| 6.8 | Implement Celery tasks | 30 min | `src/recommendation-engine/tasks.py` | ⬜ |
| 6.9 | Implement REST API | 30 min | `src/recommendation-engine/main.py` | ⬜ |
| 6.10 | Unit tests | 1.5 hr | `tests/unit/recommendation-engine/` | ⬜ |
| 6.11 | Integration test: full pipeline | 1 hr | `tests/integration/test_recommendation_pipeline.py` | ⬜ |

---

## Task 6.1: LLMClient

**File:** `src/recommendation-engine/llm_client.py`

```python
import json
import logging
import asyncio
from openai import AsyncOpenAI, APIError, Timeout

logger = logging.getLogger(__name__)

class LLMClient:
    """OpenAI/Azure OpenAI client with structured JSON output enforcement."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o", 
                 temperature: float = 0.1, max_retries: int = 3,
                 endpoint: str = None):
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        
        if endpoint:
            self.client = AsyncOpenAI(api_key=api_key, base_url=endpoint)
        else:
            self.client = AsyncOpenAI(api_key=api_key)
    
    async def generate_structured(self, system_prompt: str, user_prompt: str, 
                                   json_schema: dict = None) -> dict:
        """Generate structured JSON output with schema validation."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt + (
                            f"\n\nPrevious error: {last_error}. Please ensure valid JSON."
                            if last_error else ""
                        )}
                    ]
                )
                result = json.loads(response.choices[0].message.content)
                return result
            except (json.JSONDecodeError, APIError, Timeout) as e:
                last_error = str(e)
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
```

---

## Task 6.2: EmbeddingClient

**File:** `src/recommendation-engine/embedding_client.py`

```python
"""Embedding client for text-embedding-ada-002."""

import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Generates 1536-dimensional embeddings via OpenAI API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-ada-002",
        dimensions: int = 1536,
        endpoint: str | None = None,
    ):
        self.model = model
        self.dimensions = dimensions
        if endpoint:
            self.client = AsyncOpenAI(api_key=api_key, base_url=endpoint)
        else:
            self.client = AsyncOpenAI(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        """Generate a single embedding vector."""
        response = await self.client.embeddings.create(
            model=self.model, input=text
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embedding with per-item error isolation.

        Failed items return a zero-vector so callers can handle them gracefully.
        """
        results: list[list[float]] = []
        for text in texts:
            try:
                results.append(await self.embed(text))
            except Exception:
                logger.warning("Embedding failed for text fragment", exc_info=True)
                results.append([0.0] * self.dimensions)
        return results
```

---

## Task 6.3–6.4: RAG Pipeline Components

**ContextAssembler** (`context_assembler.py`):
- Fetches incident from memory service
- Fetches metric snapshots ±30 min around detection
- Fetches query plan via MCP (if PERFORMANCE domain)
- Returns assembled context dict

**RAGRetriever** (`rag_retriever.py`):
```python
class RAGRetriever:
    async def retrieve_similar(self, incident_text: str, top_k: int = 3) -> list[dict]:
        # Embed the incident text
        query_vector = await self.embedding_client.embed(incident_text)
        # Search memory service
        response = await self.client.post(
            f"{self.memory_url}/embeddings/search",
            json={"query_vector": query_vector, "limit": top_k, "threshold": 0.5}
        )
        return response.json()
```

---

## Task 6.5: PromptTemplates

**File:** `src/recommendation-engine/prompt_templates.py`

```python
SYSTEM_PROMPT = """You are an expert DBA assistant for AI DBA Copilot. Analyze database
incidents and provide structured Root Cause Analysis with remediation steps.

Rules:
1. Output ONLY valid JSON. No markdown, no code fences, no explanatory text.
2. Base your analysis on the provided context and similar past incidents.
3. Confidence scores: 0.95+ only for definitively known patterns with exact past match.
4. Risk: LOW (safe/reversible), MEDIUM (schema changes with rollback), HIGH (destructive).
5. Tag actions as BLOCKED if they involve DROP or TRUNCATE.
6. Tag actions as AUTO if they are non-destructive maintenance (ANALYZE, UPDATE STATISTICS).

Output schema:
{
  "rca": "string - detailed root cause analysis",
  "actions": [{"step": "string", "command": "string", "type": "AUTO|APPROVAL_REQUIRED|BLOCKED"}],
  "risk": "LOW|MEDIUM|HIGH",
  "confidence_score": 0.0-1.0
}"""

def build_user_prompt(incident_context: dict, past_incidents: list[dict]) -> str:
    """Build the user message with context and similar past incidents."""
    sections = [
        "# Current Incident",
        f"Domain: {incident_context.get('domain')}",
        f"DB Target: {incident_context.get('db_target')}",
        f"Error: {incident_context.get('error_code_or_metric_type')}",
        f"Severity: {incident_context.get('severity')}",
        "",
        "## Recent Metrics",
        json.dumps(incident_context.get('metrics_window', [])[:5], indent=2),
    ]
    
    if past_incidents:
        sections.append("\n## Similar Past Incidents")
        for i, inc in enumerate(past_incidents[:3], 1):
            sections.append(f"\n### Past Incident {i}")
            sections.append(f"RCA: {inc.get('rca_text', 'N/A')[:500]}")
    
    return "\n".join(sections)
```

---

## Task 6.6: Generator

**File:** `src/recommendation-engine/generator.py`

```python
import logging
from httpx import AsyncClient

logger = logging.getLogger(__name__)

class RecommendationGenerator:
    """Full RCA generation pipeline."""
    
    def __init__(self, llm_client, embedding_client, rag_retriever, context_assembler, classifier,
                 memory_url: str):
        self.llm = llm_client
        self.embedding_client = embedding_client
        self.rag = rag_retriever
        self.assembler = context_assembler
        self.classifier = classifier
        self.memory_url = memory_url
        self.client = AsyncClient(timeout=60)
    
    async def generate(self, incident_id: str) -> dict:
        """Generate and persist recommendation for an incident."""
        # 1. Assemble context
        context = await self.assembler.assemble(incident_id)
        
        # 2. Retrieve similar past incidents
        incident_text = f"{context.get('domain')}: {context.get('error_code_or_metric_type')}"
        past = await self.rag.retrieve_similar(incident_text)
        
        # 3. Build prompt and call LLM
        user_prompt = build_user_prompt(context, past)
        result = await self.llm.generate_structured(SYSTEM_PROMPT, user_prompt)
        
        # 4. Validate result
        if not self._validate(result):
            logger.error("LLM output schema validation failed")
            result = self._fallback_response()
        
        # 5. Apply confidence gate
        confidence = result.get("confidence_score", 0.0)
        requires_human = confidence < 0.60
        
        # 6. Classify action types
        actions = self.classifier.classify(result.get("actions", []))
        
        # 7. Store recommendation
        rec = await self.client.post(f"{self.memory_url}/recommendations", json={
            "incident_id": incident_id,
            "rca_text": result["rca"],
            "action_steps": actions,
            "confidence_score": confidence,
            "risk_level": result.get("risk", "MEDIUM"),
            "requires_human_validation": requires_human
        })
        rec_data = rec.json()
        
        # 8. Store embedding
        await self._store_embedding("RECOMMENDATION", rec_data["rec_id"], result["rca"])
        
        return {
            "rec_id": rec_data["rec_id"],
            "confidence_score": confidence,
            "risk_level": result.get("risk"),
            "requires_human_validation": requires_human
        }
    
    def _validate(self, result: dict) -> bool:
        required = ["rca", "actions", "risk", "confidence_score"]
        if not all(k in result for k in required):
            return False
        if not isinstance(result["actions"], list) or len(result["actions"]) == 0:
            return False
        if result["risk"] not in ("LOW", "MEDIUM", "HIGH"):
            return False
        if not 0.0 <= result["confidence_score"] <= 1.0:
            return False
        return True
    
    def _fallback_response(self) -> dict:
        return {
            "rca": "Automated RCA generation failed. Manual investigation required.",
            "actions": [{"step": "Investigate manually", "command": "", "type": "APPROVAL_REQUIRED"}],
            "risk": "HIGH",
            "confidence_score": 0.0
        }
    
    async def _store_embedding(self, source_type: str, source_id: str, text: str):
        embedding = await self.embedding_client.embed(text)
        await self.client.post(f"{self.memory_url}/embeddings", json={
            "source_type": source_type,
            "source_id": source_id,
            "embedding": embedding
        })
```

---

## Task 6.7: RemediationClassifier

**File:** `src/recommendation-engine/remediation_classifier.py`

```python
import re

CLASSIFICATION_RULES = [
    (r'^\s*ANALYZE\s+', 'AUTO'),
    (r'^\s*UPDATE\s+STATISTICS\s+', 'AUTO'),
    (r'^\s*CREATE\s+(INDEX|STATISTICS)\s+', 'APPROVAL_REQUIRED'),
    (r'^\s*ALTER\s+(DATABASE|TABLE|INDEX|PROCEDURE)', 'APPROVAL_REQUIRED'),
    (r'^\s*KILL\s+\d+', 'APPROVAL_REQUIRED'),
    (r'^\s*DBCC\s+', 'APPROVAL_REQUIRED'),
    (r'^\s*EXEC\s+', 'APPROVAL_REQUIRED'),
    (r'^\s*DROP\s+(TABLE|DATABASE|VIEW|PROCEDURE|FUNCTION)', 'BLOCKED'),
    (r'^\s*TRUNCATE\s+TABLE\s+', 'BLOCKED'),
    (r'^\s*DELETE\s+FROM\s+', 'BLOCKED'),
]

class RemediationClassifier:
    @staticmethod
    def classify(actions: list[dict]) -> list[dict]:
        """Tag each action with type based on command pattern."""
        tagged = []
        for action in actions:
            command = action.get("command", "")
            action_type = 'APPROVAL_REQUIRED'  # Conservative default
            for pattern, classification in CLASSIFICATION_RULES:
                if re.match(pattern, command.strip(), re.IGNORECASE):
                    action_type = classification
                    break
            tagged.append({**action, "type": action_type})
        return tagged
```

---

## Task 6.8–6.11

Standard Celery tasks, REST API (port 8002), unit tests for RAG retriever, context assembler, generator confidence gating, and integration test for the full pipeline.

## Phase 6 Completion Criteria

- [ ] LLMClient generates structured JSON output with retry on schema failure
- [ ] EmbeddingClient returns 1536-dim vectors
- [ ] ContextAssembler fetches incident + metrics + query plan (PERFORMANCE domain only)
- [ ] RAGRetriever returns top-3 similar past incidents ranked by cosine similarity
- [ ] Generator: confidence < 0.60 → requires_human_validation = True
- [ ] Generator: confidence ≥ 0.60 → requires_human_validation = False
- [ ] RemediationClassifier correctly tags ANALYZE→AUTO, DROP→BLOCKED, unknown→APPROVAL_REQUIRED
- [ ] Recommendation + embedding persisted to memory service
- [ ] Unit tests pass for RAG, context assembly, generator confidence gating
- [ ] Integration test: incident → recommendation generated → stored → retrievable via search
