# =========================================================
# ApexDeploy - Unit Tests for Event Bus
# Tests publishing, subscribing, unsubscribing, and global listening
# =========================================================

import pytest
from src.events.event_types import Event, EventType
from src.events.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    """Verify that subscribing and publishing to a specific event works."""
    bus = EventBus()
    received_events = []

    async def mock_handler(event: Event) -> None:
        received_events.append(event)

    # Subscribe and publish
    bus.subscribe(EventType.PIPELINE_STARTED, mock_handler)
    
    test_event = Event(
        event_type=EventType.PIPELINE_STARTED,
        source_agent="orchestrator",
        pipeline_run_id="run-123",
        payload={"info": "hello-world"}
    )
    
    await bus.publish(test_event)
    
    assert len(received_events) == 1
    assert received_events[0].id == test_event.id
    assert received_events[0].pipeline_run_id == "run-123"
    assert received_events[0].payload["info"] == "hello-world"


@pytest.mark.asyncio
async def test_event_bus_subscribe_all():
    """Verify that global subscription to all events works."""
    bus = EventBus()
    received_events = []

    async def mock_global_handler(event: Event) -> None:
        received_events.append(event)

    bus.subscribe_all(mock_global_handler)

    e1 = Event(event_type=EventType.PIPELINE_QUEUED)
    e2 = Event(event_type=EventType.STAGE_STARTED)

    await bus.publish(e1)
    await bus.publish(e2)

    assert len(received_events) == 2
    assert received_events[0].event_type == EventType.PIPELINE_QUEUED
    assert received_events[1].event_type == EventType.STAGE_STARTED


@pytest.mark.asyncio
async def test_event_bus_unsubscribe():
    """Verify that unsubscribing correctly stops event delivery."""
    bus = EventBus()
    received_events = []

    async def mock_handler(event: Event) -> None:
        received_events.append(event)

    bus.subscribe(EventType.DEPLOYMENT_RUNNING, mock_handler)
    
    e = Event(event_type=EventType.DEPLOYMENT_RUNNING)
    await bus.publish(e)
    assert len(received_events) == 1

    bus.unsubscribe(EventType.DEPLOYMENT_RUNNING, mock_handler)
    await bus.publish(e)
    assert len(received_events) == 1  # count remains 1
