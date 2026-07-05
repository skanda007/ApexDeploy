# =========================================================
# ApexDeploy - File Utilities
# Helper methods for basic file I/O operations
# =========================================================

import logging
import shutil
from pathlib import Path

logger = logging.getLogger("utils.file_utils")


def ensure_dir(directory_path: str) -> Path:
    """Ensures that a directory exists, creating it if necessary.

    Args:
        directory_path: Absolute or relative path to the directory.

    Returns:
        Path object of the directory.
    """
    path = Path(directory_path)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created directory: {path}")
    return path


def delete_dir(directory_path: str) -> bool:
    """Recursively deletes a directory if it exists.

    Args:
        directory_path: Path to the directory.

    Returns:
        True if deleted or didn't exist, False if failed.
    """
    path = Path(directory_path)
    if path.exists():
        try:
            shutil.rmtree(path, ignore_errors=True)
            logger.debug(f"Deleted directory: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete directory {path}: {e}")
            return False
    return True


def write_text(file_path: str, content: str) -> bool:
    """Writes text content to a file.

    Args:
        file_path: Path to the file.
        content: Text content to write.

    Returns:
        True if successful, False otherwise.
    """
    path = Path(file_path)
    try:
        ensure_dir(str(path.parent))
        path.write_text(content, encoding="utf-8")
        logger.debug(f"Wrote file: {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write file {path}: {e}")
        return False


def read_text(file_path: str) -> str:
    """Reads text content from a file.

    Args:
        file_path: Path to the file.

    Returns:
        File contents as a string or empty string on failure.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read file {path}: {e}")
        return ""
