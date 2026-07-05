# =========================================================
# ApexDeploy - Event Handlers
# Handles events dispatched by the Event Bus (e.g. database logging)
# =========================================================

import json
import logging
from src.events.event_types import Event
from src.db.database import get_db_connection

logger = logging.getLogger("events.handlers")


async def db_event_logger_handler(event: Event) -> None:
    """Asynchronous handler that logs all system events to the database."""
    logger.debug(f"Persisting event {event.event_type} to database.")
    try:
        payload_str = json.dumps(event.payload)
        
        async with get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO event_log (
                    id, event_type, source_agent, pipeline_run_id, payload_json, emitted_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.event_type.value if hasattr(event.event_type, "value") else event.event_type,
                    event.source_agent,
                    event.pipeline_run_id,
                    payload_str,
                    event.timestamp.isoformat()
                )
            )
            await conn.commit()
            
    except Exception as e:
        logger.error(f"Failed to persist event {event.id} to SQLite event_log: {e}", exc_info=True)


def register_core_event_handlers() -> None:
    """Registers standard cross-cutting event handlers to the Event Bus."""
    from src.events.event_bus import event_bus
    
    # Register the db persistent logging handler globally to all events
    event_bus.subscribe_all(db_event_logger_handler)
    logger.info("Core event handlers registered to Event Bus.")
