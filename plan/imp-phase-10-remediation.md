---
goal: Implementation Plan — Phase 10: Automated Remediation
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 3 (MCP Integration Layer), Phase 6 (Recommendation Engine)
tags: implementation, remediation, auto-fix, approval
---

# Phase 10: Automated Remediation

## Overview

Implement the three-tier remediation system: auto-execute low-risk operations (ANALYZE, UPDATE STATISTICS), gate medium/high-risk operations behind DBA approval token validation, and block destructive operations entirely.

**Estimated Duration:** 2 sprints (Sprints 19–20)

**Dependencies:** Phase 3 (MCP exec_proc, approval gate), Phase 6 (remediation_classifier)

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 10.1 | Implement AutoExecutor | 1 hr | `src/mcp-layer/tools/auto_remediation.py` | ⬜ |
| 10.2 | Implement ApprovedExecutor | 1 hr | `src/mcp-layer/tools/approved_remediation.py` | ⬜ |
| 10.3 | Implement RemediationOrchestrator | 1.5 hr | `src/mcp-layer/remediation_orchestrator.py` | ⬜ |
| 10.4 | Add /remediation/execute endpoint | 30 min | `src/mcp-layer/main.py` | ⬜ |
| 10.5 | Unit tests | 1 hr | `tests/unit/mcp-layer/test_remediation.py` | ⬜ |
| 10.6 | Integration test | 1 hr | `tests/integration/test_remediation_pipeline.py` | ⬜ |
| 10.7 | MCP circuit breaker (Gap G5) | 1.5 hr | `src/mcp-layer/client.py` | ⬜ |

---

## Task 10.1: AutoExecutor

**File:** `src/mcp-layer/tools/auto_remediation.py`

```python
import logging
from ..client import MCPClient

logger = logging.getLogger(__name__)

class AutoExecutor:
    """Execute AUTO-classified remediation actions."""
    
    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client
    
    async def execute(self, action: dict) -> dict:
        """Execute a single AUTO action."""
        command = action.get("command", "")
        logger.info(f"Auto-executing: {command}")
        
        result = await self.mcp.call_tool("exec_proc", {
            "database_id": "primary",
            "action_script": command
        })
        
        return {
            "step_index": action.get("step_index", 0),
            "action": command,
            "success": result.get("success", False),
            "output": result.get("data"),
            "error": result.get("error"),
            "duration_ms": 0  # Populated by caller
        }
```

---

## Task 10.2: ApprovedExecutor

**File:** `src/mcp-layer/tools/approved_remediation.py`

```python
import logging
from ..client import MCPClient
from ..auth import ApprovalGate

logger = logging.getLogger(__name__)

class ApprovedExecutor:
    """Execute APPROVAL_REQUIRED actions after token validation."""
    
    def __init__(self, mcp_client: MCPClient, approval_gate: ApprovalGate):
        self.mcp = mcp_client
        self.gate = approval_gate
    
    async def execute(self, action: dict, auth_token: str) -> dict:
        """Validate token, then execute action."""
        command = action.get("command", "")
        action_type = action.get("type", "APPROVAL_REQUIRED")
        
        # Validate token
        try:
            self.gate.require_approval(action_type, auth_token)
        except Exception as e:
            return {
                "step_index": action.get("step_index", 0),
                "action": command,
                "success": False,
                "error": str(e)
            }
        
        # Execute
        logger.info(f"Approved execution: {command}")
        result = await self.mcp.call_tool("exec_proc", {
            "database_id": "primary",
            "action_script": command
        })
        
        return {
            "step_index": action.get("step_index", 0),
            "action": command,
            "success": result.get("success", False),
            "output": result.get("data"),
            "error": result.get("error")
        }
```

---

## Task 10.3: RemediationOrchestrator

**File:** `src/mcp-layer/remediation_orchestrator.py`

```python
import logging
from datetime import datetime
from httpx import AsyncClient

logger = logging.getLogger(__name__)

class RemediationOrchestrator:
    """Orchestrate remediation execution across AUTO/APPROVAL_REQUIRED/BLOCKED."""
    
    def __init__(self, memory_url: str, auto_executor, approved_executor):
        self.memory_url = memory_url
        self.auto = auto_executor
        self.approved = approved_executor
        self.client = AsyncClient(timeout=60)
    
    async def execute(self, rec_id: str, auth_token: str = None) -> dict:
        start = datetime.utcnow()
        
        # 1. Fetch recommendation
        resp = await self.client.get(f"{self.memory_url}/recommendations/detail/{rec_id}")
        if resp.status_code != 200:
            return {"error": "Recommendation not found", "status": 404}
        rec = resp.json()
        
        auto_results = []
        pending = []
        blocked = []
        
        # 2. Process each action
        for i, action in enumerate(rec.get("action_steps", [])):
            action["step_index"] = i
            action_type = action.get("type", "APPROVAL_REQUIRED")
            
            if action_type == "AUTO":
                result = await self.auto.execute(action)
                result["duration_ms"] = int((datetime.utcnow() - start).total_seconds() * 1000)
                auto_results.append(result)
                
            elif action_type == "APPROVAL_REQUIRED":
                if auth_token:
                    result = await self.approved.execute(action, auth_token)
                    if result["success"]:
                        auto_results.append(result)
                    else:
                        pending.append({
                            "step_index": i,
                            "action": action.get("command"),
                            "reason": result.get("error", "auth_token_required")
                        })
                else:
                    pending.append({
                        "step_index": i,
                        "action": action.get("command"),
                        "reason": "auth_token_required"
                    })
                    
            elif action_type == "BLOCKED":
                blocked.append({
                    "step_index": i,
                    "action": action.get("command"),
                    "reason": "BLOCKED: Destructive operation not permitted through automated remediation",
                    "classification": "BLOCKED"
                })
        
        return {
            "rec_id": rec_id,
            "auto_results": auto_results,
            "pending_approval": pending,
            "blocked": blocked,
            "executed_at": datetime.utcnow().isoformat(),
            "duration_ms": int((datetime.utcnow() - start).total_seconds() * 1000)
        }
```

## Phase 10 Completion Criteria

- [ ] AUTO actions (ANALYZE, UPDATE STATISTICS) execute without human intervention
- [ ] APPROVAL_REQUIRED actions without token → pending_approval list
- [ ] APPROVAL_REQUIRED actions with valid token → execute
- [ ] BLOCKED actions → blocked list, never executed
- [ ] All outcomes logged to remediation_history
- [ ] Unit tests: all 3 classification paths
- [ ] Integration test: full remediation pipeline
- [ ] Circuit breaker trips after 5 failures and recovers after 30s (G5)

---

## Task 10.7: MCP Circuit Breaker (Gap G5)

**File:** `src/mcp-layer/client.py`

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"          # Normal — calls pass through
    OPEN = "open"              # Failing — calls rejected immediately
    HALF_OPEN = "half_open"    # Testing — limited calls allowed

class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""

class CircuitBreaker:
    """Prevents cascading failures when MCP server is degraded.
    
    Addresses Gap G5 from plan audit. Without this, a slow SQL Server
    instance causes all platform services to block on MCP timeouts.
    
    States:
      CLOSED → 5 consecutive failures → OPEN
      OPEN → 30s timeout → HALF_OPEN
      HALF_OPEN → 1 success → CLOSED | 1 failure → OPEN
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit transitioning OPEN → HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(
                    f"MCP circuit is OPEN. Retry in "
                    f"{self.recovery_timeout - (time.time() - self.last_failure_time):.0f}s"
                )

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                logger.info("Circuit recovered: HALF_OPEN → CLOSED")
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    f"Circuit OPEN after {self.failure_count} failures. "
                    f"Last error: {e}"
                )
            raise

# Usage in MCPClient:
class MCPClient:
    def __init__(self, server_url: str, ...):
        self.server_url = server_url
        self.circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        return await self.circuit.call(self._do_call, tool_name, arguments)

    async def _do_call(self, tool_name: str, arguments: dict) -> dict:
        # Original HTTP call logic here
        ...
```
