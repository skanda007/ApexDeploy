-- =========================================================
-- ApexDeploy - Initial Database Schema
-- Version: 001
-- =========================================================

-- Repositories table
CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    name TEXT NOT NULL,
    branch TEXT DEFAULT 'main',
    language TEXT,
    local_path TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pipeline runs table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repositories(id),
    status TEXT DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'passed', 'failed', 'cancelled')),
    trigger TEXT DEFAULT 'manual' CHECK (trigger IN ('manual', 'webhook', 'scheduled')),
    current_stage TEXT,
    duration_seconds REAL,
    context_json TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Agent results table
CREATE TABLE IF NOT EXISTS agent_results (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
    agent_name TEXT NOT NULL CHECK (agent_name IN (
        'git', 'code_review', 'testing', 'security',
        'docker', 'deployment', 'monitoring', 'rollback'
    )),
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'skipped')),
    result_json TEXT,
    artifact_path TEXT,
    duration_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Deployments table
CREATE TABLE IF NOT EXISTS deployments (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
    container_id TEXT,
    image_name TEXT,
    image_tag TEXT,
    port INTEGER,
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'building', 'running', 'stopped', 'failed', 'rolled_back'
    )),
    deploy_type TEXT DEFAULT 'local' CHECK (deploy_type IN ('local', 'docker')),
    adapter_name TEXT,
    deployed_at TIMESTAMP,
    stopped_at TIMESTAMP
);

-- Monitoring snapshots table
CREATE TABLE IF NOT EXISTS monitoring_snapshots (
    id TEXT PRIMARY KEY,
    deployment_id TEXT NOT NULL REFERENCES deployments(id),
    cpu_percent REAL,
    memory_mb REAL,
    memory_percent REAL,
    http_status INTEGER,
    latency_ms REAL,
    container_status TEXT,
    restart_count INTEGER DEFAULT 0,
    health_score REAL,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Security findings table
CREATE TABLE IF NOT EXISTS security_findings (
    id TEXT PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id),
    severity TEXT CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    category TEXT CHECK (category IN ('bandit', 'secrets', 'dependencies', 'config')),
    file_path TEXT,
    line_number INTEGER,
    description TEXT,
    recommendation TEXT,
    cwe_id TEXT,
    found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rollback events table
CREATE TABLE IF NOT EXISTS rollback_events (
    id TEXT PRIMARY KEY,
    deployment_id TEXT NOT NULL REFERENCES deployments(id),
    reason TEXT,
    from_image TEXT,
    to_image TEXT,
    status TEXT DEFAULT 'triggered' CHECK (status IN ('triggered', 'completed', 'failed')),
    health_score_before REAL,
    health_score_after REAL,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Agent memory table
CREATE TABLE IF NOT EXISTS agent_memory (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    memory_type TEXT CHECK (memory_type IN ('session', 'pipeline', 'deployment')),
    key TEXT NOT NULL,
    value_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- Event log table
CREATE TABLE IF NOT EXISTS event_log (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source_agent TEXT,
    pipeline_run_id TEXT REFERENCES pipeline_runs(id),
    payload_json TEXT,
    emitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- Indexes for query performance
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_repo_id ON pipeline_runs(repo_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_agent_results_pipeline ON agent_results(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_agent_results_name ON agent_results(agent_name);
CREATE INDEX IF NOT EXISTS idx_deployments_pipeline ON deployments(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_monitoring_deployment ON monitoring_snapshots(deployment_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_captured ON monitoring_snapshots(captured_at);
CREATE INDEX IF NOT EXISTS idx_security_pipeline ON security_findings(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_security_severity ON security_findings(severity);
CREATE INDEX IF NOT EXISTS idx_rollback_deployment ON rollback_events(deployment_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent ON agent_memory(agent_name);
CREATE INDEX IF NOT EXISTS idx_memory_key ON agent_memory(key);
CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_pipeline ON event_log(pipeline_run_id);
