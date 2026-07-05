# =========================================================
# ApexDeploy - Git Utilities
# Helpers for checking environment git client and parsing URLs
# =========================================================

import logging
import re
import subprocess
from typing import Dict, Optional

logger = logging.getLogger("utils.git_utils")


def is_git_installed() -> bool:
    """Checks if the git CLI tool is installed and available on PATH.

    Returns:
        True if installed, False otherwise.
    """
    try:
        res = subprocess.run(
            ["git", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        return res.returncode == 0
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.warning(f"Error checking git version: {e}")
        return False


def parse_github_url(url: str) -> Optional[Dict[str, str]]:
    """Parses owner and repository name from common GitHub URLs.

    Args:
        url: Github URL string.

    Returns:
        Dict with keys 'owner' and 'repo' or None if not matching.
    """
    # Patterns for:
    # https://github.com/owner/repo.git
    # git@github.com:owner/repo.git
    # https://github.com/owner/repo
    pattern = r"(?:https://github\.com/|git@github\.com:)([^/]+)/([^/.]+)(?:\.git)?"
    match = re.match(pattern, url.strip())
    if match:
        return {
            "owner": match.group(1),
            "repo": match.group(2)
        }
    return None
