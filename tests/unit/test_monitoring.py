# =========================================================
# ApexDeploy - Unit Tests for Monitoring Agent and Modules
# Verifies CPU/Memory monitoring, HTTP health probe, metrics scoring, and MonitoringAgent
# =========================================================

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from src.agents.monitoring_agent import MonitoringAgent
from src.config.settings import settings
from src.core.exceptions import AgentException
from src.db.database import get_db_connection, run_migrations
from src.monitoring import (
    get_container_cpu_usage,
    get_container_memory_usage,
    probe_http_health,
    scan_logs_for_errors,
    calculate_health_score,
)


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Initializes the database schema before each test run."""
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./data/test_apexdeploy_monitoring.db")
    await run_migrations()
    
    # Insert dummy records to satisfy foreign keys
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO repositories (id, url, name, branch, status)
            VALUES ('repo-mon-test', 'https://github.com/user/test.git', 'test', 'main', 'active')
            """
        )
        await conn.execute(
            """
            INSERT OR REPLACE INTO pipeline_runs (id, repo_id, status, trigger, started_at)
            VALUES ('run-mon-test', 'repo-mon-test', 'running', 'manual', '2026-07-04T12:00:00')
            """
        )
        await conn.execute(
            """
            INSERT OR REPLACE INTO deployments (id, pipeline_run_id, container_id, image_name, image_tag, port, status, deploy_type, adapter_name, deployed_at)
            VALUES ('deploy-mon-test', 'run-mon-test', 'container-mon-xyz', 'apexdeploy/test', 'latest', 8080, 'running', 'docker', 'docker', '2026-07-04T12:10:00')
            """
        )
        await conn.commit()


# =========================================================
# MONITOR MODULE TESTS
# =========================================================

@patch("src.monitoring.cpu_monitor.is_docker_available")
@patch("src.monitoring.cpu_monitor.get_client")
def test_cpu_monitor_calculation(mock_get_client, mock_is_available):
    """Verify that get_container_cpu_usage delta math returns correct percentage."""
    mock_is_available.return_value = True
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container

    # Mock double stat returns (first run call, then sleep, then second run call)
    # stats1 represents precpu, stats2 represents cpu
    mock_container.stats.side_effect = [
        {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 100000000},
                "system_cpu_usage": 1000000000,
                "online_cpus": 2
            }
        },
        {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 150000000},
                "system_cpu_usage": 1200000000,
                "online_cpus": 2
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100000000},
                "system_cpu_usage": 1000000000
            }
        }
    ]

    percent = get_container_cpu_usage("container-xyz")
    # cpu_delta = 150000000 - 100000000 = 50000000
    # system_delta = 1200000000 - 1000000000 = 200000000
    # ratio = 50000000 / 200000000 = 0.25
    # percent = 0.25 * 2 * 100 = 50.0%
    assert percent == 50.0


@patch("src.monitoring.memory_monitor.is_docker_available")
@patch("src.monitoring.memory_monitor.get_client")
def test_memory_monitor_calculation(mock_get_client, mock_is_available):
    """Verify memory monitor extracts MB and percentage correctly from stats."""
    mock_is_available.return_value = True
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container

    mock_container.stats.return_value = {
        "memory_stats": {
            "usage": 104857600,  # 100 MB
            "limit": 1048576000  # 1000 MB
        }
    }

    usage_mb, usage_percent = get_container_memory_usage("container-xyz")
    assert usage_mb == 100.0
    assert usage_percent == 10.0


@pytest.mark.asyncio
@patch("src.monitoring.health_checker.httpx.AsyncClient.get")
async def test_health_checker_http_probe(mock_get):
    """Verify probe_http_health reports correct codes and latencies."""
    # Case 1: Healthy status
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_get.return_value = mock_res

    res = await probe_http_health(8080, "/health")
    assert res["success"] is True
    assert res["http_status"] == 200
    assert res["error"] is None

    # Case 2: Port not listening (Connection Refused)
    mock_get.side_effect = httpx.ConnectError("Connection refused")
    res = await probe_http_health(8081, "/health")
    assert res["success"] is False
    assert res["http_status"] == 0
    assert "refused" in res["error"]


def test_log_monitor_scanner():
    """Verify scan_logs_for_errors extracts warnings and ignores safe keywords."""
    mock_logs = (
        "[07/05/26 01:10:00] INFO Start service\n"
        "[07/05/26 01:10:02] ERROR Connection closed unexpectedly\n"
        "[07/05/26 01:10:05] WARNING Try reconnecting...\n"
        "[07/05/26 01:10:08] CRITICAL Database connection failed!\n"
    )

    with patch("src.monitoring.log_monitor.get_container_logs", return_value=mock_logs):
        errors = scan_logs_for_errors("container-xyz")
        assert len(errors) == 2
        assert "ERROR" in errors[0]
        assert "CRITICAL" in errors[1]


# =========================================================
# SCORE DEDUCTION METRIC TESTS
# =========================================================

def test_metrics_health_scorer():
    """Verify calculate_health_score deduces scores correctly based on metrics."""
    # 1. Perfect container
    metrics = {
        "container_status": "running",
        "http_status": 200,
        "latency_ms": 150.0,
        "cpu_percent": 15.0,
        "memory_percent": 30.0,
        "restart_count": 0
    }
    assert calculate_health_score(metrics) == 100.0

    # 2. Exited container status -> 0.0
    metrics["container_status"] = "exited"
    assert calculate_health_score(metrics) == 0.0

    # 3. HTTP status error (deduct 50) and high latency (deduct 20)
    metrics["container_status"] = "running"
    metrics["http_status"] = 500
    metrics["latency_ms"] = 1200.0  # > 1000ms
    assert calculate_health_score(metrics) == 30.0  # 100 - 50 - 20 = 30.0

    # 4. Overloaded resources (CPU > 90%, memory > 90%, restart count = 2)
    metrics_overloaded = {
        "container_status": "running",
        "http_status": 200,
        "latency_ms": 50.0,
        "cpu_percent": 95.0,     # deduct 20
        "memory_percent": 92.0,  # deduct 25
        "restart_count": 2        # deduct 20
    }
    # 100 - 20 - 25 - 20 = 35.0
    assert calculate_health_score(metrics_overloaded) == 35.0


# =========================================================
# AGENT SYSTEM TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.agents.monitoring_agent.get_container_cpu_usage")
@patch("src.agents.monitoring_agent.get_container_memory_usage")
@patch("src.agents.monitoring_agent.probe_http_health")
@patch("src.agents.monitoring_agent.scan_logs_for_errors")
@patch("src.agents.monitoring_agent.is_docker_available")
async def test_monitoring_agent_healthy_run(
    mock_docker_ok, mock_logs, mock_probe, mock_mem, mock_cpu, tmp_path, monkeypatch
):
    """Verify MonitoringAgent checks metrics, saves record to DB, and writes JSON report."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    mock_docker_ok.return_value = False  # Keep test environment independent of active daemon
    mock_cpu.return_value = 5.2
    mock_mem.return_value = (45.0, 15.0)
    mock_probe.return_value = {
        "success": True,
        "http_status": 200,
        "latency_ms": 12.0,
        "error": None
    }
    mock_logs.return_value = []

    agent = MonitoringAgent()
    context = {
        "pipeline_run_id": "run-mon-test",
        "deployment_results": {
            "deployment_id": "deploy-mon-test",
            "container_id": "container-mon-xyz",
            "port": 8080
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"

    results = res["results"]
    assert results["monitoring_status"] == "healthy"
    assert results["health_score"] == 100.0
    assert results["cpu_percent"] == 5.2
    assert results["memory_mb"] == 45.0
    assert results["http_status"] == 200

    # Verify SQLite Database row is created in snapshots
    async with get_db_connection() as conn, conn.execute(
        "SELECT * FROM monitoring_snapshots WHERE deployment_id = 'deploy-mon-test'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row["cpu_percent"] == 5.2
        assert row["memory_mb"] == 45.0
        assert row["health_score"] == 100.0

    # Verify JSON artifact report exists
    report_file = tmp_path / "artifacts" / "run-mon-test" / "monitoring_report.json"
    assert report_file.exists()


@pytest.mark.asyncio
async def test_monitoring_agent_skipped_no_deployment():
    """Verify MonitoringAgent skips execution gracefully when no container details are found."""
    agent = MonitoringAgent()
    
    # context misses deployment/container IDs
    context = {
        "pipeline_run_id": "run-mon-skip",
        "deployment_results": {}
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["monitoring_status"] == "healthy"  # Kept green
    assert results["container_status"] == "none"
    assert "no container was deployed" in results["logs"]
