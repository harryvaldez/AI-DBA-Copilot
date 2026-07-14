---
goal: Implementation Plan — Phase 3: MCP Integration Layer
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 1 (Foundation)
tags: implementation, mcp, integration, safety, tool-mapping
---

# Phase 3: MCP Integration Layer

## Overview

Build the MCP integration client and policy wrapper that bridges all platform services to the existing `mcp-sql-server`. This includes canonical-to-runtime tool name mapping, read-only safety enforcement, secret scrubbing, approval-gated writes, a REST proxy, and adapter modules for metrics, performance, storage, operations, and remediation.

**Estimated Duration:** 2 sprints (Sprints 5–6)

**Dependencies:** Phase 1 (foundation must provide Docker Compose + service skeleton). External `mcp-sql-server` must be running for integration tests.

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 3.1 | Create tool_mapping.yaml | 1 hr | `src/mcp-layer/tool_mapping.yaml` | ⬜ |
| 3.2 | Implement MCPClient | 1 hr | `src/mcp-layer/client.py` | ⬜ |
| 3.3 | Implement SafetyWrapper | 1 hr | `src/mcp-layer/safety.py` | ⬜ |
| 3.4 | Implement ApprovalGate | 1 hr | `src/mcp-layer/auth.py` | ⬜ |
| 3.5 | Implement Metrics adapters | 1 hr | `src/mcp-layer/tools/metrics.py` | ⬜ |
| 3.6 | Implement Performance adapters | 1 hr | `src/mcp-layer/tools/performance.py` | ⬜ |
| 3.7 | Implement Storage adapters | 30 min | `src/mcp-layer/tools/storage.py` | ⬜ |
| 3.8 | Implement Operations adapters | 30 min | `src/mcp-layer/tools/operations.py` | ⬜ |
| 3.9 | Implement Remediation tools | 1 hr | `src/mcp-layer/tools/remediation.py` | ⬜ |
| 3.10 | Implement REST proxy (main.py) | 1 hr | `src/mcp-layer/main.py` | ⬜ |
| 3.11 | Unit tests: safety, auth, mapping | 1.5 hr | `tests/unit/mcp-layer/` | ⬜ |
| 3.12 | Integration test: full tool chain | 1 hr | `tests/integration/test_mcp_chain.py` | ⬜ |

---

## Task 3.1: Tool Mapping YAML

**File:** `src/mcp-layer/tool_mapping.yaml`

```yaml
instances:
  primary:
    driver: sql2019
    tools:
      get_database_metrics:
        runtime: db_primary_sql2019_diagnostics
        read_only: true
      get_host_metrics:
        runtime: db_primary_sql2019_sessions
        read_only: true
      get_connection_metrics:
        runtime: db_primary_sql2019_active_sessions_report
        read_only: true
      get_replication_metrics:
        runtime: db_primary_sql2019_replica_report
        read_only: true
      get_slow_queries:
        runtime: db_primary_sql2019_top_queries_report
        read_only: true
      get_query_plan:
        runtime: db_primary_sql2019_execute_query
        read_only: true
      get_blocking_sessions:
        runtime: db_primary_sql2019_block_report
        read_only: true
      get_storage_growth:
        runtime: db_primary_sql2019_query_store_mem_used
        read_only: true
      get_tablespace_usage:
        runtime: db_primary_sql2019_query_store_consumption
        read_only: true
      get_database_configuration:
        runtime: db_primary_sql2019_get_query_store_options
        read_only: true
      exec_proc:
        runtime: db_primary_sql2019_execute_query
        read_only: false

  secondary:
    driver: sql2019
    tools:
      get_database_metrics:
        runtime: db_secondary_sql2019_diagnostics
        read_only: true
      get_slow_queries:
        runtime: db_secondary_sql2019_top_queries_report
        read_only: true
      get_blocking_sessions:
        runtime: db_secondary_sql2019_block_report
        read_only: true
      # ... additional tools follow same naming pattern
```

**Validation:** YAML file loads without errors. All canonical names from TDD catalog are present.

---

## Task 3.2: MCPClient

**File:** `src/mcp-layer/client.py`

```python
import httpx
import logging
from typing import Any

logger = logging.getLogger(__name__)

class MCPClient:
    """HTTP client for mcp-sql-server."""
    
    def __init__(self, server_url: str, timeout: int = 30, max_retries: int = 3):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=httpx.Timeout(timeout))
    
    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute an MCP tool. Returns standardized envelope."""
        for attempt in range(self.max_retries):
            try:
                response = self._client.post(
                    f"{self.server_url}/mcp/tool",
                    json={"name": tool_name, "arguments": arguments}
                )
                response.raise_for_status()
                return {"success": True, "data": response.json(), "error": None}
            except httpx.TimeoutException:
                logger.warning(f"MCP call timeout (attempt {attempt+1}): {tool_name}")
                if attempt < self.max_retries - 1:
                    continue
                return {"success": False, "data": None, "error": "MCP_TIMEOUT"}
            except httpx.HTTPStatusError as e:
                return {"success": False, "data": None, "error": f"MCP_HTTP_{e.response.status_code}"}
            except httpx.RequestError as e:
                logger.error(f"MCP request failed: {e}")
                return {"success": False, "data": None, "error": "MCP_UNREACHABLE"}
    
    def ping(self) -> bool:
        """Check MCP server connectivity."""
        try:
            resp = self._client.get(f"{self.server_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
    
    def close(self):
        self._client.close()
```

---

## Task 3.3: SafetyWrapper

**File:** `src/mcp-layer/safety.py`

```python
import re

class SafetyWrapper:
    """Read-only validation and secret scrubbing."""
    
    DESTRUCTIVE_PATTERNS = [
        r'\bDROP\s+(TABLE|INDEX|VIEW|PROCEDURE|DATABASE|SCHEMA|FUNCTION)\b',
        r'\bALTER\s+(TABLE|DATABASE|INDEX)\b',
        r'\bTRUNCATE\s+TABLE\b',
        r'\bINSERT\s+INTO\b',
        r'\bUPDATE\s+.+\s+SET\b',
        r'\bDELETE\s+FROM\b',
        r'\bCREATE\s+(TABLE|INDEX|DATABASE)\b',
        r'\bEXEC\s*\(',  # Dynamic SQL execution
    ]
    
    SECRET_PATTERNS = [
        (r"(password|pwd)\s*=\s*['\"][^'\"]+['\"]", r"\1='[REDACTED]'"),
        (r"IDENTIFIED\s+BY\s+['\"][^'\"]+['\"]", "IDENTIFIED BY [REDACTED]"),
        (r"(secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]", r"\1='[REDACTED]'"),
        (r"(connection_string|conn_str)\s*=\s*['\"][^'\"]+['\"]", r"\1='[REDACTED]'"),
    ]
    
    @classmethod
    def validate_read_only(cls, sql: str) -> bool:
        """Returns True if safe (no destructive patterns). Returns False if blocked."""
        for pattern in cls.DESTRUCTIVE_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                return False
        return True
    
    @classmethod
    def scrub_secrets(cls, text: str) -> str:
        """Redact known secret patterns from text."""
        result = text
        for pattern, replacement in cls.SECRET_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result
```

---

## Task 3.4: ApprovalGate

**File:** `src/mcp-layer/auth.py`

```python
import jwt
import time
import logging

logger = logging.getLogger(__name__)

class ApprovalRequiredError(Exception):
    def __init__(self, message="Approval token required for this operation"):
        self.message = message
        super().__init__(self.message)

class ApprovalGate:
    """JWT-based approval token validation."""
    
    def __init__(self, public_key: str, algorithm: str = "RS256"):
        self.public_key = public_key
        self.algorithm = algorithm
    
    def validate_token(self, token: str, required_scope: str = "dba_admin",
                       required_action: str = None) -> dict:
        """
        Validate JWT token. Returns decoded payload if valid.
        Raises ApprovalRequiredError if invalid.
        """
        try:
            payload = jwt.decode(token, self.public_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            logger.warning("Approval token expired")
            raise ApprovalRequiredError("Token expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid approval token: {e}")
            raise ApprovalRequiredError("Invalid token")
        
        # Check scope
        scopes = payload.get("scope", [])
        if required_scope not in scopes:
            logger.warning(f"Token missing required scope: {required_scope}")
            raise ApprovalRequiredError(f"Insufficient scope: need {required_scope}")
        
        # Check action
        if required_action and required_action not in payload.get("actions", []):
            logger.warning(f"Token missing required action: {required_action}")
            raise ApprovalRequiredError(f"Action not authorized: {required_action}")
        
        return payload
    
    def require_approval(self, action_type: str, token: str = None):
        """Raise if action requires approval and token is missing/invalid."""
        if token is None:
            raise ApprovalRequiredError("Approval token is required")
        self.validate_token(token, required_action=action_type)
```

---

## Tasks 3.5–3.8: Adapter Modules

### Metrics Adapters (`tools/metrics.py`)
```python
from ..client import MCPClient
from ..safety import SafetyWrapper

def get_database_metrics(client: MCPClient, db_name: str) -> dict:
    result = client.call_tool("db_primary_sql2019_diagnostics", {"db_name": db_name})
    # Scrub all text fields
    if result["success"] and result["data"]:
        result["data"] = SafetyWrapper.scrub_secrets(str(result["data"]))
    return result

def get_connection_metrics(client: MCPClient, db_name: str) -> dict:
    return client.call_tool("db_primary_sql2019_active_sessions_report", {"db_name": db_name})

def get_replication_metrics(client: MCPClient, db_name: str) -> dict:
    return client.call_tool("db_primary_sql2019_replica_report", {"db_name": db_name})
```

### Performance Adapters (`tools/performance.py`)
```python
from ..client import MCPClient
from ..safety import SafetyWrapper

def get_slow_queries(client: MCPClient, db_name: str, threshold_ms: int = 1000) -> dict:
    result = client.call_tool("db_primary_sql2019_top_queries_report", {
        "db_name": db_name
    })
    if result["success"] and result["data"]:
        result["data"] = SafetyWrapper.scrub_secrets(str(result["data"]))
    return result

def get_blocking_sessions(client: MCPClient, db_name: str) -> dict:
    return client.call_tool("db_primary_sql2019_block_report", {"db_name": db_name})
```

### Storage Adapters (`tools/storage.py`)
```python
from ..client import MCPClient

def get_storage_growth(client: MCPClient, db_name: str) -> dict:
    return client.call_tool("db_primary_sql2019_query_store_mem_used", {"db_name": db_name})

def get_tablespace_usage(client: MCPClient, db_name: str) -> dict:
    return client.call_tool("db_primary_sql2019_query_store_consumption", {"db_name": db_name})
```

### Operations Adapters (`tools/operations.py`)
```python
from ..client import MCPClient

def get_database_configuration(client: MCPClient, db_name: str) -> dict:
    return client.call_tool("db_primary_sql2019_get_query_store_options", {"db_name": db_name})
```

---

## Task 3.9: Remediation Tools

**File:** `src/mcp-layer/tools/remediation.py`

```python
from ..client import MCPClient
from ..auth import ApprovalGate, ApprovalRequiredError

def auto_remediation(client: MCPClient, action_type: str, action_script: str) -> dict:
    """Execute AUTO-classified actions with system service account."""
    result = client.call_tool("db_primary_sql2019_execute_query", {
        "query": action_script,
        "database_id": "primary"
    })
    return result

def approved_remediation(client: MCPClient, action_type: str, 
                          action_script: str, auth_token: str) -> dict:
    """Execute APPROVAL_REQUIRED actions after token validation."""
    gate = ApprovalGate(public_key="", algorithm="RS256")  # Configured via env
    try:
        gate.validate_token(auth_token, required_action=action_type)
    except ApprovalRequiredError as e:
        return {"success": False, "data": None, "error": str(e)}
    
    result = client.call_tool("db_primary_sql2019_execute_query", {
        "query": action_script,
        "database_id": "primary"
    })
    return result
```

---

## Task 3.10: REST Proxy (main.py)

**File:** `src/mcp-layer/main.py`

```python
from fastapi import FastAPI, HTTPException
from .client import MCPClient
from .tool_mapping import load_mapping, resolve_tool_name
import os

app = FastAPI(title="AI DBA Copilot - MCP Layer", version="0.1.0")
mcp_client = MCPClient(server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8080"))

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mcp_connected": mcp_client.ping(),
        "service": "mcp-layer"
    }

@app.get("/mcp/status")
async def mcp_status():
    connected = mcp_client.ping()
    return {
        "connected": connected,
        "server_url": os.getenv("MCP_SERVER_URL"),
        "last_ping": connected,
        "error": None if connected else "MCP server unreachable"
    }

@app.post("/tools/{canonical_name}")
async def invoke_tool(canonical_name: str, arguments: dict):
    try:
        runtime_name = resolve_tool_name(canonical_name, os.getenv("MCP_INSTANCE", "primary"))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Tool '{canonical_name}' not found")
    
    result = mcp_client.call_tool(runtime_name, arguments)
    if not result["success"]:
        raise HTTPException(status_code=503, detail=result["error"])
    return result["data"]

@app.post("/remediation/execute")
async def execute_remediation(rec_id: str, auth_token: str = None):
    """Executes remediation for a recommendation. Delegated to orchestrator."""
    # This is a proxy — full logic in RemediationOrchestrator
    return {"status": "pending", "rec_id": rec_id}
```

---

## Tasks 3.11–3.12: Tests

### Unit Tests (`tests/unit/mcp-layer/test_safety_wrapper.py`)
```python
import pytest
from src.mcp_layer.safety import SafetyWrapper

class TestSafetyWrapper:
    def test_drop_table_rejected(self):
        assert SafetyWrapper.validate_read_only("DROP TABLE orders;") == False
    
    def test_select_allowed(self):
        assert SafetyWrapper.validate_read_only("SELECT * FROM sys.dm_exec_queries") == True
    
    def test_alter_rejected(self):
        assert SafetyWrapper.validate_read_only("ALTER DATABASE test SET SINGLE_USER") == False
    
    def test_truncate_rejected(self):
        assert SafetyWrapper.validate_read_only("TRUNCATE TABLE orders") == False
    
    def test_scrub_password(self):
        result = SafetyWrapper.scrub_secrets("password='supersecret123'")
        assert "[REDACTED]" in result
        assert "supersecret123" not in result
    
    def test_scrub_multiple_patterns(self):
        text = "conn_str='Server=db;User=admin;Password=secret123'"
        result = SafetyWrapper.scrub_secrets(text)
        assert "[REDACTED]" in result
        assert "secret123" not in result
    
    def test_scrub_does_not_modify_clean_text(self):
        clean = "SELECT TOP 10 * FROM sys.dm_exec_query_stats"
        assert SafetyWrapper.scrub_secrets(clean) == clean
```

### Unit Tests (`tests/unit/mcp-layer/test_tool_mapping.py`)
```python
import pytest
import yaml
from pathlib import Path

MAPPING_PATH = "src/mcp-layer/tool_mapping.yaml"

class TestToolMapping:
    def test_yaml_loads(self):
        with open(MAPPING_PATH) as f:
            mapping = yaml.safe_load(f)
        assert "instances" in mapping
    
    def test_primary_has_all_required_tools(self):
        with open(MAPPING_PATH) as f:
            mapping = yaml.safe_load(f)
        tools = mapping["instances"]["primary"]["tools"]
        required = [
            "get_database_metrics", "get_host_metrics", "get_connection_metrics",
            "get_replication_metrics", "get_slow_queries", "get_query_plan",
            "get_blocking_sessions", "get_storage_growth", "get_tablespace_usage",
            "get_database_configuration", "exec_proc"
        ]
        for tool in required:
            assert tool in tools, f"Missing required tool: {tool}"
    
    def test_all_tools_have_runtime_name(self):
        with open(MAPPING_PATH) as f:
            mapping = yaml.safe_load(f)
        for instance_name, instance in mapping["instances"].items():
            for tool_name, tool_config in instance["tools"].items():
                assert "runtime" in tool_config, f"{instance_name}/{tool_name} missing runtime"
```

## Phase 3 Completion Criteria

- [ ] `tool_mapping.yaml` loads without errors and contains all required tools
- [ ] `MCPClient.call_tool()` returns standardized envelope on success/failure/timeout
- [ ] `SafetyWrapper.validate_read_only()` blocks all destructive SQL patterns
- [ ] `SafetyWrapper.scrub_secrets()` redacts all known secret patterns
- [ ] `ApprovalGate.validate_token()` rejects expired/missing/invalid tokens
- [ ] `ApprovalGate.require_approval()` raises `ApprovalRequiredError` for unauthorized calls
- [ ] All adapter modules return data in expected format
- [ ] REST proxy `/tools/{name}` resolves canonical names correctly
- [ ] REST proxy `/mcp/status` reports MCP server connectivity
- [ ] Unit test suite passes with ≥ 90% coverage on safety, auth, mapping modules
