# =========================================================
# ApexDeploy - Test Fixtures (Phase 16)
# Shared pytest fixtures for unit and integration tests
# =========================================================

import os
import sys
import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def app_settings(monkeypatch, tmp_path):
    """Provide isolated test application settings with temp directories."""
    from src.config.settings import settings

    db_path = tmp_path / "test_apexdeploy.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(settings, "APP_ENV", "testing")

    # Ensure directories exist
    (tmp_path / "workspaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)

    return settings


@pytest.fixture
async def initialized_db(app_settings):
    """Run database migrations and return the settings instance (async)."""
    from src.db.database import run_migrations
    await run_migrations()
    return app_settings


@pytest.fixture
def sample_python_project(tmp_path):
    """Creates a minimal Python project structure for testing agents."""
    project_dir = tmp_path / "sample_python"
    project_dir.mkdir(parents=True, exist_ok=True)

    (project_dir / "app.py").write_text(
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "\n"
        "@app.route('/')\n"
        "def hello():\n"
        "    return 'Hello, World!'\n"
    )
    (project_dir / "utils.py").write_text(
        "def sanitize_input(data: str) -> str:\n"
        "    return data.strip()\n"
    )
    (project_dir / "requirements.txt").write_text("flask==3.0.0\nrequests==2.31.0\n")

    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("")
    (tests_dir / "test_app.py").write_text(
        "def test_hello():\n"
        "    assert True\n"
    )

    return project_dir


@pytest.fixture
def sample_node_project(tmp_path):
    """Creates a minimal Node.js project structure for testing agents."""
    project_dir = tmp_path / "sample_node"
    project_dir.mkdir(parents=True, exist_ok=True)

    (project_dir / "package.json").write_text(
        '{"name": "test-app", "version": "1.0.0", "scripts": {"test": "jest"}}'
    )
    (project_dir / "index.js").write_text(
        "const express = require('express');\n"
        "const app = express();\n"
        "app.get('/', (req, res) => res.send('Hello'));\n"
        "module.exports = app;\n"
    )
    (project_dir / "app.jsx").write_text("export default function App() { return <div/>; }\n")

    return project_dir


@pytest.fixture
def sample_java_project(tmp_path):
    """Creates a minimal Java/Maven project structure for testing agents."""
    project_dir = tmp_path / "sample_java"
    project_dir.mkdir(parents=True, exist_ok=True)

    (project_dir / "pom.xml").write_text(
        "<project>\n"
        "  <groupId>com.test</groupId>\n"
        "  <artifactId>test-app</artifactId>\n"
        "  <version>1.0.0</version>\n"
        "</project>\n"
    )
    src_dir = project_dir / "src" / "main" / "java"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "App.java").write_text(
        'public class App { public static void main(String[] args) { System.out.println("Hello"); } }\n'
    )

    return project_dir


@pytest.fixture
def mock_docker_client():
    """Provides a pre-configured MagicMock for Docker client interactions."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.version.return_value = {
        "Version": "24.0.7",
        "ApiVersion": "1.43",
        "Os": "linux",
        "Arch": "amd64",
    }
    mock_client.info.return_value = {
        "ServerVersion": "24.0.7",
        "OperatingSystem": "Docker Desktop",
        "Architecture": "x86_64",
        "NCPU": 4,
        "MemTotal": 8_200_000_000,
        "ContainersRunning": 2,
        "ContainersStopped": 5,
        "Images": 15,
    }
    return mock_client
