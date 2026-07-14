---
goal: Implementation Plan — Phase 4: Detection Engine
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 2 (Memory Layer), Phase 3 (MCP Integration)
tags: implementation, detection-engine, rules, ml
---

# Phase 4: Detection Engine

## Overview

Implement metric collection from MCP into the memory layer, rule-based and ML-based detection, deterministic fingerprinting, incident upsert pipeline, and Celery task chain that triggers downstream Jira + recommendation workflows.

**Estimated Duration:** 2 sprints (Sprints 7–8)

**Dependencies:** Phase 2 (memory service with /snapshots and /incidents endpoints), Phase 3 (MCP adapters)

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 4.1 | Implement MetricCollector | 1 hr | `src/detection-engine/collector.py` | ⬜ |
| 4.2 | Implement seed DetectionRules | 1 hr | `src/detection-engine/rules.py` | ⬜ |
| 4.3 | Implement RuleEvaluator | 1 hr | `src/detection-engine/rules.py` | ⬜ |
| 4.4 | Implement IsolationForestDetector | 1 hr | `src/detection-engine/ml_detector.py` | ⬜ |
| 4.5 | Implement FingerprintService | 30 min | `src/detection-engine/fingerprint.py` | ⬜ |
| 4.6 | Implement DetectionOrchestrator | 1.5 hr | `src/detection-engine/evaluator.py` | ⬜ |
| 4.7 | Implement Celery app and tasks | 1 hr | `src/detection-engine/celery_app.py`, `tasks.py` | ⬜ |
| 4.8 | Implement REST API (main.py) | 30 min | `src/detection-engine/main.py` | ⬜ |
| 4.9 | Unit tests: fingerprint, rules, ML | 1 hr | `tests/unit/detection-engine/` | ⬜ |
| 4.10 | Integration test: detection pipeline | 1 hr | `tests/integration/test_detection_pipeline.py` | ⬜ |
| 4.11 | Integration test: dedup E2E | 1 hr | `tests/integration/test_dedup_e2e.py` | ⬜ |

---

## Task 4.1: MetricCollector

**File:** `src/detection-engine/collector.py`

```python
import asyncio
import logging
from httpx import AsyncClient

logger = logging.getLogger(__name__)

class MetricCollector:
    """Collects database metrics from MCP layer and stores in memory service."""
    
    def __init__(self, mcp_url: str, memory_url: str, db_targets: list[str]):
        self.mcp_url = mcp_url
        self.memory_url = memory_url
        self.db_targets = db_targets
        self.client = AsyncClient(timeout=30)
    
    async def collect_cycle(self) -> dict:
        """Iterate all targets and collect metrics."""
        results = {"success": 0, "failed": 0, "targets": []}
        for target in self.db_targets:
            try:
                result = await self.collect_single(target)
                results["success"] += 1
                results["targets"].append(result)
            except Exception as e:
                logger.error(f"Collection failed for {target}: {e}")
                results["failed"] += 1
        return results
    
    async def collect_single(self, target: str) -> dict:
        """Collect and store metrics for one target."""
        # Call MCP adapters
        db_metrics = await self._get(f"{self.mcp_url}/tools/get_database_metrics", {"db_name": target})
        host_metrics = await self._get(f"{self.mcp_url}/tools/get_host_metrics", {"db_name": target})
        conn_metrics = await self._get(f"{self.mcp_url}/tools/get_connection_metrics", {"db_name": target})
        
        # Store each metric type
        for metric_type, payload in [("PERFORMANCE", db_metrics), ("CAPACITY", {}), ("AVAILABILITY", {})]:
            resp = await self.client.post(
                f"{self.memory_url}/snapshots",
                json={"db_target": target, "metric_type": metric_type, "payload": payload}
            )
            resp.raise_for_status()
        
        return {"target": target, "metric_types": ["PERFORMANCE", "CAPACITY", "AVAILABILITY"]}
    
    async def _get(self, url: str, params: dict) -> dict:
        resp = await self.client.post(url, json=params)
        resp.raise_for_status()
        return resp.json()
```

---

## Task 4.2: Seed DetectionRules

**File:** `src/detection-engine/rules.py`

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class DetectionRule:
    name: str
    domain: Literal["PERFORMANCE", "CAPACITY", "AVAILABILITY", "MAINTENANCE", "COST"]
    metric_type: str
    error_code: str
    threshold: float
    operator: Literal["gt", "gte", "lt", "lte", "eq"]
    duration_minutes: int
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]

SEED_RULES = [
    DetectionRule("high_cpu", "PERFORMANCE", "cpu_usage", "high_cpu", 90, "gt", 10, "CRITICAL"),
    DetectionRule("high_iops", "PERFORMANCE", "iops_pct", "high_iops", 95, "gt", 5, "HIGH"),
    DetectionRule("slow_queries", "PERFORMANCE", "slow_query_count", "slow_queries", 50, "gt", 5, "HIGH"),
    DetectionRule("blocking_sessions", "PERFORMANCE", "blocking_count", "blocking_sessions", 10, "gt", 2, "HIGH"),
    DetectionRule("deadlocks", "PERFORMANCE", "deadlock_rate", "deadlocks", 5, "gt", 1, "CRITICAL"),
    DetectionRule("storage_critical", "CAPACITY", "storage_pct", "storage_critical", 95, "gte", 0, "CRITICAL"),
    DetectionRule("storage_warning", "CAPACITY", "storage_pct", "storage_warning", 85, "gte", 0, "HIGH"),
    DetectionRule("connections_critical", "CAPACITY", "connection_pct", "connections_critical", 95, "gte", 0, "CRITICAL"),
    DetectionRule("replication_lag", "AVAILABILITY", "repl_lag_ms", "replication_lag", 30000, "gt", 2, "HIGH"),
    DetectionRule("backup_stale", "AVAILABILITY", "backup_age_hours", "backup_stale", 48, "gt", 0, "HIGH"),
    DetectionRule("stale_statistics", "MAINTENANCE", "stats_age_days", "stale_statistics", 7, "gt", 0, "MEDIUM"),
]
```

---

## Task 4.3: RuleEvaluator

**File:** `src/detection-engine/rules.py` (continued)

```python
@dataclass
class Candidate:
    domain: str
    metric_type: str
    error_code: str
    severity: str
    db_target: str
    current_value: float
    threshold: float

class RuleEvaluator:
    def evaluate(self, snapshots: list[dict], rules: list[DetectionRule]) -> list[Candidate]:
        candidates = []
        for rule in rules:
            # Filter snapshots by target and metric type
            relevant = [
                s for s in snapshots
                if s.get("payload", {}).get(rule.metric_type.split("_")[0]) is not None
            ]
            if not relevant:
                continue
            
            # Check most recent value against threshold
            latest = relevant[-1]
            value = self._get_metric_value(latest["payload"], rule.metric_type)
            if value is None:
                continue
            
            if self._compare(value, rule.threshold, rule.operator):
                candidates.append(Candidate(
                    domain=rule.domain,
                    metric_type=rule.metric_type,
                    error_code=rule.error_code,
                    severity=rule.severity,
                    db_target=latest.get("db_target", "unknown"),
                    current_value=value,
                    threshold=rule.threshold
                ))
        
        return candidates
    
    def _get_metric_value(self, payload: dict, metric_type: str) -> float | None:
        """Extract numeric value from payload based on metric type pattern."""
        # Simple key lookup — extend per metric type
        for key in payload:
            if metric_type.split("_")[0] in key.lower():
                try:
                    return float(payload[key])
                except (ValueError, TypeError):
                    return None
        return None
    
    def _compare(self, value: float, threshold: float, operator: str) -> bool:
        ops = {
            "gt": lambda v, t: v > t,
            "gte": lambda v, t: v >= t,
            "lt": lambda v, t: v < t,
            "lte": lambda v, t: v <= t,
            "eq": lambda v, t: v == t,
        }
        return ops.get(operator, lambda v, t: False)(value, threshold)
```

---

## Task 4.4: IsolationForestDetector

**File:** `src/detection-engine/ml_detector.py`

```python
import logging
import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib

logger = logging.getLogger(__name__)

class IsolationForestDetector:
    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.model = None
        self.is_trained = False
    
    def train_baseline(self, metric_data: pd.DataFrame):
        """Fit isolation forest on historical data."""
        if len(metric_data) < 10:
            logger.warning(f"Insufficient data for training: {len(metric_data)} rows")
            return
        
        # Extract numeric features from JSON payload
        features = self._extract_features(metric_data)
        if features.empty:
            logger.warning("No numeric features extracted for training")
            return
        
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_estimators=100
        )
        self.model.fit(features)
        self.is_trained = True
        logger.info(f"Model trained on {len(features)} samples")
    
    def detect_anomalies(self, current_data: pd.DataFrame) -> list[dict]:
        """Detect anomalies in current metrics."""
        if not self.is_trained or self.model is None:
            logger.info("Model not trained — skipping ML detection")
            return []
        
        features = self._extract_features(current_data)
        if features.empty:
            return []
        
        scores = self.model.decision_function(features)
        predictions = self.model.predict(features)
        
        anomalies = []
        for idx, (score, pred) in enumerate(zip(scores, predictions)):
            if pred == -1:  # Anomaly
                anomalies.append({
                    "index": idx,
                    "anomaly_score": float(score),
                    "severity": "HIGH" if score < -0.3 else "MEDIUM",
                    "features": features.iloc[idx].to_dict()
                })
        
        return anomalies
    
    def _extract_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract numeric columns from payload JSONB."""
        rows = []
        for _, row in data.iterrows():
            payload = row.get("payload", {})
            if isinstance(payload, dict):
                numeric = {k: v for k, v in payload.items() 
                          if isinstance(v, (int, float))}
                if numeric:
                    rows.append(numeric)
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    def save_model(self, path: str):
        if self.model:
            joblib.dump(self.model, path)
    
    def load_model(self, path: str):
        self.model = joblib.load(path)
        self.is_trained = True
```

---

## Task 4.5: FingerprintService

**File:** `src/detection-engine/fingerprint.py`

```python
import hashlib
from datetime import datetime

def generate_fingerprint(db_target: str, error_code_or_metric_type: str, timestamp: datetime) -> str:
    """Deterministic SHA-256 fingerprint with 4-hour window coalescing."""
    date_bucket = timestamp.strftime('%Y-%m-%d')
    hour_window = (timestamp.hour // 4) * 4
    raw = f"{db_target}:{error_code_or_metric_type}:{date_bucket}-{hour_window:02d}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

---

## Task 4.6: DetectionOrchestrator

**File:** `src/detection-engine/evaluator.py`

```python
import logging
from datetime import datetime, timedelta
from httpx import AsyncClient

logger = logging.getLogger(__name__)

class DetectionOrchestrator:
    def __init__(self, memory_url: str, rule_evaluator, ml_detector, celery_app):
        self.memory_url = memory_url
        self.rule_evaluator = rule_evaluator
        self.ml_detector = ml_detector
        self.celery_app = celery_app
        self.client = AsyncClient(timeout=30)
    
    async def evaluate_cycle(self) -> dict:
        """Main evaluation cycle: fetch → rules + ML → fingerprint → upsert."""
        start = datetime.utcnow()
        
        # 1. Fetch recent snapshots
        snapshots = await self._fetch_recent_snapshots()
        
        # 2. Run rules
        rule_candidates = self.rule_evaluator.evaluate(snapshots, SEED_RULES)
        
        # 3. Run ML detection
        ml_candidates = self.ml_detector.detect_anomalies(pd.DataFrame(snapshots))
        
        # 4. Fingerprint and upsert
        incidents_created = 0
        incidents_updated = 0
        
        for candidate in rule_candidates:
            fp = generate_fingerprint(candidate.db_target, candidate.error_code, start)
            result = await self._upsert_incident(fp, candidate)
            if result.get("created"):
                incidents_created += 1
                self.celery_app.send_task("process_new_incident", args=[result["incident_id"]])
            else:
                incidents_updated += 1
        
        return {
            "incidents_created": incidents_created,
            "incidents_updated": incidents_updated,
            "rules_evaluated": len(SEED_RULES),
            "ml_evaluated": self.ml_detector.is_trained,
            "duration_ms": int((datetime.utcnow() - start).total_seconds() * 1000)
        }
    
    async def _fetch_recent_snapshots(self, minutes: int = 5) -> list[dict]:
        resp = await self.client.get(
            f"{self.memory_url}/snapshots",
            params={"from": (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()}
        )
        return resp.json() if resp.status_code == 200 else []
    
    async def _upsert_incident(self, fingerprint: str, candidate) -> dict:
        # Check for existing active incident
        resp = await self.client.get(
            f"{self.memory_url}/incidents",
            params={"fingerprint": fingerprint, "status": "ACTIVE"}
        )
        existing = resp.json() if resp.status_code == 200 else []
        
        if existing and len(existing) > 0:
            # Update existing
            inc = existing[0]
            await self.client.patch(
                f"{self.memory_url}/incidents/{inc['incident_id']}",
                json={"detection_count": inc.get("detection_count", 1) + 1}
            )
            return {"incident_id": inc["incident_id"], "created": False}
        else:
            # Create new
            resp = await self.client.post(f"{self.memory_url}/incidents", json={
                "fingerprint": fingerprint,
                "error_code_or_metric_type": candidate.error_code,
                "severity": candidate.severity,
                "domain": candidate.domain,
                "db_target": candidate.db_target
            })
            data = resp.json() if resp.status_code == 201 else {}
            return {"incident_id": data.get("incident_id"), "created": resp.status_code == 201}
```

---

## Task 4.7: Celery App and Tasks

**File:** `src/detection-engine/celery_app.py`
```python
from celery import Celery

app = Celery("detection_engine")
app.config_from_object({
    "broker_url": "redis://redis:6379/0",
    "result_backend": "redis://redis:6379/1",
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "task_track_started": True,
    "worker_prefetch_multiplier": 1,
})

app.conf.beat_schedule = {
    "collect-metrics": {
        "task": "detection_engine.tasks.collect_metrics",
        "schedule": 60.0,
    },
    "evaluate-cycle": {
        "task": "detection_engine.tasks.evaluate_cycle",
        "schedule": 60.0,
    },
    "train-ml-models": {
        "task": "detection_engine.tasks.train_ml_models",
        "schedule": {"hour": 2, "minute": 0},  # Daily 02:00 UTC
    },
}
```

**File:** `src/detection-engine/tasks.py`
```python
from .celery_app import app

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_new_incident(self, incident_id: str):
    """Triggers downstream Jira sync and recommendation generation."""
    # Chain: jira_sync → recommendation_generation
    chain = (
        app.signature("jira_integration.tasks.process_jira_for_incident", args=[incident_id]),
        app.signature("recommendation_engine.tasks.generate_recommendation", args=[incident_id]),
    )
    return chain()

@app.task
def collect_metrics():
    from .collector import MetricCollector
    import os
    collector = MetricCollector(
        mcp_url=os.getenv("MCP_LAYER_URL", "http://mcp-layer:8004"),
        memory_url=os.getenv("MEMORY_SERVICE_URL", "http://memory-service:8005"),
        db_targets=os.getenv("DB_TARGETS", "db_primary_sql2019").split(",")
    )
    return collector.collect_cycle()

@app.task
def evaluate_cycle():
    from .evaluator import DetectionOrchestrator
    from .rules import RuleEvaluator
    from .ml_detector import IsolationForestDetector
    import os
    
    orchestrator = DetectionOrchestrator(
        memory_url=os.getenv("MEMORY_SERVICE_URL"),
        rule_evaluator=RuleEvaluator(),
        ml_detector=IsolationForestDetector(contamination=float(os.getenv("ML_CONTAMINATION", "0.1"))),
        celery_app=app
    )
    return orchestrator.evaluate_cycle()

@app.task
def train_ml_models():
    from .ml_detector import IsolationForestDetector
    import os
    detector = IsolationForestDetector()
    # Fetch 7 days of data and train
    # ... (implementation)
```

---

## Task 4.8: REST API (main.py)

**File:** `src/detection-engine/main.py`

```python
from fastapi import FastAPI, HTTPException
from .rules import SEED_RULES, DetectionRule
import os

app = FastAPI(title="AI DBA Copilot - Detection Engine", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "detection-engine"}

@app.post("/evaluate")
async def trigger_evaluation():
    """Manually trigger evaluation cycle."""
    from .evaluator import DetectionOrchestrator
    from .rules import RuleEvaluator
    from .ml_detector import IsolationForestDetector
    from .celery_app import app as celery_app
    
    orchestrator = DetectionOrchestrator(
        memory_url=os.getenv("MEMORY_SERVICE_URL", "http://memory-service:8005"),
        rule_evaluator=RuleEvaluator(),
        ml_detector=IsolationForestDetector(),
        celery_app=celery_app
    )
    return await orchestrator.evaluate_cycle()

@app.get("/rules")
async def list_rules():
    return [{"name": r.name, "domain": r.domain, "metric_type": r.metric_type,
             "error_code": r.error_code, "threshold": r.threshold,
             "operator": r.operator, "severity": r.severity}
            for r in SEED_RULES]

@app.post("/rules")
async def create_rule(rule: DetectionRule):
    SEED_RULES.append(rule)
    return {"status": "created", "name": rule.name}
```

## Phase 4 Completion Criteria

- [ ] MetricCollector polls MCP adapters and stores snapshots in memory service
- [ ] All 12 seed rules are defined covering 5 domains
- [ ] RuleEvaluator correctly identifies threshold breaches
- [ ] IsolationForestDetector trains async and detects anomalies
- [ ] FingerprintService produces deterministic SHA-256 with 4-hour window
- [ ] DetectionOrchestrator upserts incidents correctly (new → POST, existing → PATCH)
- [ ] Celery task chain triggers downstream Jira + recommendation generation
- [ ] Unit tests pass for fingerprint, rules, ML detector
- [ ] Integration test: seed snapshots → evaluate → incident created
- [ ] Integration test: same fingerprint within window → detection_count incremented, not duplicated
