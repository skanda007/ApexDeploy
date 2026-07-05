# =========================================================
# ApexDeploy - Unit Tests for Report Service
# Verifies report rendering, JSON formatting, Markdown, HTML template rendering, and file archiving
# =========================================================

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from src.config.settings import settings
from src.db.database import run_migrations
from src.db.repositories import (
    repository_repo,
    pipeline_run_repo,
    agent_result_repo,
    deployment_repo,
    monitoring_snapshot_repo,
    security_finding_repo,
    rollback_event_repo,
)
from src.services.report_service import report_service
from src.core.exceptions import ConfigurationException, ResourceNotFoundException


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch, tmp_path):
    """Setup isolated environment for report testing."""
    db_path = tmp_path / "test_apexdeploy_reports_service.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    
    # Isolate directories
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    
    (tmp_path / "workspaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)

    await run_migrations()

    # Seed some standard data for reports
    await repository_repo.create(url="url", name="test-repo", repo_id="repo-1")
    await pipeline_run_repo.create(repo_id="repo-1", run_id="run-1")
    await pipeline_run_repo.finalize("run-1", status="passed", duration=5.0)

    await deployment_repo.create(pipeline_run_id="run-1", deployment_id="dep-1", image_name="img", image_tag="t")
    await deployment_repo.update_status("dep-1", "running")

    # Monitor
    await monitoring_snapshot_repo.create(deployment_id="dep-1", health_score=95.0, cpu_percent=1.2, memory_mb=100.0)

    # Security
    await security_finding_repo.create_batch("run-1", [
        {"id": "sf-1", "severity": "high", "category": "secrets", "description": "leak"}
    ])

    # Testing Agent Result
    test_result_json = json.dumps({
        "total_tests": 10,
        "passed": 9,
        "failed": 1,
        "coverage_percentage": 90.0,
        "failures": [{"name": "test_app", "error": "AssertionError"}]
    })
    await agent_result_repo.create(
        pipeline_run_id="run-1",
        agent_name="testing",
        status="completed",
        result_data=json.loads(test_result_json),
        duration=2.5
    )


@pytest.mark.asyncio
async def test_report_service_invalid_parameters():
    """Verify exception handling on invalid report type or format."""
    with pytest.raises(ConfigurationException) as exc:
        await report_service.generate_report(report_type="invalid", output_format="json")
    assert "Unsupported report type" in str(exc.value)

    with pytest.raises(ConfigurationException) as exc:
        await report_service.generate_report(report_type="security", output_format="xml")
    assert "Unsupported output format" in str(exc.value)


@pytest.mark.asyncio
async def test_generate_deployment_reports(tmp_path):
    """Verify deployment report generation for json, markdown, and html."""
    # JSON
    path_json, content_json = await report_service.generate_report("deployment", "json")
    assert path_json.exists()
    assert "deployments" in content_json
    assert content_json["summary"]["total"] == 1

    # MD
    path_md, content_md = await report_service.generate_report("deployment", "markdown")
    assert path_md.exists()
    assert "# ApexDeploy — Deployment Report" in content_md
    assert "Total Deployments" in content_md

    # HTML
    path_html, content_html = await report_service.generate_report("deployment", "html")
    assert path_html.exists()
    assert "<!DOCTYPE html>" in content_html
    assert "Deployment Report" in content_html


@pytest.mark.asyncio
async def test_generate_security_reports():
    """Verify security report generation works with or without scope_id."""
    # Without scope
    path_json, content_json = await report_service.generate_report("security", "json")
    assert content_json["summary"]["total_findings"] == 1
    assert content_json["severity_counts"]["high"] == 1

    # With scope
    path_html, content_html = await report_service.generate_report("security", "html", scope_id="run-1")
    assert "Security Report" in content_html
    assert "leak" in content_html


@pytest.mark.asyncio
async def test_generate_testing_reports():
    """Verify testing report generation pulls pipeline results."""
    # Testing requires scope_id
    with pytest.raises(ConfigurationException):
        await report_service.generate_report("testing", "json")

    # With correct scope
    path_json, content_json = await report_service.generate_report("testing", "json", scope_id="run-1")
    assert content_json["summary"]["total_tests"] == 10
    assert content_json["summary"]["passed"] == 9
    assert content_json["summary"]["failed"] == 1
    assert content_json["summary"]["coverage"] == 90.0
    assert len(content_json["failures"]) == 1

    # HTML
    path_html, content_html = await report_service.generate_report("testing", "html", scope_id="run-1")
    assert "test_app" in content_html
    assert "AssertionError" in content_html


@pytest.mark.asyncio
async def test_generate_monitoring_reports():
    """Verify monitoring report captures deployment snapshots."""
    path_json, content_json = await report_service.generate_report("monitoring", "json", scope_id="dep-1")
    assert content_json["deployment_id"] == "dep-1"
    assert content_json["summary"]["health_score"] == 95.0
    assert content_json["summary"]["avg_cpu"] == 1.2
    assert len(content_json["snapshots"]) == 1

    # HTML
    path_html, content_html = await report_service.generate_report("monitoring", "html", scope_id="dep-1")
    assert "Monitoring Report" in content_html
    assert "95" in content_html


@pytest.mark.asyncio
async def test_generate_rollback_reports():
    """Verify rollback report structures."""
    # Seed a rollback event
    await rollback_event_repo.create(
        deployment_id="dep-1",
        reason="unstable",
        from_image="img:v2",
        to_image="img:v1",
        health_score_before=30.0
    )

    path_json, content_json = await report_service.generate_report("rollback", "json")
    assert content_json["summary"]["total"] == 1
    assert len(content_json["events"]) == 1

    path_md, content_md = await report_service.generate_report("rollback", "markdown")
    assert "unstable" in content_md


@pytest.mark.asyncio
async def test_generate_health_reports():
    """Verify executive summary report covers overall KPIs."""
    path_json, content_json = await report_service.generate_report("health", "json")
    assert "overview" in content_json
    assert "pipeline" in content_json
    assert "security" in content_json

    path_html, content_html = await report_service.generate_report("health", "html")
    assert "Overall Health Report" in content_html


@pytest.mark.asyncio
async def test_list_reports():
    """Verify that reports listing aggregates files from disk correctly."""
    # Generate some reports
    await report_service.generate_report("deployment", "json")
    await report_service.generate_report("security", "markdown")
    await report_service.generate_report("health", "html")
    report_list = await report_service.list_reports()
    assert len(report_list) == 3
    assert any(r["extension"] == "json" for r in report_list)
    assert any(r["extension"] in ("md", "markdown") for r in report_list)
    assert any(r["extension"] == "html" for r in report_list)
    assert all("path" in r for r in report_list)
