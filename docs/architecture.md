# ApexDeploy — Architecture

## System Architecture

ApexDeploy is built as a **multi-agent AI platform** using Google ADK, where 8 specialized agents collaborate through an event-driven pipeline to automate the full software deployment lifecycle.

### High-Level Overview

```mermaid
graph TB
    subgraph "Frontend Layer"
        ST["🖥️ Streamlit Dashboard<br/>(Port 8501)"]
    end

    subgraph "API Layer"
        FA["⚡ FastAPI Server<br/>(Port 8000)"]
    end

    subgraph "Orchestration Layer"
        ORC["🧠 Orchestrator<br/>(Google ADK)"]
        PR["🔄 Pipeline Runner"]
        EV["📡 Event Bus"]
        TQ["📋 Task Queue"]
    end

    subgraph "Agent Layer"
        GA["📂 Git Agent"]
        CRA["🔍 Code Review Agent"]
        TA["🧪 Testing Agent"]
        SA["🛡️ Security Agent"]
        DA["🐳 Docker Agent"]
        DEP["🚀 Deployment Agent"]
        MA["📊 Monitoring Agent"]
        RA["⏪ Rollback Agent"]
    end

    subgraph "Intelligence Layer"
        LLM["🤖 Gemini Client"]
        MEM["🧠 Agent Memory"]
        STATE["📌 State Manager"]
    end

    subgraph "MCP Layer"
        FS_MCP["📁 Filesystem MCP"]
        GIT_MCP["🔀 Git MCP"]
        GH_MCP["🐙 GitHub MCP"]
        TERM_MCP["💻 Terminal MCP"]
    end

    subgraph "Infrastructure Layer"
        DB["🗃️ SQLite"]
        DOCKER["🐳 Docker Engine"]
        TEL["📈 Telemetry"]
    end

    subgraph "Storage Layer"
        ART["📦 artifacts/"]
        WS["📁 workspaces/"]
    end

    ST -->|REST API| FA
    FA --> ORC
    ORC --> PR
    PR --> TQ
    TQ --> GA & CRA & TA & SA & DA & DEP & MA & RA
    GA & CRA & TA & SA & DA & DEP & MA & RA -->|publish| EV
    EV -->|subscribe| ORC

    GA --> GIT_MCP & GH_MCP
    CRA --> FS_MCP & LLM
    TA --> TERM_MCP
    SA --> TERM_MCP & FS_MCP
    DA --> DOCKER
    DEP --> DOCKER
    MA --> DOCKER
    RA --> DOCKER

    GA & CRA & TA & SA & DA & DEP & MA & RA --> STATE
    GA & CRA & TA & SA & DA & DEP & MA & RA --> MEM
    GA & CRA & TA & SA & DA & DEP & MA & RA --> DB
    GA & CRA & TA & SA & DA & DEP & MA & RA --> ART
    GA --> WS
    ORC --> TEL
```

---

## Layers

### 1. Frontend Layer
**Streamlit Dashboard** — provides a real-time UI with 10 pages: Overview, Repositories, Pipeline, Agents, Docker, Monitoring, Security, Reports, Logs, and Settings. Communicates with the backend via REST API calls.

### 2. API Layer
**FastAPI Server** — exposes RESTful endpoints for pipeline management, agent control, deployment operations, monitoring data, and report generation. Provides auto-generated OpenAPI docs.

### 3. Orchestration Layer
- **Orchestrator (Google ADK)** — the central brain that coordinates all agents
- **Pipeline Runner** — executes pipeline stages in sequence/parallel
- **Event Bus** — pub/sub system for decoupled agent communication
- **Task Queue** — priority queue for scheduling agent work

### 4. Agent Layer
Eight specialized agents, each with a single responsibility:
- **Git Agent** → Repository operations
- **Code Review Agent** → Code quality analysis
- **Testing Agent** → Test suite execution
- **Security Agent** → Vulnerability scanning
- **Docker Agent** → Image build & management
- **Deployment Agent** → Container deployment
- **Monitoring Agent** → Health monitoring
- **Rollback Agent** → Failure recovery

### 5. Intelligence Layer
- **Gemini Client** → Centralized LLM integration
- **Agent Memory** → Cross-pipeline learning
- **State Manager** → Real-time agent status

### 6. MCP Layer
Model Context Protocol wrappers providing standardized tool interfaces for filesystem, Git, GitHub, and terminal operations.

### 7. Infrastructure Layer
- **SQLite** → Persistent storage for all data
- **Docker Engine** → Container lifecycle management
- **Telemetry** → Performance metrics and traces

### 8. Storage Layer
- **artifacts/** → Organized agent outputs
- **workspaces/** → Cloned repositories

---

## Database Schema

See [001_initial.sql](../src/db/migrations/001_initial.sql) for the complete schema with 9 tables:
- `repositories` — tracked Git repositories
- `pipeline_runs` — pipeline execution records
- `agent_results` — per-agent output data
- `deployments` — container deployment records
- `monitoring_snapshots` — health check data
- `security_findings` — vulnerability records
- `rollback_events` — rollback history
- `agent_memory` — agent learning data
- `event_log` — event audit trail

---

## Pipeline Flow

```mermaid
stateDiagram-v2
    [*] --> Queued: Pipeline triggered
    Queued --> CloneRepo: Dequeue task

    CloneRepo --> AnalyzeCode: Clone success
    CloneRepo --> Failed: Clone failed

    state parallel_analysis <<fork>>
    AnalyzeCode --> parallel_analysis

    parallel_analysis --> CodeReview
    parallel_analysis --> RunTests
    parallel_analysis --> SecurityScan

    state parallel_join <<join>>
    CodeReview --> parallel_join
    RunTests --> parallel_join
    SecurityScan --> parallel_join

    parallel_join --> GateCheck: All complete

    GateCheck --> BuildImage: All passed
    GateCheck --> Failed: Critical issues

    BuildImage --> DeployContainer: Build success
    BuildImage --> Failed: Build failed

    DeployContainer --> Monitoring: Deploy success
    DeployContainer --> Failed: Deploy failed

    Monitoring --> Healthy: Health OK
    Monitoring --> Unhealthy: Health degraded

    Unhealthy --> Rollback: Auto-rollback
    Rollback --> RolledBack: Rollback success
    Rollback --> Failed: Rollback failed

    Healthy --> [*]: Pipeline complete
    RolledBack --> [*]: Rolled back safely
    Failed --> [*]: Pipeline failed
```

---

## Event System

```mermaid
graph LR
    subgraph "Publishers"
        GA["Git Agent"]
        TA["Testing Agent"]
        DA["Docker Agent"]
        MA["Monitor Agent"]
        RA["Rollback Agent"]
    end

    subgraph "Event Bus"
        EB["📡 In-Process Pub/Sub"]
    end

    subgraph "Subscribers"
        ORC["Orchestrator"]
        STATE["State Manager"]
        TEL["Telemetry"]
        MEM["Memory"]
        DB["Database Logger"]
    end

    GA -->|REPO_CLONED| EB
    TA -->|TESTS_COMPLETED| EB
    DA -->|IMAGE_BUILT| EB
    MA -->|HEALTH_CHECK| EB
    RA -->|ROLLBACK_COMPLETED| EB

    EB --> ORC & STATE & TEL & MEM & DB
```
