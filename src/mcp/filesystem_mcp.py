# =========================================================
# ApexDeploy - Filesystem MCP Wrapper
# Sandboxed file I/O tools for agent consumption
# =========================================================

import fnmatch
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.settings import settings
from src.core.exceptions import MCPException

logger = logging.getLogger("mcp.filesystem")

# Maximum file size for read operations (1 MB)
MAX_READ_SIZE_BYTES = 1_048_576


def _resolve_safe_path(filepath: str) -> Path:
    """Resolves a path and ensures it falls within the allowed workspaces or artifacts directories.

    This prevents directory traversal attacks outside authorized application paths.

    Args:
        filepath: Relative or absolute path to validate.

    Returns:
        Resolved absolute Path object.

    Raises:
        MCPException: If the path escapes both allowed sandboxes.
    """
    workspace_sandbox = settings.workspaces_path.resolve()
    artifacts_sandbox = settings.artifacts_path.resolve()
    
    workspace_sandbox.mkdir(parents=True, exist_ok=True)
    artifacts_sandbox.mkdir(parents=True, exist_ok=True)

    target = Path(filepath)
    
    # Anchor relative paths
    if not target.is_absolute():
        # Normalize by converting to posix-style string and stripping leading './'
        normalized = filepath.replace("\\", "/").lstrip("./")
        if normalized.startswith("artifacts/") or normalized == "artifacts":
            # Route to artifacts sandbox, stripping the 'artifacts' prefix
            remainder = normalized[len("artifacts"):].lstrip("/")
            target = artifacts_sandbox / remainder if remainder else artifacts_sandbox
        else:
            target = workspace_sandbox / target
            
    target = target.resolve()

    # Security check: target must resolve to either workspace_sandbox or artifacts_sandbox
    in_workspace = False
    try:
        target.relative_to(workspace_sandbox)
        in_workspace = True
    except ValueError:
        pass

    in_artifacts = False
    try:
        target.relative_to(artifacts_sandbox)
        in_artifacts = True
    except ValueError:
        pass

    if not in_workspace and not in_artifacts:
        raise MCPException(
            f"Path traversal blocked: '{filepath}' resolves outside allowed sandboxes ('{workspace_sandbox}' and '{artifacts_sandbox}')",
            details={
                "filepath": filepath,
                "resolved": str(target),
                "workspace_sandbox": str(workspace_sandbox),
                "artifacts_sandbox": str(artifacts_sandbox)
            }
        )

    return target


def read_file(filepath: str) -> str:
    """Reads and returns the text content of a file inside the workspace sandbox.

    Args:
        filepath: Path to the file (relative to workspaces or absolute).

    Returns:
        File contents as a UTF-8 string.

    Raises:
        MCPException: If the file doesn't exist, is too large, or is outside the sandbox.
    """
    target = _resolve_safe_path(filepath)

    if not target.exists():
        raise MCPException(f"File not found: {target}")
    if not target.is_file():
        raise MCPException(f"Path is not a regular file: {target}")

    size = target.stat().st_size
    if size > MAX_READ_SIZE_BYTES:
        raise MCPException(
            f"File too large to read: {size:,} bytes (limit: {MAX_READ_SIZE_BYTES:,})",
            details={"filepath": str(target), "size_bytes": size},
        )

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        logger.debug(f"Read {len(content)} chars from {target}")
        return content
    except Exception as e:
        raise MCPException(f"Failed to read file '{target}': {e}") from e


def write_file(filepath: str, content: str) -> str:
    """Writes text content to a file inside the workspace sandbox.

    Creates parent directories automatically if they don't exist.

    Args:
        filepath: Destination path (relative to workspaces or absolute).
        content: Text content to write.

    Returns:
        Confirmation message with the absolute path written to.

    Raises:
        MCPException: If the path is outside the sandbox or write fails.
    """
    target = _resolve_safe_path(filepath)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info(f"Wrote {len(content)} chars to {target}")
        return f"Successfully wrote {len(content)} characters to {target}"
    except Exception as e:
        raise MCPException(f"Failed to write file '{target}': {e}") from e


def list_directory(dir_path: str, max_depth: int = 3) -> List[Dict[str, Any]]:
    """Lists files and subdirectories within a sandboxed directory.

    Args:
        dir_path: Directory path (relative to workspaces or absolute).
        max_depth: Maximum recursion depth (default 3 to prevent runaway listings).

    Returns:
        List of dicts with keys: name, path, is_dir, size_bytes, modified.

    Raises:
        MCPException: If the path is outside sandbox or isn't a directory.
    """
    target = _resolve_safe_path(dir_path)

    if not target.exists():
        raise MCPException(f"Directory not found: {target}")
    if not target.is_dir():
        raise MCPException(f"Path is not a directory: {target}")

    entries: List[Dict[str, Any]] = []

    def _walk(current: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            for item in sorted(current.iterdir()):
                # Skip hidden files/dirs and __pycache__
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size_bytes": stat.st_size if item.is_file() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
                if item.is_dir():
                    _walk(item, depth + 1)
        except PermissionError:
            logger.warning(f"Permission denied listing: {current}")

    _walk(target, 1)
    logger.debug(f"Listed {len(entries)} entries from {target}")
    return entries


def file_info(filepath: str) -> Dict[str, Any]:
    """Returns metadata about a single file.

    Args:
        filepath: Path to the file.

    Returns:
        Dict with keys: name, path, size_bytes, extension, modified, lines (if text).
    """
    target = _resolve_safe_path(filepath)

    if not target.exists():
        raise MCPException(f"File not found: {target}")

    stat = target.stat()
    info: Dict[str, Any] = {
        "name": target.name,
        "path": str(target),
        "size_bytes": stat.st_size,
        "extension": target.suffix,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "is_dir": target.is_dir(),
    }

    # Count lines for small text files
    if target.is_file() and stat.st_size <= MAX_READ_SIZE_BYTES:
        try:
            info["lines"] = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            info["lines"] = None
    else:
        info["lines"] = None

    return info


def search_files(dir_path: str, pattern: str = "*") -> List[str]:
    """Searches for files matching a glob pattern inside a sandboxed directory.

    Args:
        dir_path: Root directory to search from.
        pattern: Glob pattern (e.g. '*.py', 'test_*', '**/*.json').

    Returns:
        List of matching file paths as strings.
    """
    target = _resolve_safe_path(dir_path)

    if not target.exists() or not target.is_dir():
        raise MCPException(f"Search directory not found or not a directory: {target}")

    matches = [str(p) for p in target.rglob(pattern) if p.is_file()]
    logger.debug(f"Search '{pattern}' in {target} found {len(matches)} files")
    return matches
