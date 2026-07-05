# =========================================================
# ApexDeploy - Event Bus
# In-process asynchronous publish-subscribe message broker
# =========================================================

import asyncio
import logging
from typing import Callable, Dict, List, Set, Awaitable
from src.events.event_types import Event, EventType

logger = logging.getLogger("events.bus")


class EventBus:
    """An asynchronous in-process event bus for decoupled communication between
    agents and system components.
    """

    def __init__(self):
        self._subscribers: Dict[EventType, Set[Callable[[Event], Awaitable[None]]]] = {}
        self._all_subscribers: Set[Callable[[Event], Awaitable[None]]] = set()

    def subscribe(self, event_type: EventType, callback: Callable[[Event], Awaitable[None]]) -> None:
        """Subscribes an async callback to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        self._subscribers[event_type].add(callback)
        logger.debug(f"Subscribed handler to event type: {event_type.value}")

    def subscribe_all(self, callback: Callable[[Event], Awaitable[None]]) -> None:
        """Subscribes an async callback to all event publications (e.g., for logging/telemetry)."""
        self._all_subscribers.add(callback)
        logger.debug("Subscribed handler globally to all events")

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], Awaitable[None]]) -> None:
        """Unsubscribes an async callback from a specific event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(callback)

    def unsubscribe_all(self, callback: Callable[[Event], Awaitable[None]]) -> None:
        """Unsubscribes an async callback from all event publications."""
        self._all_subscribers.discard(callback)

    async def publish(self, event: Event) -> None:
        """Publishes an event to all interested subscribers concurrently."""
        logger.info(f"Publishing event [{event.event_type}] from source: {event.source_agent or 'system'}")
        
        # Combine target handlers
        handlers = set(self._all_subscribers)
        if event.event_type in self._subscribers:
            handlers.update(self._subscribers[event.event_type])

        if not handlers:
            logger.debug(f"No handlers registered for event: {event.event_type}")
            return

        # Helper to execute a handler and catch exceptions to prevent cascading failures
        async def call_handler(handler: Callable[[Event], Awaitable[None]]):
            try:
                await handler(event)
            except Exception as ex:
                logger.error(
                    f"Error in event handler {handler.__name__} processing event {event.event_type}: {ex}",
                    exc_info=True
                )

        # Run all handlers concurrently
        tasks = [asyncio.create_task(call_handler(h)) for h in handlers]
        await asyncio.gather(*tasks)


# Global singleton instance
event_bus = EventBus()
