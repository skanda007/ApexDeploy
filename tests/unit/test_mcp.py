# =========================================================
# ApexDeploy - Unit Tests for MCP Wrappers
# Tests filesystem, git, github, and terminal tools including security gates
# =========================================================

import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.config.settings import settings
from src.core.exceptions import MCPException
from src.mcp.filesystem_mcp import (
    file_info,
    list_directory,
    read_file,
    search_files,
    write_file,
)
from src.mcp.git_mcp import (
    git_branches,
    git_changed_files,
    git_clone,
    git_diff,
    git_log,
)
from src.mcp.github_mcp import (
    get_latest_commits,
    get_repo_contents,
    get_repo_info,
    get_repo_languages,
)
from src.mcp.terminal_mcp import execute_command


@pytest.fixture(autouse=True)
def setup_test_workspaces(monkeypatch, tmp_path):
    """Overrides workspace settings to point to a temporary folder for I/O safety."""
    test_workspaces_dir = tmp_path / "workspaces"
    test_workspaces_dir.mkdir()
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(test_workspaces_dir))
    return test_workspaces_dir


# =========================================================
# FILESYSTEM MCP TESTS
# =========================================================

def test_filesystem_read_write_flow():
    """Verify writing then reading a file inside the sandboxed workspace."""
    filepath = "project-1/src/main.py"
    content = "print('hello world')"
    
    # Write file
    write_msg = write_file(filepath, content)
    assert "Successfully wrote" in write_msg
    
    # Read file
    read_content = read_file(filepath)
    assert read_content == content


def test_filesystem_directory_and_search():
    """Verify recursive folder listing and pattern search."""
    write_file("app/index.js", "console.log('test')")
    write_file("app/utils/helper.js", "export const help = () => {}")
    write_file("app/config.json", "{}")
    
    # List Directory
    entries = list_directory("app")
    names = {e["name"] for e in entries}
    assert "index.js" in names
    assert "config.json" in names
    assert "utils" in names
    
    # Search Files
    js_files = search_files("app", "**/*.js")
    assert len(js_files) == 2
    assert any("index.js" in f for f in js_files)
    assert any("helper.js" in f for f in js_files)


def test_filesystem_file_info():
    """Verify file metadata extraction works."""
    write_file("info.txt", "line1\nline2\nline3")
    info = file_info("info.txt")
    
    assert info["name"] == "info.txt"
    assert info["size_bytes"] > 0
    assert info["lines"] == 3
    assert info["extension"] == ".txt"
    assert info["is_dir"] is False


def test_filesystem_path_traversal_protection():
    """Verify that path traversal attempts raise MCPException."""
    # Attempt absolute paths resolving outside sandbox
    with pytest.raises(MCPException) as excinfo:
        read_file("/etc/passwd")
    assert "Path traversal blocked" in str(excinfo.value)

    # Attempt relative path escapes
    with pytest.raises(MCPException) as excinfo:
        write_file("../escape.txt", "malicious data")
    assert "Path traversal blocked" in str(excinfo.value)


# =========================================================
# GIT MCP TESTS
# =========================================================

@patch("git.Repo.clone_from")
def test_git_clone_wrapper(mock_clone, setup_test_workspaces):
    """Verify Git clone initializes settings and returns commit details."""
    mock_repo_inst = MagicMock()
    mock_head = MagicMock()
    mock_commit = MagicMock()
    
    mock_commit.hexsha = "abcdef1234567890abcdef1234567890abcdef12"
    mock_commit.message = "Initial commit\n"
    mock_commit.author = "Test Author"
    mock_commit.committed_date = 1719600000  # Unix timestamp
    
    mock_head.commit = mock_commit
    mock_repo_inst.head = mock_head
    mock_clone.return_value = mock_repo_inst
    
    res = git_clone("https://github.com/user/repo.git", "target-repo")
    
    assert res["status"] == "success"
    assert "target-repo" in res["path"]
    assert res["commit_sha"] == mock_commit.hexsha
    assert res["commit_message"] == "Initial commit"


@patch("src.mcp.git_mcp._open_repo")
def test_git_operations(mock_open_repo):
    """Verify git log, git branches, and git diff wrappers call local GitPython methods."""
    mock_repo = MagicMock()
    
    # Mock Log Commit
    mock_commit = MagicMock()
    mock_commit.hexsha = "abcdef12"
    mock_author = MagicMock()
    mock_author.__str__.return_value = "Developer"
    mock_author.email = "dev@test.com"
    mock_commit.author = mock_author
    mock_commit.committed_date = 1719600000
    mock_commit.message = "Commit test message"
    
    mock_repo.iter_commits.return_value = [mock_commit]
    
    # Mock Branches
    mock_branch = MagicMock()
    mock_branch.name = "main"
    mock_repo.branches = [mock_branch]
    mock_repo.remotes = []
    
    # Mock Diff
    mock_repo.git.diff.return_value = "diff --git a/file b/file"
    
    mock_open_repo.return_value = mock_repo
    
    # Run log
    commits = git_log("dummy-path", limit=1)
    assert len(commits) == 1
    assert commits[0]["sha"] == "abcdef12"
    
    # Run branches
    branches = git_branches("dummy-path")
    assert branches == ["main"]
    
    # Run diff
    diff = git_diff("dummy-path")
    assert "diff" in diff


# =========================================================
# GITHUB MCP TESTS
# =========================================================

@patch("httpx.request")
def test_github_repo_info(mock_request):
    """Verify GitHub repository info fetching parses HTTP payloads correctly."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "project",
        "full_name": "owner/project",
        "description": "A test project",
        "stargazers_count": 42,
        "forks_count": 5,
        "default_branch": "main",
        "clone_url": "https://github.com/owner/project.git"
    }
    mock_request.return_value = mock_response
    
    info = get_repo_info("owner", "project")
    
    assert info["name"] == "project"
    assert info["stars"] == 42
    assert info["default_branch"] == "main"


@patch("httpx.request")
def test_github_repo_languages(mock_request):
    """Verify GitHub language analysis wrapper returns mapped counts."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"Python": 12000, "HTML": 350}
    mock_request.return_value = mock_response
    
    langs = get_repo_languages("owner", "project")
    assert langs == {"Python": 12000, "HTML": 350}


# =========================================================
# TERMINAL MCP TESTS
# =========================================================

@pytest.mark.asyncio
async def test_terminal_execute_command():
    """Verify safe terminal commands run successfully and return output."""
    # Echo command works across Windows/Linux shell
    res = await execute_command("echo hello")
    
    assert res["exit_code"] == 0
    assert "hello" in res["stdout"].strip().lower()
    assert res["timeout_exceeded"] is False


@pytest.mark.asyncio
async def test_terminal_command_timeout():
    """Verify command timeouts terminate hung processes."""
    # Sleep/ping commands run infinitely or take time
    # Windows: ping 127.0.0.1 -n 10
    # Linux: sleep 10
    import sys
    cmd = "ping 127.0.0.1 -n 10" if sys.platform == "win32" else "sleep 10"
    
    res = await execute_command(cmd, timeout=1)
    
    assert res["exit_code"] == -9
    assert "timed out" in res["stderr"].lower()
    assert res["timeout_exceeded"] is True


@pytest.mark.asyncio
async def test_terminal_security_block():
    """Verify that blacklisted terminal command words raise exceptions."""
    with pytest.raises(MCPException) as excinfo:
        await execute_command("rm -rf /")
    assert "Security block" in str(excinfo.value)
    
    with pytest.raises(MCPException) as excinfo:
        await execute_command("sudo apt update")
    assert "Security block" in str(excinfo.value)
