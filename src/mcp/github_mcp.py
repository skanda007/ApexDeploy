# =========================================================
# ApexDeploy - GitHub MCP Wrapper
# GitHub REST API v3 tool interfaces via httpx
# =========================================================

import logging
from typing import Any, Dict, List, Optional

import httpx

from src.config.settings import settings
from src.core.exceptions import MCPException

logger = logging.getLogger("mcp.github")

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 15  # seconds


def _get_headers() -> Dict[str, str]:
    """Builds request headers, including auth token if configured."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ApexDeploy/1.0",
    }
    token = settings.GITHUB_TOKEN
    if token:
        headers["Authorization"] = f"token {token}"
        logger.debug("Using authenticated GitHub API requests")
    else:
        logger.debug("Using unauthenticated GitHub API requests (lower rate limits)")
    return headers


def _make_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """Executes an HTTP request against the GitHub API.

    Args:
        method: HTTP method (GET, POST, etc.).
        endpoint: API endpoint path (e.g., /repos/owner/name).
        params: Optional query parameters.

    Returns:
        Parsed JSON response body.

    Raises:
        MCPException: On HTTP errors or network failures.
    """
    url = f"{GITHUB_API_BASE}{endpoint}"
    headers = _get_headers()

    try:
        response = httpx.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )

        if response.status_code == 404:
            raise MCPException(
                f"GitHub resource not found: {endpoint}",
                details={"url": url, "status": 404},
            )
        if response.status_code == 403:
            raise MCPException(
                "GitHub API rate limit exceeded or access denied. "
                "Set GITHUB_TOKEN in .env for higher limits.",
                details={"url": url, "status": 403},
            )
        if response.status_code >= 400:
            raise MCPException(
                f"GitHub API error ({response.status_code}): {response.text[:200]}",
                details={"url": url, "status": response.status_code},
            )

        return response.json()

    except httpx.TimeoutException:
        raise MCPException(
            f"GitHub API request timed out after {DEFAULT_TIMEOUT}s: {endpoint}",
            details={"endpoint": endpoint},
        )
    except httpx.RequestError as e:
        raise MCPException(f"GitHub API network error: {e}") from e


def get_repo_info(owner: str, repo: str) -> Dict[str, Any]:
    """Fetches general metadata about a GitHub repository.

    Args:
        owner: Repository owner (user or org).
        repo: Repository name.

    Returns:
        Dict with: name, full_name, description, language, default_branch,
        stars, forks, open_issues, created_at, updated_at, clone_url.
    """
    logger.info(f"Fetching repo info for {owner}/{repo}")
    data = _make_request("GET", f"/repos/{owner}/{repo}")

    return {
        "name": data.get("name"),
        "full_name": data.get("full_name"),
        "description": data.get("description") or "",
        "language": data.get("language"),
        "default_branch": data.get("default_branch", "main"),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "open_issues": data.get("open_issues_count", 0),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "clone_url": data.get("clone_url"),
        "private": data.get("private", False),
        "size_kb": data.get("size", 0),
    }


def get_repo_languages(owner: str, repo: str) -> Dict[str, int]:
    """Fetches the language breakdown for a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.

    Returns:
        Dict mapping language names to byte counts (e.g., {"Python": 45230, "Shell": 1200}).
    """
    logger.info(f"Fetching languages for {owner}/{repo}")
    data = _make_request("GET", f"/repos/{owner}/{repo}/languages")
    return data


def get_latest_commits(
    owner: str,
    repo: str,
    limit: int = 5,
    branch: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetches the most recent commits from a GitHub repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        limit: Number of commits to fetch (max 30).
        branch: Branch/ref to query (default: repo's default branch).

    Returns:
        List of commit dicts with: sha, author, date, message.
    """
    logger.info(f"Fetching latest {limit} commits for {owner}/{repo}")
    params: Dict[str, Any] = {"per_page": min(limit, 30)}
    if branch:
        params["sha"] = branch

    data = _make_request("GET", f"/repos/{owner}/{repo}/commits", params=params)

    commits = []
    for item in data:
        commit_data = item.get("commit", {})
        author = commit_data.get("author", {})
        commits.append({
            "sha": item.get("sha"),
            "short_sha": item.get("sha", "")[:8],
            "author": author.get("name", "Unknown"),
            "email": author.get("email", ""),
            "date": author.get("date"),
            "message": commit_data.get("message", "").strip(),
        })

    return commits


def get_repo_contents(
    owner: str,
    repo: str,
    path: str = "",
    ref: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lists files and directories at a path in a GitHub repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        path: Path inside the repository (default: root).
        ref: Branch or commit ref to query.

    Returns:
        List of dicts with: name, path, type (file/dir), size, download_url.
    """
    logger.info(f"Fetching contents for {owner}/{repo}/{path}")
    endpoint = f"/repos/{owner}/{repo}/contents/{path}"
    params = {}
    if ref:
        params["ref"] = ref

    data = _make_request("GET", endpoint, params=params or None)

    # GitHub returns a single object for files, a list for directories
    if isinstance(data, dict):
        data = [data]

    contents = []
    for item in data:
        contents.append({
            "name": item.get("name"),
            "path": item.get("path"),
            "type": item.get("type"),  # "file" or "dir"
            "size": item.get("size", 0),
            "download_url": item.get("download_url"),
        })

    return contents
