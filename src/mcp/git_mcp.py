# =========================================================
# ApexDeploy - Git MCP Wrapper
# Local Git repository operations via GitPython
# =========================================================

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from git import GitCommandError, InvalidGitRepositoryError, Repo

from src.config.settings import settings
from src.core.exceptions import MCPException

logger = logging.getLogger("mcp.git")


def git_clone(
    repo_url: str,
    target_dir: str,
    branch: str = "main",
    depth: Optional[int] = None,
) -> Dict[str, Any]:
    """Clones a Git repository into the workspace sandbox.

    Args:
        repo_url: HTTPS URL of the repository to clone.
        target_dir: Destination directory name (relative to workspaces).
        branch: Branch to checkout (default: 'main').
        depth: Shallow clone depth. None for full clone, 1 for latest only.

    Returns:
        Dict with clone results: path, branch, commit_sha, commit_message.

    Raises:
        MCPException: If the clone fails or the URL is invalid.
    """
    workspace_root = settings.workspaces_path.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    clone_path = (workspace_root / target_dir).resolve()

    # Verify the clone target stays inside the sandbox
    try:
        clone_path.relative_to(workspace_root)
    except ValueError:
        raise MCPException(
            f"Clone target escapes workspace sandbox: {clone_path}",
            details={"target_dir": target_dir, "sandbox": str(workspace_root)},
        )

    # Remove existing directory if present (re-clone scenario)
    if clone_path.exists():
        logger.info(f"Removing existing clone directory: {clone_path}")
        shutil.rmtree(clone_path, ignore_errors=True)

    clone_depth = depth if depth is not None else settings.GIT_CLONE_DEPTH

    logger.info(f"Cloning {repo_url} (branch={branch}, depth={clone_depth}) -> {clone_path}")
    try:
        clone_kwargs: Dict[str, Any] = {
            "branch": branch,
            "single_branch": True,
        }
        if clone_depth and clone_depth > 0:
            clone_kwargs["depth"] = clone_depth

        try:
            repo = Repo.clone_from(
                repo_url,
                str(clone_path),
                **clone_kwargs,
            )
        except GitCommandError as e:
            logger.warning(f"Git clone for branch '{branch}' failed. Retrying with remote default branch... Error: {e}")
            if clone_path.exists():
                shutil.rmtree(clone_path, ignore_errors=True)
            
            clone_kwargs_fallback: Dict[str, Any] = {}
            if clone_depth and clone_depth > 0:
                clone_kwargs_fallback["depth"] = clone_depth
                
            repo = Repo.clone_from(
                repo_url,
                str(clone_path),
                **clone_kwargs_fallback,
            )
            try:
                branch = repo.active_branch.name
            except Exception:
                # If active_branch is detached or not named, fallback to head commit info
                branch = "HEAD"

        head_commit = repo.head.commit
        result = {
            "status": "success",
            "path": str(clone_path),
            "branch": branch,
            "commit_sha": head_commit.hexsha,
            "commit_message": head_commit.message.strip(),
            "commit_author": str(head_commit.author),
            "commit_date": datetime.fromtimestamp(head_commit.committed_date).isoformat(),
        }
        logger.info(f"Clone successful: {result['commit_sha'][:8]} (branch: {branch})")
        return result

    except GitCommandError as e:
        raise MCPException(
            f"Git clone failed for '{repo_url}': {e.stderr or e.stdout or str(e)}",
            details={"repo_url": repo_url, "branch": branch},
        ) from e
    except Exception as e:
        raise MCPException(f"Unexpected error cloning '{repo_url}': {e}") from e


def git_log(repo_dir: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves recent commit history from a local Git repository.

    Args:
        repo_dir: Path to the repository root (relative to workspaces or absolute).
        limit: Maximum number of commits to return.

    Returns:
        List of commit dicts with: sha, author, email, date, message.
    """
    repo = _open_repo(repo_dir)

    commits = []
    for commit in repo.iter_commits(max_count=limit):
        commits.append({
            "sha": commit.hexsha,
            "short_sha": commit.hexsha[:8],
            "author": str(commit.author),
            "email": commit.author.email if commit.author.email else "",
            "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
            "message": commit.message.strip(),
        })

    logger.debug(f"Retrieved {len(commits)} commits from {repo_dir}")
    return commits


def git_branches(repo_dir: str) -> List[str]:
    """Lists all branches (local and remote) in a repository.

    Args:
        repo_dir: Path to the repository root.

    Returns:
        List of branch names.
    """
    repo = _open_repo(repo_dir)

    branches: List[str] = []
    # Local branches
    for ref in repo.branches:
        branches.append(ref.name)
    # Remote branches
    for remote in repo.remotes:
        for ref in remote.refs:
            name = ref.name
            if name not in branches:
                branches.append(name)

    logger.debug(f"Found {len(branches)} branches in {repo_dir}")
    return branches


def git_diff(repo_dir: str, commit_a: str = "HEAD~1", commit_b: str = "HEAD") -> str:
    """Returns the unified diff between two commits.

    Args:
        repo_dir: Path to the repository root.
        commit_a: First commit reference (default: HEAD~1).
        commit_b: Second commit reference (default: HEAD).

    Returns:
        Unified diff string.
    """
    repo = _open_repo(repo_dir)

    try:
        diff_output = repo.git.diff(commit_a, commit_b)
        logger.debug(f"Generated diff {commit_a}..{commit_b}: {len(diff_output)} chars")
        return diff_output
    except GitCommandError as e:
        raise MCPException(
            f"Git diff failed ({commit_a}..{commit_b}): {e.stderr or str(e)}",
            details={"repo_dir": repo_dir, "commit_a": commit_a, "commit_b": commit_b},
        ) from e


def git_changed_files(repo_dir: str) -> Dict[str, List[str]]:
    """Lists files with uncommitted changes in the working directory.

    Args:
        repo_dir: Path to the repository root.

    Returns:
        Dict with keys: modified, added, deleted, untracked.
    """
    repo = _open_repo(repo_dir)

    result: Dict[str, List[str]] = {
        "modified": [],
        "added": [],
        "deleted": [],
        "untracked": list(repo.untracked_files),
    }

    # Diff between index and working tree
    for diff_item in repo.index.diff(None):
        if diff_item.change_type == "M":
            result["modified"].append(diff_item.a_path)
        elif diff_item.change_type == "A":
            result["added"].append(diff_item.a_path)
        elif diff_item.change_type == "D":
            result["deleted"].append(diff_item.a_path)

    logger.debug(
        f"Changed files in {repo_dir}: "
        f"{len(result['modified'])} modified, "
        f"{len(result['untracked'])} untracked"
    )
    return result


def _open_repo(repo_dir: str) -> Repo:
    """Opens and validates a local Git repository path.

    Args:
        repo_dir: Path to the repository root.

    Returns:
        GitPython Repo object.

    Raises:
        MCPException: If the path isn't a valid git repository.
    """
    workspace_root = settings.workspaces_path.resolve()
    target = Path(repo_dir)
    if not target.is_absolute():
        target = workspace_root / target
    target = target.resolve()

    if not target.exists():
        raise MCPException(f"Repository directory not found: {target}")

    try:
        return Repo(str(target))
    except InvalidGitRepositoryError:
        raise MCPException(
            f"Not a valid Git repository: {target}",
            details={"repo_dir": str(target)},
        )
