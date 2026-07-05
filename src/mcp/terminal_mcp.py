# =========================================================
# ApexDeploy - Terminal MCP Wrapper
# Isolated asynchronous shell command execution with security gates
# =========================================================

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from src.config.settings import settings
from src.core.exceptions import MCPException

logger = logging.getLogger("mcp.terminal")

# Dangerous command keywords/patterns to block for security
DENY_LIST = [
    "sudo",
    "chmod",
    "chown",
    "rm -rf",
    "rmdir",
    "format",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "wget",
    "curl",  # Avoid external script downloads (use Python httpx instead)
    "chsh",
    "passwd",
]


def _check_security(command: str) -> None:
    """Verifies that the command does not contain dangerous commands or directory escapes.

    Args:
        command: Command string to run.

    Raises:
        MCPException: If the command is denied.
    """
    clean_command = command.strip().lower()
    
    # Check blacklist keywords
    for pattern in DENY_LIST:
        if pattern in clean_command:
            raise MCPException(
                f"Security block: Command '{command}' contains forbidden keyword/pattern '{pattern}'",
                details={"command": command, "violation": pattern}
            )


async def execute_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 60,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Executes a terminal command asynchronously with timeout and security screening.

    Args:
        command: The command line to run in the system shell.
        cwd: Directory where the command should execute (resolves to absolute path).
        timeout: Time limit in seconds before the command is terminated.
        env: Dict of environment variables to supply to the command.

    Returns:
        Dict containing exit_code, stdout, stderr, and duration_seconds.

    Raises:
        MCPException: If security checks fail or process spawning encounters failures.
    """
    _check_security(command)
    
    # Resolve directory path safely
    resolved_cwd = None
    if cwd:
        workspace_root = settings.workspaces_path.resolve()
        from pathlib import Path
        p = Path(cwd)
        if not p.is_absolute():
            p = workspace_root / p
        resolved_cwd = str(p.resolve())
        
        # Verify target cwd is within workspaces to avoid escapes
        try:
            Path(resolved_cwd).relative_to(workspace_root)
        except ValueError:
            raise MCPException(
                f"Security block: cwd '{cwd}' resolves outside workspaces directory.",
                details={"cwd": cwd, "resolved": resolved_cwd}
            )

    logger.info(f"Executing command: '{command}' in cwd: {resolved_cwd or 'default'}")
    
    start_time = time.perf_counter()
    process = None
    
    try:
        # Spawn asynchronous shell subprocess
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=resolved_cwd,
            env=env
        )
        
        # Wait for command completion or timeout
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=float(timeout)
            )
        except asyncio.TimeoutError:
            # Terminate and kill hanging process
            logger.warning(f"Command '{command}' timed out after {timeout} seconds. Terminating.")
            try:
                process.terminate()
                await process.wait()
            except Exception as e:
                logger.error(f"Failed to terminate timed out process: {e}")
            
            duration = time.perf_counter() - start_time
            return {
                "exit_code": -9,  # Standard SIGKILL code representation
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds.",
                "duration_seconds": duration,
                "timeout_exceeded": True
            }
            
        duration = time.perf_counter() - start_time
        
        # Decode output
        stdout = stdout_bytes.decode(encoding="utf-8", errors="replace")
        stderr = stderr_bytes.decode(encoding="utf-8", errors="replace")
        
        return {
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_seconds": duration,
            "timeout_exceeded": False
        }
        
    except Exception as e:
        logger.error(f"Spawning terminal process failed: {e}", exc_info=True)
        raise MCPException(f"Failed to execute command '{command}': {e}") from e
