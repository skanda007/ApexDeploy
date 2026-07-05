# =========================================================
# ApexDeploy - Unit Tests for Reports API Route
# Verifies route handlers, HTTP endpoints, query params, and validation schemas
# =========================================================

import json
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from pathlib import Path

from src.main import app
from src.config.settings import settings
from src.db.database import run_migrations, get_db_connection
from src.db.repositories import repository_repo, pipeline_run_repo, agent_result_repo, deployment_repo


@pytest.fixture(autouse=True)
async def setup_test_api_db(monkeypatch, tmp_path):
    """Isolates the database URL and static directory paths for route tests."""
    db_path = tmp_path / "test_apexdeploy_api_route.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    
    # Isolate paths
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    
    (tmp_path / "workspaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)

    await run_migrations()

    # Seed data
    await repository_repo.create(url="url", name="test-repo", repo_id="repo-1")
    await pipeline_run_repo.create(repo_id="repo-1", run_id="run-1")
    await pipeline_run_repo.finalize("run-1", status="passed", duration=5.0)

    # Agent result
    await agent_result_repo.create(
        pipeline_run_id="run-1",
        agent_name="git",
        status="completed",
        result_data={"commit": "sha"},
        duration=1.0
    )


def test_generate_report_endpoint():
    """Verify POST /api/reports/generate creates a report and responds with 201."""
    with TestClient(app) as client:
        payload = {
            "report_type": "deployment",
            "output_format": "json",
            "scope_id": "run-1"
        }
        res = client.post("/api/reports/generate", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["report_type"] == "deployment"
        assert data["output_format"] == "json"
        assert "filename" in data
        assert "path" in data
        assert data["content"]["summary"]["total"] == 0


def test_list_reports_endpoint():
    """Verify GET /api/reports/list retrieves list of archived reports."""
    with TestClient(app) as client:
        # Generate a report first
        payload = {
            "report_type": "health",
            "output_format": "html"
        }
        client.post("/api/reports/generate", json=payload)

        # Get list
        res = client.get("/api/reports/list")
        assert res.status_code == 200
        data = res.json()
        assert len(data) >= 1
        assert data[0]["extension"] == "html"
        assert "health_report" in data[0]["filename"]


def test_get_run_report_summary_endpoint():
    """Verify GET /api/reports/run/{run_id} returns mapped agent results."""
    with TestClient(app) as client:
        res = client.get("/api/reports/run/run-1")
        assert res.status_code == 200
        data = res.json()
        assert "git" in data
        assert data["git"]["status"] == "completed"
        assert data["git"]["duration_seconds"] == 1.0

        # Query nonexistent run
        res_404 = client.get("/api/reports/run/nonexistent")
        assert res_404.status_code == 404


def test_download_artifact_file_endpoint(tmp_path):
    """Verify GET /api/reports/download serves files and guards against traversal."""
    # Write a test file under project root
    project_root = Path.cwd().resolve()
    test_file = project_root / "test_download_artifact.txt"
    test_file.write_text("secure file contents")

    try:
        with TestClient(app) as client:
            # Clean download
            res = client.get(f"/api/reports/download?path={str(test_file)}")
            assert res.status_code == 200
            assert res.text == "secure file contents"

            # Directory traversal block (trying to read outside project root)
            traversal_path = Path("C:/Windows/System32/drivers/etc/hosts") if Path("C:/Windows/System32/drivers/etc/hosts").exists() else Path("/etc/passwd")
            res_forbidden = client.get(f"/api/reports/download?path={str(traversal_path.resolve())}")
            assert res_forbidden.status_code in (403, 404)

            # Not found
            res_404 = client.get(f"/api/reports/download?path={str(project_root / 'nonexistent.txt')}")
            assert res_404.status_code == 404
    finally:
        if test_file.exists():
            test_file.unlink()
