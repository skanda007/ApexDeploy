# =========================================================
# ApexDeploy - Integration Tests for REST API Endpoints
# Verifies health, repositories, pipelines, and settings routes
# =========================================================

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.config.settings import settings
from src.db.database import run_migrations, get_db_connection


@pytest.fixture(autouse=True)
async def setup_test_api_db(monkeypatch, tmp_path):
    """Isolates the database and configurations for clean API tests."""
    db_path = tmp_path / "test_api_integration.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    
    (tmp_path / "workspaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)

    await run_migrations()


# =========================================================
# SYSTEM & HEALTH ENDPOINT TESTS
# =========================================================

def test_root_welcome_endpoint():
    """Verify that root endpoint responds with metadata and 200."""
    with TestClient(app) as client:
        res = client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert "Welcome to the ApexDeploy API" in data["message"]
        assert "health" in data
        assert "version" in data


def test_health_check_shallow():
    """Verify shallow healthcheck endpoint responds with uptime status."""
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["app"] == "ApexDeploy API"


def test_health_check_details():
    """Verify detailed healthcheck fetches specs and DB state."""
    with TestClient(app) as client:
        res = client.get("/api/health/details")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert data["database"]["status"] == "healthy"
        assert "system" in data


# =========================================================
# REPOSITORIES ENDPOINT TESTS
# =========================================================

def test_repository_crud_cycle():
    """Verify registration, listing, and deletion of repositories via HTTP."""
    with TestClient(app) as client:
        # 1. Register repository
        payload = {
            "url": "https://github.com/example/api-repo.git",
            "name": "api-repo",
            "branch": "main"
        }
        create_res = client.post("/api/repositories", json=payload)
        assert create_res.status_code == 201
        created = create_res.json()
        assert "id" in created
        assert created["name"] == "api-repo"
        assert created["url"] == "https://github.com/example/api-repo.git"
        assert created["status"] == "active"
        
        repo_id = created["id"]

        # 2. Try registering duplicate name (should fail with 400)
        duplicate_res = client.post("/api/repositories", json=payload)
        assert duplicate_res.status_code == 400
        assert "already exists" in duplicate_res.json()["detail"]

        # 3. List repositories
        list_res = client.get("/api/repositories")
        assert list_res.status_code == 200
        repos = list_res.json()
        assert len(repos) >= 1
        assert any(r["id"] == repo_id for r in repos)

        # 4. Delete repository
        delete_res = client.delete(f"/api/repositories/{repo_id}")
        assert delete_res.status_code == 204

        # 5. Get list again, should be empty/deleted
        list_res_after = client.get("/api/repositories")
        assert not any(r["id"] == repo_id for r in list_res_after.json())


# =========================================================
# PIPELINE CONFIG & TRIGGER TESTS
# =========================================================

@pytest.mark.asyncio
async def test_trigger_pipeline_endpoint(monkeypatch):
    """Verify triggering pipeline initializes background job execution."""
    # Seed repository in database
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO repositories (id, url, name, branch, status)
            VALUES ('repo-trigger-1', 'https://github.com/example/trigger.git', 'trigger-repo', 'develop', 'active')
            """
        )
        await conn.commit()

    with TestClient(app) as client:
        # Mock orchestrator background task triggering to avoid real side effects in simple endpoint test
        with pytest.MonkeyPatch.context() as mp:
            # Trigger
            payload = {
                "repo_id": "repo-trigger-1",
                "branch": "develop"
            }
            res = client.post("/api/pipeline/trigger", json=payload)
            assert res.status_code == 202
            data = res.json()
            assert "pipeline_run_id" in data
            assert data["status"] == "triggered"
            
            run_id = data["pipeline_run_id"]

            # Query status
            status_res = client.get(f"/api/pipeline/runs/{run_id}")
            assert status_res.status_code == 200
            status_data = status_res.json()
            assert status_data["id"] == run_id
            assert status_data["repo_id"] == "repo-trigger-1"


# =========================================================
# SETTINGS & CONFIGURATION TESTS
# =========================================================

def test_settings_retrieval_endpoint():
    """Verify that settings are returned with credentials masked."""
    with TestClient(app) as client:
        res = client.get("/api/settings")
        assert res.status_code == 200
        configs = res.json()
        assert configs["APP_NAME"] == "ApexDeploy"
        
        # Masked keys check
        assert configs["SECRET_KEY"] == "********"
