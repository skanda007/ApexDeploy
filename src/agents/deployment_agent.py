# =========================================================
# ApexDeploy - Deployment Agent
# Local deployment of container using adapter pattern
# =========================================================

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from src.core.base_agent import BaseAgent
from src.core.exceptions import AgentException
from src.db.database import get_db_connection
from src.deployment import get_adapter
from src.mcp import write_file

logger = logging.getLogger("agents.deployment")


class DeploymentAgent(BaseAgent):
    """Deployment Agent responsible for deploying built Docker images locally
    using the Deployment Adapter pattern, recording states to the database,
    and writing reports to artifacts.
    """

    def __init__(self):
        super().__init__("deployment")

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_run_id = context.get("pipeline_run_id")
        docker_results = context.get("docker_results", {})
        image_name = docker_results.get("image_name")
        image_tag = docker_results.get("image_tag", "latest")

        # Skip deployment if no docker image was built/provided
        if not image_name:
            logger.warning("No built Docker image found in context. Skipping deployment.")
            return {
                "deployment_status": "skipped",
                "container_id": "",
                "container_name": "",
                "port": None,
                "url": "",
                "adapter_used": "none",
                "logs": "Skipped deployment - no built Docker image was found in pipeline context."
            }

        # Retrieve target configuration (default is 'docker')
        # Settings can define default deployment targets if needed
        target = context.get("deployment_target", "docker")
        logger.info(f"DeploymentAgent executing local deploy for target: '{target}'")

        try:
            # 1. Resolve adapter and deploy
            adapter = get_adapter(target)
            deploy_res = await adapter.deploy(context)

            deployment_id = str(uuid.uuid4())
            container_id = deploy_res.get("container_id")
            container_name = deploy_res.get("container_name")
            port = deploy_res.get("port")
            url = deploy_res.get("url")
            deployed_at = deploy_res.get("deployed_at", datetime.utcnow().isoformat())

            # 2. Register deployment record in the SQLite Database
            logger.info(f"Saving deployment record {deployment_id} to database...")
            async with get_db_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO deployments (
                        id, pipeline_run_id, container_id, image_name, image_tag, port, status, deploy_type, adapter_name, deployed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        deployment_id,
                        pipeline_run_id,
                        container_id,
                        image_name,
                        image_tag,
                        port,
                        "running",
                        "docker" if target == "docker" else "local",
                        target,
                        deployed_at
                    )
                )
                await conn.commit()

            # Compile execution report
            report = {
                "deployment_id": deployment_id,
                "pipeline_run_id": pipeline_run_id,
                "deployment_status": "success",
                "container_id": container_id,
                "container_name": container_name,
                "image_name": image_name,
                "image_tag": image_tag,
                "port": port,
                "url": url,
                "adapter_used": target,
                "deployed_at": deployed_at,
                "logs": f"Successfully deployed container '{container_name}' locally on port {port} using '{target}' adapter."
            }

            # 3. Write deployment report JSON under artifacts folder
            artifact_file = f"./artifacts/{pipeline_run_id}/deployment_report.json"
            logger.info(f"Writing deployment JSON report to: {artifact_file}")
            write_file(
                filepath=artifact_file,
                content=json.dumps(report, indent=2)
            )

            return report

        except Exception as e:
            logger.error(f"DeploymentAgent failed to complete deployment: {e}", exc_info=True)
            raise AgentException(
                f"DeploymentAgent execution failed: {e}",
                details={"pipeline_run_id": pipeline_run_id}
            ) from e
