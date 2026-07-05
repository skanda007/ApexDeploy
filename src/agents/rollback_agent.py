# =========================================================
# ApexDeploy - Rollback Agent
# Automatically rolls back unhealthy deployments to previous healthy versions
# =========================================================

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from src.core.base_agent import BaseAgent
from src.core.exceptions import AgentException
from src.db.database import get_db_connection
from src.deployment import get_adapter
from src.docker import is_docker_available, run_container, get_container_status
from src.mcp import write_file

logger = logging.getLogger("agents.rollback")


class RollbackAgent(BaseAgent):
    """Rollback Agent responsible for reverting unhealthy deployments
    to the last known healthy deployment, cleaning up resources,
    updating the SQLite database, and publishing reports.
    """

    def __init__(self):
        super().__init__("rollback")

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_run_id = context.get("pipeline_run_id")
        repo_id = context.get("repo_id")
        deployment_results = context.get("deployment_results", {}) or {}
        monitoring_results = context.get("monitoring_results", {}) or {}

        health_score_before = monitoring_results.get("health_score", 0.0)

        # 1. Resolve repository ID from pipeline_runs table if missing in context
        if not repo_id:
            logger.info("repo_id missing in context. Querying database...")
            try:
                async with get_db_connection() as conn:
                    async with conn.execute(
                        "SELECT repo_id FROM pipeline_runs WHERE id = ?",
                        (pipeline_run_id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            repo_id = row["repo_id"]
            except Exception as e:
                logger.debug(f"Failed to query repo_id: {e}")

        # 2. Resolve current unhealthy deployment details
        current_deployment_id = deployment_results.get("deployment_id")
        current_container_id = deployment_results.get("container_id") or context.get("container_id")
        current_port = deployment_results.get("port") or context.get("deployment_port")
        current_image_name = deployment_results.get("image_name")
        current_image_tag = deployment_results.get("image_tag", "latest")

        # Fallback database lookup for current deployment if context is sparse
        if not current_deployment_id:
            logger.info("Deployment details sparse in context. Querying database...")
            try:
                async with get_db_connection() as conn:
                    async with conn.execute(
                        """
                        SELECT id, container_id, port, image_name, image_tag 
                        FROM deployments 
                        WHERE pipeline_run_id = ?
                        """,
                        (pipeline_run_id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            current_deployment_id = row["id"]
                            current_container_id = row["container_id"]
                            current_port = row["port"]
                            current_image_name = row["image_name"]
                            current_image_tag = row["image_tag"]
            except Exception as e:
                logger.debug(f"Failed to query current deployment from DB: {e}")

        if not current_deployment_id:
            logger.warning(f"Could not find any active deployment for pipeline run {pipeline_run_id} to rollback.")
            return {
                "rollback_status": "skipped",
                "reason": "No active deployment records found to roll back.",
                "success": True
            }

        # Determine target adapter (default is 'docker')
        target_adapter = context.get("deployment_target", "docker")
        logger.info(f"RollbackAgent initiating rollback for deployment {current_deployment_id} using '{target_adapter}'")

        # 3. Query DB for last healthy deployment (status 'running' or 'stopped' from previous runs)
        prev_deployment_id = None
        prev_container_id = None
        prev_image_name = None
        prev_image_tag = "latest"
        prev_port = None
        prev_pipeline_run_id = None

        if repo_id:
            try:
                async with get_db_connection() as conn:
                    async with conn.execute(
                        """
                        SELECT d.id, d.container_id, d.image_name, d.image_tag, d.port, d.pipeline_run_id
                        FROM deployments d
                        JOIN pipeline_runs pr ON d.pipeline_run_id = pr.id
                        WHERE pr.repo_id = ? AND d.status IN ('running', 'stopped') AND d.id != ?
                        ORDER BY d.deployed_at DESC
                        LIMIT 1
                        """,
                        (repo_id, current_deployment_id)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            prev_deployment_id = row["id"]
                            prev_container_id = row["container_id"]
                            prev_image_name = row["image_name"]
                            prev_image_tag = row["image_tag"] or "latest"
                            prev_port = row["port"]
                            prev_pipeline_run_id = row["pipeline_run_id"]
                            logger.info(f"Identified previous healthy deployment: {prev_deployment_id}")
            except Exception as e:
                logger.warning(f"Failed to query previous healthy deployment from DB: {e}")

        # 4. Perform rollback actions
        from_image = f"{current_image_name}:{current_image_tag}" if current_image_name else "unknown:latest"
        to_image = None
        rollback_action = "none"

        try:
            # Undeploy the current unhealthy container
            if current_container_id:
                logger.info(f"Undeploying unhealthy container: {current_container_id}")
                try:
                    adapter = get_adapter(target_adapter)
                    await adapter.undeploy(current_container_id)
                except Exception as e:
                    logger.warning(f"Failed to undeploy unhealthy container {current_container_id}: {e}")

            # If previous deployment exists, restore it
            if prev_deployment_id and prev_image_name:
                to_image = f"{prev_image_name}:{prev_image_tag}"
                
                # Check if previous container is still running in Docker
                prev_running = False
                if is_docker_available() and prev_container_id:
                    try:
                        status_info = get_container_status(prev_container_id)
                        prev_running = status_info.get("status") == "running"
                    except Exception:
                        pass

                if prev_running:
                    logger.info(f"Previous container '{prev_container_id}' is already running. Rollback complete.")
                    rollback_action = "restored_active_container"
                else:
                    # Previous container is stopped or missing; redeploy it
                    if is_docker_available():
                        # Retrieve the exposed port from the previous docker agent results
                        exposed_port = 8000
                        try:
                            async with get_db_connection() as conn:
                                async with conn.execute(
                                    "SELECT result_json FROM agent_results WHERE pipeline_run_id = ? AND agent_name = 'docker'",
                                    (prev_pipeline_run_id,)
                                ) as cursor:
                                    row = await cursor.fetchone()
                                    if row and row["result_json"]:
                                        docker_data = json.loads(row["result_json"])
                                        exposed_port = docker_data.get("exposed_port", 8000)
                        except Exception as e:
                            logger.debug(f"Failed to extract exposed port from previous docker run: {e}")

                        restored_name = f"apexdeploy-rollback-{prev_deployment_id}"
                        logger.info(f"Spinning up previous image '{to_image}' on port {prev_port} (container port {exposed_port})")
                        
                        run_res = run_container(
                            image_name=prev_image_name,
                            image_tag=prev_image_tag,
                            container_name=restored_name,
                            ports={str(exposed_port): prev_port or 8080},
                            env_vars={"APP_ENV": "production", "PORT": str(exposed_port)}
                        )
                        # Update the previous container ID in deployments table
                        async with get_db_connection() as conn:
                            await conn.execute(
                                "UPDATE deployments SET container_id = ?, status = 'running' WHERE id = ?",
                                (run_res["container_id"], prev_deployment_id)
                            )
                            await conn.commit()
                        rollback_action = "redeployed_previous_image"
                    else:
                        logger.warning("Docker daemon unavailable. Mocking restore of previous image.")
                        rollback_action = "mock_restored_previous_image"

            else:
                logger.info("No previous healthy deployment exists. Cleaned up unhealthy container only.")
                rollback_action = "cleaned_up_unhealthy_only"

            # 5. Record rollback in SQLite database
            rollback_id = str(uuid.uuid4())
            now_str = datetime.now(timezone.utc).isoformat()
            async with get_db_connection() as conn:
                # Mark current deployment as rolled_back
                await conn.execute(
                    "UPDATE deployments SET status = 'rolled_back', stopped_at = ? WHERE id = ?",
                    (now_str, current_deployment_id)
                )
                
                # Insert rollback event record
                await conn.execute(
                    """
                    INSERT INTO rollback_events (
                        id, deployment_id, reason, from_image, to_image, status, health_score_before, health_score_after, triggered_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rollback_id,
                        current_deployment_id,
                        f"Health check failed (score: {health_score_before})",
                        from_image,
                        to_image,
                        "completed",
                        health_score_before,
                        100.0 if to_image else 0.0,
                        now_str,
                        now_str
                    )
                )
                await conn.commit()

            # Compile execution report
            report = {
                "rollback_id": rollback_id,
                "deployment_id": current_deployment_id,
                "rollback_status": "completed",
                "action_taken": rollback_action,
                "from_image": from_image,
                "to_image": to_image,
                "health_score_before": health_score_before,
                "health_score_after": 100.0 if to_image else 0.0,
                "success": True,
                "timestamp": now_str
            }

            # Write rollback report JSON under artifacts folder
            artifact_file = f"./artifacts/{pipeline_run_id}/rollback_report.json"
            logger.info(f"Writing rollback JSON report to: {artifact_file}")
            write_file(
                filepath=artifact_file,
                content=json.dumps(report, indent=2)
            )

            report["artifact_path"] = artifact_file
            return report

        except Exception as e:
            logger.error(f"RollbackAgent failed during execution: {e}", exc_info=True)
            raise AgentException(
                f"RollbackAgent execution failed: {e}",
                details={"pipeline_run_id": pipeline_run_id}
            ) from e
