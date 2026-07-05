# =========================================================
# ApexDeploy - Event Types & Schemas
# Defines the pub/sub messages for decoupled agent sync
# =========================================================

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    # Pipeline execution events
    PIPELINE_QUEUED = "pipeline.queued"
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"
    PIPELINE_CANCELLED = "pipeline.cancelled"

    # Stage execution events
    STAGE_STARTED = "stage.started"
    STAGE_COMPLETED = "stage.completed"
    STAGE_FAILED = "stage.failed"

    # Agent specific execution lifecycle
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"

    # Docker & deployment states
    DEPLOYMENT_BUILDING = "deployment.building"
    DEPLOYMENT_RUNNING = "deployment.running"
    DEPLOYMENT_STOPPED = "deployment.stopped"
    DEPLOYMENT_FAILED = "deployment.failed"
    DEPLOYMENT_ROLLED_BACK = "deployment.rolled_back"

    # Health monitoring snapshots
    MONITORING_HEALTH_CHECK = "monitoring.health_check"

    # Rollback execution lifecycle
    ROLLBACK_TRIGGERED = "rollback.triggered"
    ROLLBACK_COMPLETED = "rollback.completed"
    ROLLBACK_FAILED = "rollback.failed"


class Event(BaseModel):
    """The standard event message passed through the ApexDeploy Event Bus."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    source_agent: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
