# =========================================================
# ApexDeploy - Unit Tests for Database Repository Layer
# Verifies base CRUD, singletons, and stats aggregations
# =========================================================

import pytest
from datetime import datetime, timezone

from src.config.settings import settings
from src.db.database import run_migrations, get_db_connection
from src.db.repositories import (
    repository_repo,
    pipeline_run_repo,
    agent_result_repo,
    deployment_repo,
    monitoring_snapshot_repo,
    security_finding_repo,
    rollback_event_repo,
    agent_memory_repo,
    event_log_repo,
)
from src.db import stats
from src.core.exceptions import ResourceNotFoundException, DatabaseException


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch, tmp_path):
    """Initializes schema on an isolated temp database file before each test run."""
    db_path = tmp_path / "test_apexdeploy_repos.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    await run_migrations()


@pytest.mark.asyncio
async def test_repository_repo_operations():
    """Verify RepositoryRepo create, update, and search methods."""
    # Create
    repo = await repository_repo.create(
        url="https://github.com/test/repo.git",
        name="test-repo",
        branch="develop",
        repo_id="test-repo-1"
    )
    assert repo["id"] == "test-repo-1"
    assert repo["url"] == "https://github.com/test/repo.git"
    assert repo["branch"] == "develop"
    assert repo["status"] == "active"

    # Update methods
    await repository_repo.update_language("test-repo-1", "python")
    await repository_repo.update_local_path("test-repo-1", "/tmp/local")
    await repository_repo.update_status("test-repo-1", "archived")

    updated = await repository_repo.get_by_id("test-repo-1")
    assert updated["language"] == "python"
    assert updated["local_path"] == "/tmp/local"
    assert updated["status"] == "archived"

    # Exists check
    exists = await repository_repo.exists_by_name_or_url("test-repo", "some-other-url")
    assert exists is True

    exists_false = await repository_repo.exists_by_name_or_url("nonexistent", "nonexistent-url")
    assert exists_false is False


@pytest.mark.asyncio
async def test_pipeline_run_repo_operations():
    """Verify PipelineRunRepo lifecycle methods and listings."""
    # Add dependency repo
    await repository_repo.create(
        url="url", name="repo-name", repo_id="repo-dep"
    )

    # Create run
    run_id = await pipeline_run_repo.create(repo_id="repo-dep", trigger="manual", run_id="run-1")
    assert run_id == "run-1"

    # Update stage
    await pipeline_run_repo.update_stage(run_id, stage="git", status="running")
    run = await pipeline_run_repo.get_by_id(run_id)
    assert run["status"] == "running"
    assert run["current_stage"] == "git"

    # Finalize
    await pipeline_run_repo.finalize(run_id, status="passed", duration=15.5, context_json='{"status": "ok"}')
    finalized = await pipeline_run_repo.get_detail(run_id)
    assert finalized["status"] == "passed"
    assert finalized["duration_seconds"] == 15.5
    assert finalized["context_json"] == '{"status": "ok"}'
    assert finalized["repo_name"] == "repo-name"

    # Query methods
    runs = await pipeline_run_repo.get_by_repo("repo-dep")
    assert len(runs) == 1
    assert runs[0]["id"] == "run-1"

    all_runs = await pipeline_run_repo.list_with_repo_name(limit=5)
    assert len(all_runs) == 1
    assert all_runs[0]["repo_name"] == "repo-name"


@pytest.mark.asyncio
async def test_agent_result_repo_operations():
    """Verify AgentResultRepo creates and retrieves results correctly."""
    await repository_repo.create(url="url", name="repo-name", repo_id="repo-dep")
    await pipeline_run_repo.create(repo_id="repo-dep", run_id="run-1")

    # Create
    res_id = await agent_result_repo.create(
        pipeline_run_id="run-1",
        agent_name="git",
        status="completed",
        result_data={"commit": "sha"},
        duration=1.2,
        artifact_path="/path/to/art",
        result_id="res-1"
    )
    assert res_id == "res-1"

    # Query
    run_results = await agent_result_repo.get_by_pipeline_run("run-1")
    assert len(run_results) == 1
    assert run_results[0]["agent_name"] == "git"
    assert run_results[0]["status"] == "completed"
    assert run_results[0]["duration_seconds"] == 1.2
    assert run_results[0]["artifact_path"] == "/path/to/art"

    agent_results = await agent_result_repo.get_by_agent_name("git")
    assert len(agent_results) == 1


@pytest.mark.asyncio
async def test_deployment_repo_operations():
    """Verify DeploymentRepo lifecycle and active listings."""
    await repository_repo.create(url="url", name="repo-name", repo_id="repo-dep")
    await pipeline_run_repo.create(repo_id="repo-dep", run_id="run-1")

    # Create
    dep_id = await deployment_repo.create(
        pipeline_run_id="run-1",
        image_name="test-image",
        image_tag="v1",
        port=8080,
        deploy_type="local",
        adapter_name="docker",
        deployment_id="dep-1"
    )
    assert dep_id == "dep-1"

    # Update to running
    await deployment_repo.update_status(dep_id, "running", container_id="container-abc")
    dep = await deployment_repo.get_by_id(dep_id)
    assert dep["status"] == "running"
    assert dep["container_id"] == "container-abc"
    assert dep["deployed_at"] is not None

    # Get active
    active = await deployment_repo.get_active()
    assert len(active) == 1
    assert active[0]["id"] == "dep-1"

    # Stop deployment
    await deployment_repo.update_status(dep_id, "stopped")
    dep_stopped = await deployment_repo.get_by_id(dep_id)
    assert dep_stopped["status"] == "stopped"
    assert dep_stopped["stopped_at"] is not None


@pytest.mark.asyncio
async def test_monitoring_snapshot_repo_operations():
    """Verify MonitoringSnapshotRepo captures and evaluates health scores."""
    await repository_repo.create(url="url", name="repo-name", repo_id="repo-dep")
    await pipeline_run_repo.create(repo_id="repo-dep", run_id="run-1")
    await deployment_repo.create(pipeline_run_id="run-1", deployment_id="dep-1")

    # Create snapshot
    snap_id = await monitoring_snapshot_repo.create(
        deployment_id="dep-1",
        cpu_percent=12.5,
        memory_mb=128.0,
        memory_percent=5.0,
        http_status=200,
        latency_ms=120.0,
        container_status="running",
        restart_count=0,
        health_score=95.0,
        snapshot_id="snap-1"
    )
    assert snap_id == "snap-1"

    # Get snapshots and stats
    snapshots = await monitoring_snapshot_repo.get_by_deployment("dep-1")
    assert len(snapshots) == 1
    assert snapshots[0]["cpu_percent"] == 12.5
    assert snapshots[0]["health_score"] == 95.0

    latest = await monitoring_snapshot_repo.get_latest("dep-1")
    assert latest["id"] == "snap-1"

    score = await monitoring_snapshot_repo.get_health_score("dep-1")
    assert score == 95.0


@pytest.mark.asyncio
async def test_security_finding_repo_operations():
    """Verify SecurityFindingRepo handles batch insert and query groups."""
    await repository_repo.create(url="url", name="repo-name", repo_id="repo-dep")
    await pipeline_run_repo.create(repo_id="repo-dep", run_id="run-1")

    findings = [
        {
            "id": "f-1",
            "severity": "high",
            "category": "bandit",
            "file_path": "main.py",
            "line_number": 10,
            "description": "Hardcoded key",
            "recommendation": "Use env var",
            "cwe_id": "CWE-798"
        },
        {
            "id": "f-2",
            "severity": "medium",
            "category": "secrets",
            "file_path": "config.json",
            "line_number": 2,
            "description": "API secret found",
            "recommendation": "Remove it",
            "cwe_id": "CWE-522"
        }
    ]

    inserted = await security_finding_repo.create_batch("run-1", findings)
    assert inserted == 2

    # Get by run
    run_findings = await security_finding_repo.get_by_pipeline_run("run-1")
    assert len(run_findings) == 2
    assert run_findings[0]["severity"] == "high"

    # Count by severity
    counts = await security_finding_repo.count_by_severity("run-1")
    assert counts["high"] == 1
    assert counts["medium"] == 1

    # Get by severity
    high_findings = await security_finding_repo.get_by_severity("high")
    assert len(high_findings) == 1
    assert high_findings[0]["id"] == "f-1"


@pytest.mark.asyncio
async def test_rollback_event_repo_operations():
    """Verify RollbackEventRepo lifecycle tracking."""
    await repository_repo.create(url="url", name="repo-name", repo_id="repo-dep")
    await pipeline_run_repo.create(repo_id="repo-dep", run_id="run-1")
    await deployment_repo.create(pipeline_run_id="run-1", deployment_id="dep-1")

    # Create event
    event_id = await rollback_event_repo.create(
        deployment_id="dep-1",
        reason="HTTP timeout",
        from_image="app:latest",
        to_image="app:v1-stable",
        health_score_before=40.0,
        event_id="rollback-1"
    )
    assert event_id == "rollback-1"

    # Update status
    await rollback_event_repo.update_status("rollback-1", "completed", health_score_after=100.0)

    events = await rollback_event_repo.get_by_deployment("dep-1")
    assert len(events) == 1
    assert events[0]["status"] == "completed"
    assert events[0]["health_score_after"] == 100.0


@pytest.mark.asyncio
async def test_agent_memory_repo_operations():
    """Verify AgentMemoryRepo stores, recalls, and forgets key-value data."""
    # Store
    mem_id = await agent_memory_repo.store(
        agent_name="git",
        memory_type="session",
        key="last_sha",
        value="a1b2c3d4",
        memory_id="mem-1"
    )
    assert mem_id == "mem-1"

    # Recall
    val = await agent_memory_repo.recall("git", "last_sha")
    assert val == "a1b2c3d4"

    # Forget
    await agent_memory_repo.forget("git", "last_sha")
    val_after = await agent_memory_repo.recall("git", "last_sha")
    assert val_after is None


@pytest.mark.asyncio
async def test_event_log_repo_operations():
    """Verify EventLogRepo records and extracts platform events."""
    await repository_repo.create(url="url", name="repo-name", repo_id="repo-dep")
    await pipeline_run_repo.create(repo_id="repo-dep", run_id="run-1")

    # Emit
    event_id = await event_log_repo.emit(
        event_type="pipeline_started",
        source_agent="orchestrator",
        pipeline_run_id="run-1",
        payload={"started_by": "cli"},
        event_id="evt-1"
    )
    assert event_id == "evt-1"

    # Retrieve
    run_events = await event_log_repo.get_by_pipeline_run("run-1")
    assert len(run_events) == 1
    assert run_events[0]["event_type"] == "pipeline_started"
    assert run_events[0]["source_agent"] == "orchestrator"


@pytest.mark.asyncio
async def test_stats_aggregation_queries():
    """Verify that aggregate statistics query methods return expected metrics."""
    # Seed data
    await repository_repo.create(url="url1", name="repo1", repo_id="repo-1")
    await repository_repo.create(url="url2", name="repo2", repo_id="repo-2")

    await pipeline_run_repo.create(repo_id="repo-1", run_id="run-1")
    await pipeline_run_repo.finalize("run-1", status="passed", duration=10.0)

    await pipeline_run_repo.create(repo_id="repo-1", run_id="run-2")
    await pipeline_run_repo.finalize("run-2", status="failed", duration=20.0)

    await deployment_repo.create(pipeline_run_id="run-1", deployment_id="dep-1")
    await deployment_repo.update_status("dep-1", "running")

    await monitoring_snapshot_repo.create(deployment_id="dep-1", health_score=90.0, cpu_percent=2.5)

    findings = [
        {"id": "sf-1", "severity": "critical", "category": "bandit"},
        {"id": "sf-2", "severity": "high", "category": "secrets"}
    ]
    await security_finding_repo.create_batch("run-1", findings)

    await rollback_event_repo.create(deployment_id="dep-1", reason="Unstable")

    # Test aggregate stats
    overview = await stats.get_overview_stats()
    assert overview["total_repositories"] == 2
    assert overview["total_pipeline_runs"] == 2
    assert overview["passed_runs"] == 1
    assert overview["failed_runs"] == 1
    assert overview["total_deployments"] == 1
    assert overview["active_deployments"] == 1
    assert overview["total_security_findings"] == 2
    assert overview["total_rollbacks"] == 1

    pass_rate = await stats.get_pipeline_pass_rate()
    assert pass_rate == 50.0

    avg_dur = await stats.get_avg_pipeline_duration()
    assert avg_dur == 15.0

    securities = await stats.get_security_severity_distribution()
    assert securities["critical"] == 1
    assert securities["high"] == 1

    breakdown = await stats.get_deployment_status_breakdown()
    assert breakdown["running"] == 1

    history = await stats.get_pipeline_history(limit=5)
    assert len(history) == 2

    trend = await stats.get_health_trend("dep-1")
    assert len(trend) == 1
    assert trend[0]["health_score"] == 90.0
