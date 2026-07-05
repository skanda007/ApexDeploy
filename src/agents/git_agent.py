# =========================================================
# ApexDeploy - Git Agent
# Clones, reads commits/branches, detects language, saves DB info
# =========================================================

import logging
from typing import Any, Dict

from src.core.base_agent import BaseAgent
from src.core.exceptions import AgentException
from src.db.database import get_db_connection
from src.mcp import git_branches, git_changed_files, git_clone, git_log
from src.utils.language_detector import detect_primary_language

logger = logging.getLogger("agents.git")


class GitAgent(BaseAgent):
    """Git Agent responsible for cloning Git repositories, extracting commit logs,
    indexing branches, detecting the project language, and updating the database.
    """

    def __init__(self):
        super().__init__("git")

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        repo_id = context.get("repo_id")
        repo_url = context.get("repo_url")
        branch = context.get("branch", "main")
        workspace_path = context.get("workspace_path")

        if not repo_id or not repo_url or not workspace_path:
            raise AgentException(
                "Missing required parameters in GitAgent run context.",
                details={
                    "repo_id": repo_id,
                    "repo_url": repo_url,
                    "workspace_path": workspace_path,
                },
            )

        logger.info(f"GitAgent running for repo '{repo_id}' (URL: {repo_url}, branch: {branch})")

        try:
            # 1. Clone the repository into workspace target folder
            # We use target folder name matching the run_id to avoid collision
            target_dir = workspace_path.split("/")[-1]
            logger.info(f"Cloning repository branch '{branch}' into workspace: {target_dir}")
            
            clone_res = git_clone(
                repo_url=repo_url,
                target_dir=target_dir,
                branch=branch,
            )

            local_path = clone_res["path"]
            branch = clone_res.get("branch", branch)

            # 2. Extract commit logs (limit to 10 commits)
            logger.info("Extracting repository commit logs...")
            commit_history = git_log(repo_dir=local_path, limit=10)

            # 3. Retrieve branches list
            logger.info("Retrieving repository branches...")
            branch_list = git_branches(repo_dir=local_path)

            # 4. Check for changed files (uncommitted)
            logger.info("Scanning for changed or untracked files...")
            changed_info = git_changed_files(repo_dir=local_path)

            # 5. Detect project primary language
            logger.info("Analyzing workspace structure to determine project language...")
            detected_lang = detect_primary_language(directory_path=local_path)

            # 6. Update repository entry in SQLite Database
            logger.info(f"Updating database registry with branch={branch}, language={detected_lang}")
            async with get_db_connection() as conn:
                await conn.execute(
                    """
                    UPDATE repositories
                    SET branch = ?, language = ?, local_path = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (branch, detected_lang, local_path, repo_id),
                )
                await conn.commit()

            # Compile metadata result structure
            metadata = {
                "repo_name": repo_url.split("/")[-1].replace(".git", ""),
                "branch": branch,
                "commit_sha": clone_res.get("commit_sha"),
                "author": clone_res.get("commit_author"),
                "message": clone_res.get("commit_message"),
                "language": detected_lang,
                "cloned_path": local_path,
                "commit_history": commit_history,
                "branches": branch_list,
                "changed_files": changed_info,
                "status": "success",
            }
            
            logger.info(f"GitAgent completed successfully. Primary language detected: {detected_lang}")
            return metadata

        except Exception as e:
            logger.error(f"GitAgent operation failed: {e}", exc_info=True)
            raise AgentException(
                f"GitAgent execution failed: {e}",
                details={"repo_id": repo_id, "repo_url": repo_url},
            ) from e
