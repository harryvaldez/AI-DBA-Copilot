---
goal: Implementation Plan — Phase 8: Predictive Analytics
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 2 (Memory Layer), Phase 4 (Detection Engine)
tags: implementation, predictive-analytics, forecasting
---

# Phase 8: Predictive Analytics

## Overview

Implement forecasting models for storage/connection exhaustion and cost anomaly detection. Uses linear regression on metric_aggregates data to project resource exhaustion 14+ days in advance, and isolation forest for daily cost spike detection.

**Estimated Duration:** 2 sprints (Sprints 15–16)

**Dependencies:** Phase 2 (metric_aggregates table populated), Phase 4 (incident creation pipeline)

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 8.1 | Implement StorageForecaster | 1 hr | `src/predictive-analytics/forecaster.py` | ⬜ |
| 8.2 | Implement ConnectionForecaster | 30 min | `src/predictive-analytics/connection_forecaster.py` | ⬜ |
| 8.3 | Implement ReplicationForecaster | 30 min | `src/predictive-analytics/replication_forecaster.py` | ⬜ |
| 8.4 | Implement CostAnomalyDetector | 1 hr | `src/predictive-analytics/cost_anomaly.py` | ⬜ |
| 8.5 | Implement ForecastOrchestrator | 1 hr | `src/predictive-analytics/orchestrator.py` | ⬜ |
| 8.6 | Implement Scheduler + Celery | 30 min | `src/predictive-analytics/scheduler.py` | ⬜ |
| 8.7 | Implement REST API | 30 min | `src/predictive-analytics/main.py` | ⬜ |
| 8.8 | Unit tests | 1 hr | `tests/unit/predictive-analytics/` | ⬜ |
| 8.9 | Integration test | 1 hr | `tests/integration/test_predictive_pipeline.py` | ⬜ |

---

## Task 8.1: StorageForecaster

**File:** `src/predictive-analytics/forecaster.py`

```python
import numpy as np
from sklearn.linear_model import LinearRegression
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class ForecastResult:
    db_target: str
    metric_key: str
    days_until_threshold: float  # -1 if no breach projected
    estimated_breach_date: datetime | None
    current_value: float
    threshold_value: float
    trend_slope: float
    r_squared: float
    confidence_interval: tuple[float, float]
    data_points: int

class StorageForecaster:
    """Linear regression forecast for storage exhaustion."""
    
    THRESHOLD_PCT = 95.0
    MIN_DATA_POINTS = 7
    
    def forecast(self, db_target: str, metric_data: list[dict]) -> ForecastResult:
        """Project days until storage reaches threshold."""
        if len(metric_data) < self.MIN_DATA_POINTS:
            return self._insufficient_data(db_target)
        
        # Extract (day_index, value) pairs
        values = []
        for i, point in enumerate(metric_data):
            payload = point.get("payload", {})
            pct = payload.get("storage_pct") or payload.get("value")
            if pct is not None:
                values.append((i, float(pct)))
        
        if len(values) < self.MIN_DATA_POINTS:
            return self._insufficient_data(db_target)
        
        X = np.array([v[0] for v in values]).reshape(-1, 1)
        y = np.array([v[1] for v in values])
        
        # Fit linear regression
        model = LinearRegression()
        model.fit(X, y)
        slope = model.coef_[0]
        intercept = model.intercept_
        
        # R-squared
        y_pred = model.predict(X)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Projection
        current_value = y[-1]
        if slope <= 0.001:  # Stable or shrinking
            return ForecastResult(
                db_target=db_target, metric_key="storage_pct",
                days_until_threshold=-1, estimated_breach_date=None,
                current_value=current_value, threshold_value=self.THRESHOLD_PCT,
                trend_slope=slope, r_squared=r_squared,
                confidence_interval=(0, 0), data_points=len(values)
            )
        
        days_until = (self.THRESHOLD_PCT - current_value) / slope
        breach_date = datetime.utcnow() + timedelta(days=days_until) if days_until > 0 else None
        
        # Simple confidence interval (±20% for MVP)
        ci_margin = days_until * 0.2
        
        return ForecastResult(
            db_target=db_target, metric_key="storage_pct",
            days_until_threshold=max(days_until, -1),
            estimated_breach_date=breach_date,
            current_value=current_value, threshold_value=self.THRESHOLD_PCT,
            trend_slope=slope, r_squared=r_squared,
            confidence_interval=(days_until - ci_margin, days_until + ci_margin),
            data_points=len(values)
        )
    
    def _insufficient_data(self, db_target: str) -> ForecastResult:
        return ForecastResult(
            db_target=db_target, metric_key="storage_pct",
            days_until_threshold=-1, estimated_breach_date=None,
            current_value=0, threshold_value=self.THRESHOLD_PCT,
            trend_slope=0, r_squared=0,
            confidence_interval=(0, 0), data_points=0
        )
```

---

## Tasks 8.2–8.3: ConnectionForecaster, ReplicationForecaster

Both follow the same pattern as StorageForecaster with different metric keys and thresholds:
- **ConnectionForecaster**: `connection_pct`, threshold 95%
- **ReplicationForecaster**: `repl_lag_ms`, threshold 30000ms

---

## Task 8.4: CostAnomalyDetector

**File:** `src/predictive-analytics/cost_anomaly.py`

```python
import numpy as np
from sklearn.ensemble import IsolationForest

class CostAnomalyDetector:
    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination
        self.model = IsolationForest(contamination=contamination, random_state=42)
    
    def detect(self, daily_costs: list[dict]) -> list[dict]:
        """Detect cost anomalies in daily spend data."""
        if len(daily_costs) < 14:
            return []
        
        values = np.array([c.get("daily_cost", 0) for c in daily_costs]).reshape(-1, 1)
        self.model.fit(values)
        
        scores = self.model.decision_function(values)
        predictions = self.model.predict(values)
        
        anomalies = []
        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred == -1:  # Anomaly
                cost = float(values[i][0])
                baseline = float(np.median(values))
                deviation_pct = ((cost - baseline) / baseline) * 100
                anomalies.append({
                    "date": daily_costs[i].get("date"),
                    "daily_cost": cost,
                    "baseline_cost": round(baseline, 2),
                    "deviation_pct": round(deviation_pct, 1),
                    "severity": "HIGH" if deviation_pct > 50 else "MEDIUM"
                })
        
        return anomalies
```

---

## Task 8.5: ForecastOrchestrator

**File:** `src/predictive-analytics/orchestrator.py`

```python
import logging
from datetime import datetime
from httpx import AsyncClient

logger = logging.getLogger(__name__)

class ForecastOrchestrator:
    def __init__(self, memory_url: str, storage_forecaster, connection_forecaster,
                 replication_forecaster, cost_detector):
        self.memory_url = memory_url
        self.storage = storage_forecaster
        self.connections = connection_forecaster
        self.replication = replication_forecaster
        self.cost = cost_detector
        self.client = AsyncClient(timeout=30)
    
    async def run_forecast_cycle(self, db_targets: list[str]) -> dict:
        """Run all forecasters for all targets."""
        results = {"targets_checked": 0, "incidents_created": 0, "duration_ms": 0}
        start = datetime.utcnow()
        
        for target in db_targets:
            results["targets_checked"] += 1
            
            # Fetch metric data
            data = await self._fetch_metrics(target)
            
            # Run forecasters
            forecasts = [
                ("predictive_storage_exhaustion", await self.storage.forecast(target, data.get("storage", []))),
                ("predictive_connection_exhaustion", await self.connections.forecast(target, data.get("connections", []))),
                ("predictive_replication_breach", await self.replication.forecast(target, data.get("replication", []))),
            ]
            
            # Create incidents for forecasts < 14 days
            for error_code, forecast in forecasts:
                if 0 < forecast.days_until_threshold < 14:
                    await self._create_predictive_incident(target, error_code, forecast)
                    results["incidents_created"] += 1
        
        results["duration_ms"] = int((datetime.utcnow() - start).total_seconds() * 1000)
        return results
    
    async def _create_predictive_incident(self, target: str, error_code: str, forecast):
        """Create predictive incident in memory service."""
        fingerprint = self._predictive_fingerprint(target, error_code)
        await self.client.post(f"{self.memory_url}/incidents", json={
            "fingerprint": fingerprint,
            "error_code_or_metric_type": error_code,
            "severity": "HIGH" if forecast.days_until_threshold < 7 else "MEDIUM",
            "domain": "CAPACITY",
            "db_target": target
        })
    
    def _predictive_fingerprint(self, target: str, error_code: str) -> str:
        import hashlib
        raw = f"{target}:{error_code}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        return hashlib.sha256(raw.encode()).hexdigest()
```

## Phase 8 Completion Criteria

- [ ] StorageForecaster: positive slope → correct days-until projection
- [ ] StorageForecaster: negative/flat slope → returns -1
- [ ] StorageForecaster: < 7 data points → returns -1
- [ ] ConnectionForecaster and ReplicationForecaster follow same contract
- [ ] CostAnomalyDetector flags spikes > 20% from baseline
- [ ] CostAnomalyDetector: normal data → no false positives
- [ ] ForecastOrchestrator creates predictive incident when < 14 days
- [ ] ForecastOrchestrator skips when ≥ 14 days
- [ ] Daily Celery Beat schedule runs forecast cycle
- [ ] Unit tests pass for storage forecaster and cost anomaly detector
