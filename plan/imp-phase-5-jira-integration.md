---
goal: Implementation Plan — Phase 5: Jira Integration
version: 1.0
date_created: 2026-07-13
owner: AI DBA Platform Team
status: Ready
depends_on: Phase 2 (Memory Layer), Phase 4 (Detection Engine)
tags: implementation, jira, integration, dedup
---

# Phase 5: Jira Integration — Smart Ticket Management

## Overview

Implement Jira integration with fingerprint-based deduplication (repository-first, Jira-fallback), create-vs-update logic, lifecycle tracking via `jira_mapping`, and Celery task chaining from the detection engine.

**Estimated Duration:** 2 sprints (Sprints 9–10)

**Dependencies:** Phase 2 (memory service with jira_mapping table), Phase 4 (detection engine chains process_new_incident task)

## Task Inventory

| Task | Description | Est. Effort | File(s) | Status |
|------|-------------|-------------|---------|--------|
| 5.1 | Implement JiraClient | 1 hr | `src/jira-integration/client.py` | ⬜ |
| 5.2 | Implement TicketBuilder | 1 hr | `src/jira-integration/ticket_builder.py` | ⬜ |
| 5.3 | Implement DeduplicationService | 1.5 hr | `src/jira-integration/dedup.py` | ⬜ |
| 5.4 | Implement TicketUpdater | 45 min | `src/jira-integration/updater.py` | ⬜ |
| 5.5 | Implement SyncService | 1 hr | `src/jira-integration/sync.py` | ⬜ |
| 5.6 | Implement Celery tasks | 30 min | `src/jira-integration/tasks.py` | ⬜ |
| 5.7 | Implement REST API (main.py) | 30 min | `src/jira-integration/main.py` | ⬜ |
| 5.8 | Unit tests | 1 hr | `tests/unit/jira-integration/` | ⬜ |
| 5.9 | Integration test: dedup E2E | 1 hr | `tests/integration/test_jira_dedup.py` | ⬜ |

---

## Task 5.1: JiraClient

**File:** `src/jira-integration/client.py`

```python
import httpx
import logging
import time

logger = logging.getLogger(__name__)

class JiraClient:
    """Jira REST API v3 client with rate-limit handling."""
    
    def __init__(self, base_url: str, api_token: str, user_email: str, project_key: str):
        self.base_url = base_url.rstrip("/")
        self.project_key = project_key
        self._client = httpx.Client(
            auth=(user_email, api_token),
            timeout=httpx.Timeout(30)
        )
    
    def create_issue(self, summary: str, description: str, priority: str,
                     labels: list[str], issue_type: str = "Incident") -> str:
        """Create Jira issue. Returns issue key."""
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
                "description": self._markdown_to_adf(description),
                "priority": {"name": priority},
                "labels": labels
            }
        }
        response = self._request("POST", "/rest/api/3/issue", json=payload)
        return response.get("key")
    
    def add_comment(self, issue_key: str, body: str):
        """Add comment to existing issue."""
        payload = {"body": self._markdown_to_adf(body)}
        self._request("POST", f"/rest/api/3/issue/{issue_key}/comment", json=payload)
    
    def search_issues(self, jql: str, max_results: int = 5) -> list[dict]:
        """Search issues by JQL."""
        response = self._request("GET", "/rest/api/3/search",
                                 params={"jql": jql, "maxResults": max_results})
        return response.get("issues", [])
    
    def transition_issue(self, issue_key: str, transition_id: int):
        """Transition issue status."""
        self._request("POST", f"/rest/api/3/issue/{issue_key}/transitions",
                      json={"transition": {"id": str(transition_id)}})
    
    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make API request with exponential backoff on 429."""
        max_retries = 3
        for attempt in range(max_retries):
            response = self._client.request(method, f"{self.base_url}{path}", **kwargs)
            if response.status_code == 429:
                wait = int(response.headers.get("Retry-After", 2 ** attempt))
                logger.warning(f"Rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        raise Exception(f"Max retries exceeded for {method} {path}")
    
    def _markdown_to_adf(self, markdown: str) -> dict:
        """Convert simple markdown to Atlassian Document Format."""
        paragraphs = markdown.strip().split("\n\n")
        content = []
        for para in paragraphs:
            if para.startswith("|"):  # Table
                content.append(self._table_to_adf(para))
            elif para.startswith("---"):  # Separator
                continue
            else:
                text_content = [{"type": "text", "text": para.strip()}]
                content.append({
                    "type": "paragraph",
                    "content": text_content
                })
        return {"type": "doc", "version": 1, "content": content}
```

---

## Task 5.2: TicketBuilder

**File:** `src/jira-integration/ticket_builder.py`

```python
PRIORITY_MAP = {
    "CRITICAL": "Highest",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "LOW": "Low",
}

def format_incident_for_jira(incident: dict) -> dict:
    """Build Jira issue payload fields."""
    severity = incident.get("severity", "LOW")
    domain = incident.get("domain", "UNKNOWN")
    db_target = incident.get("db_target", "unknown")
    error_code = incident.get("error_code_or_metric_type", "unknown")
    
    summary = f"[{severity}] {domain} - {db_target}: {error_code}"
    
    description = (
        f"*Incident ID:* `{incident.get('incident_id')}`\n\n"
        f"*DB Target:* `{db_target}`\n"
        f"*Domain:* {domain}\n"
        f"*Severity:* {severity}\n"
        f"*Fingerprint:* `{incident.get('fingerprint')}`\n"
        f"*First Detected:* {incident.get('detected_at')}\n\n"
        f"## Current Metrics\n"
        f"Detection count: {incident.get('detection_count', 1)}\n"
    )
    
    return {
        "summary": summary,
        "description": description,
        "priority": PRIORITY_MAP.get(severity, "Medium"),
        "labels": [
            incident.get("fingerprint", "")[:50],
            domain.lower(),
            db_target
        ]
    }
```

---

## Task 5.3: DeduplicationService

**File:** `src/jira-integration/dedup.py`

```python
import logging
from httpx import AsyncClient
from .ticket_builder import format_incident_for_jira

logger = logging.getLogger(__name__)

class DeduplicationService:
    """Two-layer dedup: memory mapping first, JQL fallback second."""
    
    def __init__(self, memory_url: str, jira_client):
        self.memory_url = memory_url
        self.jira = jira_client
        self.client = AsyncClient(timeout=30)
    
    async def process_incident(self, incident: dict) -> dict:
        """Main dedup logic. Returns {action, jira_key}."""
        fingerprint = incident.get("fingerprint")
        incident_id = incident.get("incident_id")
        
        # Layer 1: Check memory mapping
        mapping = await self._get_mapping(incident_id)
        if mapping and mapping.get("sync_status") != "FAILED":
            jira_key = mapping["jira_ticket_key"]
            await self._update_ticket(jira_key, incident)
            return {"action": "updated", "jira_key": jira_key}
        
        # Layer 2: JQL fallback
        jql = f'labels = "{fingerprint}" AND status != Done ORDER BY created DESC'
        issues = self.jira.search_issues(jql)
        
        if issues:
            jira_key = issues[0]["key"]
            await self._store_mapping(incident_id, jira_key)
            await self._update_ticket(jira_key, incident)
            return {"action": "updated", "jira_key": jira_key}
        
        # Layer 3: Create new ticket
        ticket = format_incident_for_jira(incident)
        jira_key = self.jira.create_issue(**ticket)
        await self._store_mapping(incident_id, jira_key)
        return {"action": "created", "jira_key": jira_key}
    
    async def _get_mapping(self, incident_id: str) -> dict | None:
        resp = await self.client.get(f"{self.memory_url}/jira_mappings/{incident_id}")
        return resp.json() if resp.status_code == 200 else None
    
    async def _store_mapping(self, incident_id: str, jira_key: str):
        await self.client.post(f"{self.memory_url}/jira_mappings", json={
            "incident_id": incident_id,
            "jira_ticket_key": jira_key,
            "sync_status": "SYNCED"
        })
    
    async def _update_ticket(self, jira_key: str, incident: dict):
        comment = (
            f"*Updated:* {incident.get('detected_at')}\n"
            f"Detection count: {incident.get('detection_count', 1)}\n"
            f"Severity: {incident.get('severity')}"
        )
        self.jira.add_comment(jira_key, comment)
```

---

## Task 5.4: TicketUpdater

**File:** `src/jira-integration/updater.py`

```python
from .ticket_builder import PRIORITY_MAP

class TicketUpdater:
    def __init__(self, jira_client):
        self.jira = jira_client
    
    def update_existing(self, jira_key: str, incident: dict):
        """Update existing ticket with new metrics and escalate if needed."""
        # Add comment with latest state
        comment = (
            f"*Auto-updated:* {incident.get('detected_at')}\n"
            f"Detection count incremented to {incident.get('detection_count')}.\n"
            f"Current severity: {incident.get('severity')}."
        )
        self.jira.add_comment(jira_key, comment)
        
        # Escalate priority if severity increased
        current_priority = PRIORITY_MAP.get(incident.get("severity"), "Medium")
        issue = self.jira._request("GET", f"/rest/api/3/issue/{jira_key}")
        existing_priority = issue.get("fields", {}).get("priority", {}).get("name", "")
        
        priority_rank = {"Lowest": 0, "Low": 1, "Medium": 2, "High": 3, "Highest": 4}
        if priority_rank.get(current_priority, 0) > priority_rank.get(existing_priority, 0):
            self.jira._request("PUT", f"/rest/api/3/issue/{jira_key}", 
                              json={"fields": {"priority": {"name": current_priority}}})
```

---

## Task 5.5–5.7: SyncService, Celery Tasks, REST API

**SyncService** (`sync.py`): Handles resolution transitions and recommendation linking.

**Celery Tasks** (`tasks.py`):
- `process_jira_for_incident(incident_id)`: Full dedup → create/update flow
- `sync_recommendation(incident_id, rec_id)`: Comment on ticket with RCA summary
- `sync_resolution(incident_id)`: Transition ticket to Done

**REST API** (`main.py`, port 8003):
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /health | GET | Health check |
| /incidents/{id}/sync | POST | Trigger manual sync |
| /mappings | GET | List all mappings |
| /mappings/{incident_id} | GET | Get mapping for incident |

## Phase 5 Completion Criteria

- [ ] JiraClient creates issues with correct priority, summary, labels
- [ ] JiraClient handles 429 with exponential backoff
- [ ] TicketBuilder maps severity→priority correctly for all 4 levels
- [ ] DeduplicationService: same fingerprint → update existing, not create new
- [ ] DeduplicationService: different fingerprint → create separate ticket
- [ ] TicketUpdater escalates priority when severity increases
- [ ] SyncService transitions ticket on incident resolution
- [ ] Memory mapping is source of truth; JQL is fallback
- [ ] Unit tests pass for dedup, ticket builder, client
- [ ] Integration test: incident → Jira create → update → resolve → transition
