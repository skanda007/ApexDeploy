# =========================================================
# ApexDeploy - MCP Wrappers Package Entry Point
# Exports all agent-ready tools for local & remote system access
# =========================================================

from src.mcp.filesystem_mcp import (
    read_file,
    write_file,
    list_directory,
    file_info,
    search_files,
)
from src.mcp.git_mcp import (
    git_clone,
    git_log,
    git_branches,
    git_diff,
    git_changed_files,
)
from src.mcp.github_mcp import (
    get_repo_info,
    get_repo_languages,
    get_latest_commits,
    get_repo_contents,
)
from src.mcp.terminal_mcp import (
    execute_command,
)

__all__ = [
    # Filesystem tools
    "read_file",
    "write_file",
    "list_directory",
    "file_info",
    "search_files",
    
    # Git tools
    "git_clone",
    "git_log",
    "git_branches",
    "git_diff",
    "git_changed_files",
    
    # GitHub tools
    "get_repo_info",
    "get_repo_languages",
    "get_latest_commits",
    "get_repo_contents",
    
    # Terminal tools
    "execute_command",
]
