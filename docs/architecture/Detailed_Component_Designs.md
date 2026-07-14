# AI DBA Copilot - Detailed Component Designs

This document provides a highly detailed architectural and functional design for each of the core deliverables (outputs) of the AI DBA Copilot Platform.

---

## 1. The Memory Layer (PostgreSQL Repository)

**Purpose:** Provides a persistent, stateful context library for the system. It enables semantic deduplication, LLM context generation, and historical trend analysis.

### System Architecture
- **Technology:** PostgreSQL 16+.
- **Extensions:** `pgvector` (for semantic knowledge graph), `timescaledb` (optional, for raw metric retention), `pg_stat_statements` (active monitoring of the memory layer itself).

### Core Schema Definition
```sql
CREATE TABLE metric_snapshots (
    snapshot_id UUID PRIMARY KEY,
    db_target VARCHAR(255) NOT NULL,
    metric_type VARCHAR(50), -- e.g., 'PERFORMANCE', 'CAPACITY'
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE incidents (
    incident_id UUID PRIMARY KEY,
    fingerprint VARCHAR(64) UNIQUE,
    severity VARCHAR(20), -- CRITICAL, HIGH, MEDIUM, LOW
    domain VARCHAR(50),
    status VARCHAR(20), -- ACTIVE, RESOLVED, IGNORED
    detected_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE TABLE recommendations (
    rec_id UUID PRIMARY KEY,
    incident_id UUID REFERENCES incidents(incident_id),
    rca_text TEXT,
    action_steps JSONB,
    confidence_score NUMERIC(3,2),
    risk_level VARCHAR(20)
);

CREATE EXTENSION vector;
CREATE TABLE embeddings (
    vector_id UUID PRIMARY KEY,
    source_type VARCHAR(50), -- 'INCIDENT' or 'RECOMMENDATION'
    source_id UUID,
    embedding VECTOR(1536) -- For OpenAI ada-002 compatibility
);
```

### How It Works: Population and Usage Lifecycle
The Memory Layer is the central source of truth, constantly written to by monitoring agents and queried by AI models.

**1. `metric_snapshots`**
- **How it is populated:** Periodically (e.g., every 60 seconds), decoupled worker jobs poll the MCP endpoints (`get_database_metrics`, `get_host_metrics`) and insert standardized payload JSONs.
- **How it is used:** Serves as the "current state" baseline. The Detection Engine scans this table continually to evaluate rule breaches. When an issue occurs, a window of these snapshots is bundled as context and sent to the LLM.

**2. `incidents`**
- **How it is populated:** Written to exclusively by the Detection Engine. When a threshold is breached, the engine creates a SHA-256 fingerprint. If that fingerprint isn't actively listed in this table, a new incident row is inserted.
- **How it is used:** Acts as the primary anchor entity. Every Jira ticket, Recommendation, and DBA interaction pivots off this `incident_id`.

**3. `recommendations` & `embeddings` (Semantic Knowledge)**
- **How it is populated:** Once an incident exists, the LLM processes it and inserts the response into `recommendations`. A background task immediately extracts the `rca_text`, passes it to an embedding model (e.g., OpenAI ada-002), and writes the resulting vector to the `embeddings` table linked via `source_id`.
- **How it is used:** The core of the platform's intelligence. Before the LLM makes a *new* recommendation, it runs a Cosine Similarity Search (`<=>`) against the `embeddings` table to fetch historical `recommendations` that solved the exact same problem in the past. 

### Data Pipeline and Retention Workflow
1. A cron process triggers `pg_cron` or a python worker to sweep old records.
2. `metric_snapshots` are pruned where `created_at < NOW() - INTERVAL '90 days'`.
3. High fidelity data is aggregated into rolling summary tables.

---

## 2. Issue Detection Engine

**Purpose:** Acts as the nervous system of the platform, continuously evaluating metrics against rule-based and ML-based thresholds.

### Component Design
- **Language/Framework:** Python (FastAPI / Celery).
- **Execution Model:** Asynchronous worker tasks processing data from the MCP metrics endpoints.

### Processing Logic
1. **Fetch:** Pulls standard telemetry using MCP endpoints (`get_database_metrics`).
2. **Evaluate:**
   - *Rule-based:* Checks static thresholds (e.g., CPU > 95% for 10 mins).
   - *Anomaly Detection ML:* Runs isolation forest logic on historical baseline norms to find deviations (e.g., sudden drop in active connections during peak hours).
3. **Fingerprint Generation:** Generates a deterministic SHA-256 hash derived from:
   `Hash(TargetDB + ErrorCode/MetricType + DateBucket)`.
   Date rounding (e.g., 4-hour window) ensures alerts firing in close proximity cluster under a single fingerprint.
4. **Trigger:** If the fingerprint is unique to active incidents, injects it into the Memory Layer and queues the Recommendation Engine.

### How It Works: Evaluation Lifecycle
- **Input:** Constantly ingests `metric_snapshots` records pulled from the memory layer, originally sourced by the MCP interface.
- **Processing:** Analyzes these inputs iteratively using deterministic threshold markers (rules) and ML algorithms (isolation forests for anomalies).
- **Output:** Writes new unique rows into the `incidents` table and fires an asynchronous event to trigger the Jira Integration and AI Recommendation components.

---

## 3. The AI Recommendation Engine

**Purpose:** The core generative reasoning engine. Analyzes the current event context, retrieves historical solutions, and formulates human-readable action plans.

### Component Design
- **LLM Integration:** Connects to OpenAI, Anthropic, or Azure OpenAI.
- **Workflow / Chain of Thought:**
  1. **Context Assembly:** Gathers `metric_snapshots` around the anomaly window.
  2. **Retrieval-Augmented Generation (RAG):**
     - Queries the `embeddings` table in Postgres for the top 3 similar past incidents using vector cosine similarity.
     - Retrieves the successful resolutions of those past events.
  3. **Analysis:** Prompts the LLM with the context to determine the Root Cause.
  4. **Output Formulation:**
     - Requires the LLM to output a strictly structured JSON containing: 
       - `rca`: The plain text root cause analysis.
       - `actions`: Array of SQL scripts or bash commands.
       - `risk`: Assessment of the commands (High/Medium/Low).
       - `confidence_score`: 0.0 to 1.0 rating of how sure the LLM is.

### How It Works: Generation Lifecycle
- **Input:** Triggered by a new `incident_id`. Reads metric context, historical SQL performance patterns, and relevant past semantic matches parsed from the `embeddings` table.
- **Processing:** Uses RAG (Retrieval-Augmented Generation) to tightly constrain and instruct the LLM, strictly binding the generation output against a JSON schema prompt. 
- **Output:** Persists the finalized RCA narrative and action steps directly into the `recommendations` table, pushing a notification to the UI.

---

## 4. Smart Jira Integration System

**Purpose:** Prevents ticket spam and ensures the platform perfectly mirrors the engineering workflow.

### Component Design
- **API Wrapper:** Python-based Jira Data Center/Cloud REST API interactor.
- **Deduplication Logic:**
  - Before making a Jira API POST request to `/rest/api/3/issue`, the system queries the `jira_mapping` table using the incident `fingerprint`.
  - **Match Found:** Executes a PUT request to append a comment to the existing ticket with updated metrics.
  - **No Match:** Creates a new ticket outlining the AI's RCA and Recommendation, then stores the newly generated Jira Key back into the local relational mapping.

### How It Works: Sync Lifecycle
- **Input:** Triggered by the Detection Engine whenever a new incident fingerprint is evaluated, or updated when the Recommendation Engine generates an RCA.
- **Processing:** Cross-references the internal `incident_id` against the `jira_mapping` lookup table to decide whether to treat the interaction as an `UPDATE` (PUT) or `CREATE` (POST).
- **Output:** Pushes structured ticket payload data out to the external Jira API. Never modifies the internal DB state, except to persistently store the external `ticket_key` for future reference.

---

## 5. The MCP Tool Catalog

**Purpose:** Provides a vendor-agnostic interface to communicate with the target databases safely via standardized tools.

### Component Design
- **Framework:** FastMCP or standard Model Context Protocol SDK.
- **Security:** Each tool inherently routes through a rigorous validation wrapper that drops forbidden destructive queries and audits the caller.

### Key Tools API Schema
- **`db_execute_diagnostic`**: 
  - *Input:* `database_id`, `safe_query`
  - *Constraint:* Read-only. Runs `EXPLAIN` explicitly.
- **`db_remediation_execution`**: 
  - *Input:* `database_id`, `action_script`, `authorization_token`
  - *Constraint:* Requires the auth token from the DBA UI approval step. Executes under a bounded database transaction.
- **`mcp_search_memory`**:
  - *Input:* `natural_language_query`
  - *Execution:* Converts query to vector using local embedding model, runs semantic DB search against `pgvector`.

### How It Works: Request Lifecycle
- **Input:** Receives authenticated structured tool calls over the Model Context Protocol from the backend orchestrator.
- **Processing:** Validates the input schemas against a strict allowlist. Crucially enforces the policy that prevents autonomous mutation commands from passing through without an explicit MFA/Approval token.
- **Output:** Connects natively to the target database and returns deterministic diagnostics, or successfully executes the human-approved script.

---

## 6. The DBA Copilot UI

**Purpose:** The single pane of glass for DBAs to interact with the platform, review AI outputs, and deploy fixes.

### Component Design
- **Frontend Stack:** React / Next.js / TailwindCSS.
- **Authentication:** OIDC/SAML integration for strict RBAC.

### Core Views
1. **The Anomaly Dashboard:** 
   - A real-time stream of detected incidents originating from the Detection Engine.
   - Shows severity, DB target, and LLM generated confidence score.
2. **The RCA & Remediation Review View:**
   - Displays the detailed Root Cause Analysis.
   - Shows a structured diff or code-block of the recommended action steps.
   - Presents an "Approve & Execute" button. If clicked, prompts for MFA/SSO re-authentication before hitting the MCP Tool Catalog `db_remediation_execution` endpoint.
3. **The Semantic Archive Search:**
   - A chat-like interface where a DBA can type: *"Have we seen IOPS spikes on Databricks clustered instances before?"*
   - Returns linked Jira tickets and historical RCAs.

### How It Works: Interaction Lifecycle
- **Input:** Reads the live state from the backend via polling or websockets, consuming the `incidents` and `recommendations` tables.
- **Processing:** Translates the raw database JSON execution steps into human-readable, syntax-highlighted code blocks for the observing DBA.
- **Output:** Awaits human interaction. Clicking "Approve" dispatches a POST request encapsulating an identity token to unblock the MCP tool runner for remote script deployment.
