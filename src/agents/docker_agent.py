# =========================================================
# ApexDeploy - Docker Agent
# Generates Dockerfile/docker-compose, builds local images
# =========================================================

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict

from src.core.base_agent import BaseAgent
from src.core.exceptions import AgentException
from src.mcp import write_file
from src.docker.docker_client import is_docker_available
from src.docker.docker_builder import generate_dockerfile, build_image

logger = logging.getLogger("agents.docker")


class DockerAgent(BaseAgent):
    """Docker Agent responsible for analyzing the workspace, generating optimized
    Dockerfile/docker-compose configurations using LLM, writing them to the workspace,
    and building local Docker images.
    """

    def __init__(self):
        super().__init__("docker")

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pipeline_run_id = context.get("pipeline_run_id")
        git_results = context.get("git_results", {}) or context.get("git_metadata", {})
        cloned_path = git_results.get("cloned_path")
        language = git_results.get("language", "python")
        repo_name = git_results.get("repo_name", "apexdeploy-app")

        if not cloned_path or not os.path.exists(cloned_path):
            logger.warning("No cloned repository workspace found in context. Skipping Docker build.")
            return {
                "docker_status": "skipped",
                "dockerfile_generated": False,
                "docker_compose_generated": False,
                "image_name": "",
                "image_tag": "",
                "image_id": "",
                "size_bytes": 0,
                "logs": "Skipped Docker build - no checkout path was provided."
            }

        logger.info(f"DockerAgent starting Docker generation and build on workspace: {cloned_path}")
        workspace_dir = Path(cloned_path).resolve()

        # 1. Scan files in workspace for Gemini context
        files_list = []
        try:
            for p in workspace_dir.rglob("*"):
                if p.is_file():
                    # Exclude venv, node_modules, and git dirs
                    if any(part.startswith(".") for part in p.parts):
                        continue
                    if "node_modules" in p.parts or "venv" in p.parts or ".venv" in p.parts:
                        continue
                    files_list.append(str(p.relative_to(workspace_dir)))
        except Exception as e:
            logger.warning(f"Error listing files in workspace for Docker prompt: {e}")

        # 2. Read dependency declarations if they exist
        dependency_content = ""
        dep_file_candidates = ["requirements.txt", "package.json", "pom.xml", "build.gradle", "go.mod", "Cargo.toml"]
        
        for candidate in dep_file_candidates:
            dep_path = workspace_dir / candidate
            if dep_path.exists():
                try:
                    logger.info(f"Found dependency configuration: {candidate}")
                    dependency_content = dep_path.read_text(encoding="utf-8", errors="replace")
                    break
                except Exception as e:
                    logger.warning(f"Failed to read dependency file {candidate}: {e}")

        # 3. Call Gemini to generate Dockerfile and docker-compose.yml
        logger.info("Requesting Gemini to generate containerization configurations...")
        try:
            docker_config = await generate_dockerfile(
                language=language,
                files_list=files_list,
                dependency_content=dependency_content
            )
        except Exception as e:
            logger.error(f"Gemini Dockerfile generation failed: {e}", exc_info=True)
            raise AgentException(f"Failed to generate Docker config: {e}") from e

        # 4. Write generated configurations to workspace using write_file (filesystem wrapper)
        dockerfile_path = workspace_dir / "Dockerfile"
        compose_path = workspace_dir / "docker-compose.yml"

        logger.info(f"Writing generated Dockerfile to {dockerfile_path}")
        write_file(filepath=str(dockerfile_path), content=docker_config.dockerfile_content)

        logger.info(f"Writing generated docker-compose.yml to {compose_path}")
        write_file(filepath=str(compose_path), content=docker_config.compose_content)

        # 5. Write copies of generated files to artifacts directory for record keeping
        artifacts_dir = f"./artifacts/{pipeline_run_id}"
        write_file(filepath=f"{artifacts_dir}/Dockerfile", content=docker_config.dockerfile_content)
        write_file(filepath=f"{artifacts_dir}/docker-compose.yml", content=docker_config.compose_content)

        # Sanitize image name according to Docker rules
        sanitized_repo_name = re.sub(r'[^a-zA-Z0-9_\-]', '-', repo_name).lower()
        image_name = f"apexdeploy/{sanitized_repo_name}"
        image_tag = "latest"

        # 6. Check if Docker daemon is available before starting build
        if not is_docker_available():
            logger.warning("Docker daemon is not running. Returning configurations without building.")
            return {
                "docker_status": "success-no-daemon",
                "dockerfile_generated": True,
                "docker_compose_generated": True,
                "image_name": image_name,
                "image_tag": image_tag,
                "image_id": "sha256-docker-unavailable-placeholder",
                "size_bytes": 0,
                "dockerfile_content": docker_config.dockerfile_content,
                "compose_content": docker_config.compose_content,
                "build_logs": ["Docker daemon unavailable. Skipping actual image build."]
            }

        # 7. Perform build
        logger.info(f"Docker daemon is running. Building Docker image: {image_name}:{image_tag}")
        try:
            build_res = build_image(
                build_path=str(workspace_dir),
                image_name=image_name,
                image_tag=image_tag,
                dockerfile_path="Dockerfile"
            )

            if not build_res.success:
                logger.error(f"Docker image build failed: {build_res.error_message}")
                # We raise AgentException to mark pipeline run stage as failed
                raise AgentException(
                    f"Docker image build failed: {build_res.error_message}",
                    details={"build_logs": build_res.build_logs}
                )

            # Write build logs to artifacts
            write_file(
                filepath=f"{artifacts_dir}/docker_build.log",
                content="\n".join(build_res.build_logs)
            )

            logger.info("DockerAgent completed successfully.")
            return {
                "docker_status": "success",
                "dockerfile_generated": True,
                "docker_compose_generated": True,
                "image_name": image_name,
                "image_tag": image_tag,
                "image_id": build_res.image_id,
                "size_bytes": build_res.size_bytes,
                "dockerfile_content": docker_config.dockerfile_content,
                "compose_content": docker_config.compose_content,
                "build_logs": build_res.build_logs
            }

        except AgentException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Docker build: {e}", exc_info=True)
            raise AgentException(f"Unexpected error during Docker build: {e}") from e
