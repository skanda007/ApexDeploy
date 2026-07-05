# =========================================================
# ApexDeploy - Pipeline Runner
# Core engine orchestrating agent runs, concurrency, and error handling
# =========================================================

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any

from src.core.agent_registry import agent_registry
from src.core.exceptions import AgentException, PipelineException
from src.config.settings import settings
from src.pipeline.pipeline_context import PipelineContext
from src.pipeline.pipeline_state import (
    update_pipeline_run_stage,
    save_agent_result,
    finalize_pipeline_run
)
from src.pipeline.pipeline_events import (
    emit_pipeline_started,
    emit_pipeline_completed,
    emit_pipeline_failed,
    emit_stage_started,
    emit_stage_completed,
    emit_stage_failed
)

logger = logging.getLogger("pipeline.runner")


class PipelineRunner:
    """The pipeline execution engine that runs agents in sequence and parallel,
    records results, and triggers rollbacks if deployments fail health checks.
    """

    async def run(self, context: PipelineContext) -> PipelineContext:
        run_id = context.pipeline_run_id
        context.started_at = datetime.utcnow()
        context.status = "running"
        
        await emit_pipeline_started(run_id, context.repo_id)
        
        try:
            # -----------------------------------------------------
            # Stage 1: Git Repository Checkout
            # -----------------------------------------------------
            context.current_stage = "git"
            await update_pipeline_run_stage(run_id, "git", "running")
            await self._run_stage("git", context)
            
            # Update languages if detected
            context.language = context.git_metadata.get("language", "python")
            
            # -----------------------------------------------------
            # Stage 2: Parallel Quality Gates (Review, Test, Scan)
            # -----------------------------------------------------
            context.current_stage = "analysis"
            await update_pipeline_run_stage(run_id, "analysis", "running")
            
            # Run Code Review, testing, and security scanning concurrently
            results = await asyncio.gather(
                self._run_stage("code_review", context),
                self._run_stage("testing", context),
                self._run_stage("security", context),
                return_exceptions=True
            )
            
            # Check for execution errors during parallel analysis
            for name, res in zip(["code_review", "testing", "security"], results):
                if isinstance(res, Exception):
                    raise PipelineException(f"Analysis stage failed inside sub-agent '{name}': {res}")
            
            # Enforcement of Quality Gates
            # A security score less than the threshold will halt build & deploy
            security_score = context.security_results.get("security_score", 100)
            threshold = settings.SECURITY_SCORE_THRESHOLD
            if security_score < threshold:
                raise PipelineException(
                    f"Security Quality Gate Failed: Vulnerability score ({security_score}) below safety limit ({threshold})."
                )
                
            test_status = context.testing_results.get("test_status", "passed")
            if test_status != "passed":
                logger.warning(
                    f"Pipeline {run_id}: Testing quality gate flagged failures "
                    f"(test_status={test_status}). Continuing pipeline — review test report."
                )
            
            # -----------------------------------------------------
            # Stage 3: Containerization (Docker Build)
            # -----------------------------------------------------
            context.current_stage = "docker"
            await update_pipeline_run_stage(run_id, "docker", "running")
            await self._run_stage("docker", context)
            
            context.docker_image_name = context.docker_results.get("image_name")
            context.docker_image_tag = context.docker_results.get("image_tag")
            
            # -----------------------------------------------------
            # Stage 4: Deployment
            # -----------------------------------------------------
            context.current_stage = "deployment"
            await update_pipeline_run_stage(run_id, "deployment", "running")
            await self._run_stage("deployment", context)
            
            context.container_id = context.deployment_results.get("container_id")
            context.deployment_port = context.deployment_results.get("port")
            
            # -----------------------------------------------------
            # Stage 5: Active Health Check (Monitoring)
            # -----------------------------------------------------
            context.current_stage = "monitoring"
            await update_pipeline_run_stage(run_id, "monitoring", "running")
            await self._run_stage("monitoring", context)
            
            # Evaluate deployment health score
            health_status = context.monitoring_results.get("monitoring_status", "healthy")
            if health_status != "healthy":
                logger.warning(
                    f"Pipeline {run_id} deployment unhealthy ({health_status}). Dispatching RollbackAgent!"
                )
                # -------------------------------------------------
                # Failure Recovery: Rollback
                # -------------------------------------------------
                context.current_stage = "rollback"
                await update_pipeline_run_stage(run_id, "rollback", "running")
                await self._run_stage("rollback", context)
                
                rollback_success = context.rollback_results.get("success", False)
                if rollback_success:
                    raise PipelineException("Deployment is unhealthy. Application was rolled back successfully.")
                else:
                    raise PipelineException("Deployment is unhealthy and AUTOMATED ROLLBACK FAILED!")

            # -----------------------------------------------------
            # Finalize: Pipeline Passed
            # -----------------------------------------------------
            context.status = "passed"
            context.completed_at = datetime.utcnow()
            context.duration_seconds = (context.completed_at - context.started_at).total_seconds()
            
            await finalize_pipeline_run(run_id, "passed", context)
            await emit_pipeline_completed(run_id, context.duration_seconds)
            logger.info(f"Pipeline run {run_id} completed successfully in {context.duration_seconds:.2f}s")
            
            return context
            
        except Exception as e:
            logger.error(f"Pipeline run {run_id} failed: {e}", exc_info=True)
            
            context.status = "failed"
            context.error_message = str(e)
            context.completed_at = datetime.utcnow()
            context.duration_seconds = (context.completed_at - context.started_at).total_seconds()
            
            await finalize_pipeline_run(run_id, "failed", context)
            await emit_pipeline_failed(run_id, str(e))
            
            return context

    async def _run_stage(self, agent_name: str, context: PipelineContext) -> Dict[str, Any]:
        """Loads and executes a single agent within the pipeline context."""
        run_id = context.pipeline_run_id
        await emit_stage_started(run_id, agent_name)
        
        agent = agent_registry.get(agent_name)
        start_time = time.perf_counter()
        
        try:
            logger.info(f"Dispatching task to Agent: '{agent_name}' for run {run_id}")
            # Serialize context dict to decouple runtime states
            serialized_context = context.model_dump()
            execution_response = await agent.execute(serialized_context)
            duration = time.perf_counter() - start_time
            
            agent_result = execution_response.get("results", {})
            
            # Map result back to context attributes
            setattr(context, f"{agent_name}_results", agent_result)
            # Compatibility with old field names in pipeline_context
            if agent_name == "git":
                context.git_metadata = agent_result
                if "branch" in agent_result:
                    context.branch = agent_result["branch"]
            
            context.agent_durations[agent_name] = duration
            
            status = execution_response.get("status", "completed")
            artifact_path = execution_response.get("artifact_path")
            
            # Save results in SQLite DB
            await save_agent_result(run_id, agent_name, status, agent_result, duration, artifact_path)
            await emit_stage_completed(run_id, agent_name, duration)
            
            return agent_result
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(f"Agent '{agent_name}' execution crashed: {e}")
            
            await save_agent_result(run_id, agent_name, "failed", {"error": str(e)}, duration)
            await emit_stage_failed(run_id, agent_name, str(e))
            raise
