# =========================================================
# ApexDeploy - Database Models
# Pydantic schemas representing DB entities for validation
# =========================================================

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RepositoryModel(BaseModel):
    id: str
    url: str
    name: str
    branch: str = "main"
    language: Optional[str] = None
    local_path: Optional[str] = None
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineRunModel(BaseModel):
    id: str
    repo_id: str
    status: str = "queued"
    trigger: str = "manual"
    current_stage: Optional[str] = None
    duration_seconds: Optional[float] = None
    context_json: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AgentResultModel(BaseModel):
    id: str
    pipeline_run_id: str
    agent_name: str
    status: str = "running"
    result_json: Optional[str] = None
    artifact_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DeploymentModel(BaseModel):
    id: str
    pipeline_run_id: str
    container_id: Optional[str] = None
    image_name: Optional[str] = None
    image_tag: Optional[str] = None
    port: Optional[int] = None
    status: str = "pending"
    deploy_type: str = "local"
    adapter_name: Optional[str] = None
    deployed_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None


class MonitoringSnapshotModel(BaseModel):
    id: str
    deployment_id: str
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    memory_percent: Optional[float] = None
    http_status: Optional[int] = None
    latency_ms: Optional[float] = None
    container_status: Optional[str] = None
    restart_count: int = 0
    health_score: Optional[float] = None
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class SecurityFindingModel(BaseModel):
    id: str
    pipeline_run_id: str
    severity: str
    category: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    description: Optional[str] = None
    recommendation: Optional[str] = None
    cwe_id: Optional[str] = None
    found_at: datetime = Field(default_factory=datetime.utcnow)


class RollbackEventModel(BaseModel):
    id: str
    deployment_id: str
    reason: Optional[str] = None
    from_image: Optional[str] = None
    to_image: Optional[str] = None
    status: str = "triggered"
    health_score_before: Optional[float] = None
    health_score_after: Optional[float] = None
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class AgentMemoryModel(BaseModel):
    id: str
    agent_name: str
    memory_type: str
    key: str
    value_json: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class EventLogModel(BaseModel):
    id: str
    event_type: str
    source_agent: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    payload_json: Optional[str] = None
    emitted_at: datetime = Field(default_factory=datetime.utcnow)
