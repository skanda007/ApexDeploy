# =========================================================
# ApexDeploy - Pipeline Event Helpers
# Standardizes publishing of pipeline events to the Event Bus
# =========================================================

import logging
from typing import Any, Dict
from src.events.event_bus import event_bus
from src.events.event_types import Event, EventType

logger = logging.getLogger("pipeline.events")


async def emit_pipeline_queued(run_id: str, repo_id: str, trigger: str) -> None:
    await event_bus.publish(
        Event(
            event_type=EventType.PIPELINE_QUEUED,
            pipeline_run_id=run_id,
            payload={"repo_id": repo_id, "trigger": trigger}
        )
    )


async def emit_pipeline_started(run_id: str, repo_id: str) -> None:
    await event_bus.publish(
        Event(
            event_type=EventType.PIPELINE_STARTED,
            pipeline_run_id=run_id,
            payload={"repo_id": repo_id}
        )
    )


async def emit_pipeline_completed(run_id: str, duration: float) -> None:
    await event_bus.publish(
        Event(
            event_type=EventType.PIPELINE_COMPLETED,
            pipeline_run_id=run_id,
            payload={"duration_seconds": duration}
        )
    )


async def emit_pipeline_failed(run_id: str, error: str) -> None:
    await event_bus.publish(
        Event(
            event_type=EventType.PIPELINE_FAILED,
            pipeline_run_id=run_id,
            payload={"error": error}
        )
    )


async def emit_stage_started(run_id: str, stage: str) -> None:
    await event_bus.publish(
        Event(
            event_type=EventType.STAGE_STARTED,
            pipeline_run_id=run_id,
            payload={"stage": stage}
        )
    )


async def emit_stage_completed(run_id: str, stage: str, duration: float) -> None:
    await event_bus.publish(
        Event(
            event_type=EventType.STAGE_COMPLETED,
            pipeline_run_id=run_id,
            payload={"stage": stage, "duration_seconds": duration}
        )
    )


async def emit_stage_failed(run_id: str, stage: str, error: str) -> None:
    await event_bus.publish(
        Event(
            event_type=EventType.STAGE_FAILED,
            pipeline_run_id=run_id,
            payload={"stage": stage, "error": error}
        )
    )
