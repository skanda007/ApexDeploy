# =========================================================
# ApexDeploy - Logging Configuration
# Dynamic configuration using standard logging + Rich
# =========================================================

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from rich.logging import RichHandler
from src.config.settings import settings


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines for structured log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logging():
    """Sets up primary root logging with Console (Rich) and Rotating File handlers."""
    log_level_name = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Ensure log directory exists
    logs_dir = Path(settings.LOG_DIR)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Main log file path
    main_log_file = logs_dir / "apexdeploy.log"

    # Root Logger Config
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates on hot-reloading
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 1. Console Handler (using Rich for premium CLI aesthetics)
    console_handler = RichHandler(
        level=log_level,
        rich_tracebacks=True,
        markup=True,
        omit_repeated_times=False
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # 2. Main File Handler (standard rotating handler)
    max_bytes = settings.LOG_MAX_SIZE_MB * 1024 * 1024
    file_handler = RotatingFileHandler(
        filename=main_log_file,
        maxBytes=max_bytes,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    
    if settings.LOG_FORMAT.lower() == "json":
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] - %(message)s"
            )
        )
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)

    # Set external libraries log levels to keep logs clean
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_agent_logger(agent_name: str) -> logging.Logger:
    """Returns a logger dedicated to a specific agent, writing to its own file."""
    logger = logging.getLogger(f"agent.{agent_name}")
    
    # Avoid duplicate handlers if logger was already created
    if logger.handlers:
        return logger

    # Ensure agent log directory exists
    agent_log_dir = Path(settings.LOG_DIR) / "agents"
    agent_log_dir.mkdir(parents=True, exist_ok=True)
    agent_log_file = agent_log_dir / f"{agent_name}.log"

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    logger.propagate = True  # Propagate to root logger (so console gets agent logs too)

    # Specific file handler for the agent
    max_bytes = settings.LOG_MAX_SIZE_MB * 1024 * 1024
    file_handler = RotatingFileHandler(
        filename=agent_log_file,
        maxBytes=max_bytes,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    
    if settings.LOG_FORMAT.lower() == "json":
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s"
            )
        )
    file_handler.setLevel(log_level)
    logger.addHandler(file_handler)

    return logger
