# =========================================================
# ApexDeploy - Pipeline Context
# Represents the context dictionary/state for a pipeline run
# =========================================================

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PipelineContext(BaseModel):
    """The shared state schema carried across pipeline stages and agents."""
    pipeline_run_id: str
    repo_id: str
    repo_url: str
    branch: str = "main"
    
    # Paths configured for the run
    workspace_path: Optional[str] = None
    artifacts_path: Optional[str] = None
    
    # Language identified
    language: Optional[str] = None
    
    # Build & Containerization Outputs
    docker_image_name: Optional[str] = None
    docker_image_tag: Optional[str] = None
    container_id: Optional[str] = None
    deployment_port: Optional[int] = None
    
    # Sub-agent intermediate and final results
    git_metadata: Dict[str, Any] = Field(default_factory=dict)
    git_results: Dict[str, Any] = Field(default_factory=dict)
    code_review_results: Dict[str, Any] = Field(default_factory=dict)
    testing_results: Dict[str, Any] = Field(default_factory=dict)
    security_results: Dict[str, Any] = Field(default_factory=dict)
    docker_results: Dict[str, Any] = Field(default_factory=dict)
    deployment_results: Dict[str, Any] = Field(default_factory=dict)
    monitoring_results: Dict[str, Any] = Field(default_factory=dict)
    rollback_results: Dict[str, Any] = Field(default_factory=dict)
    
    # Global state tracking
    status: str = "queued"  # queued, running, passed, failed, cancelled
    current_stage: Optional[str] = None
    error_message: Optional[str] = None
    
    # Execution Metrics
    duration_seconds: float = 0.0
    agent_durations: Dict[str, float] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True
