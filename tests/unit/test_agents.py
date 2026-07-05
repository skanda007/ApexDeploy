# =========================================================
# ApexDeploy - Unit Tests for Agents
# Verifies agent contracts, language detection, and Git Agent execution
# =========================================================

from datetime import datetime
from unittest.mock import MagicMock, patch

import json
import pytest

from src.agents import (
    CodeReviewAgent,
    DeploymentAgent,
    DockerAgent,
    GitAgent,
    MonitoringAgent,
    RollbackAgent,
    SecurityAgent,
    TestingAgent,
)
from src.config.settings import settings
from src.core.base_agent import BaseAgent
from src.core.exceptions import AgentException
from src.db.database import get_db_connection, run_migrations
from src.utils.language_detector import detect_primary_language


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Initializes the database schema before each test run."""
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./data/test_apexdeploy_agents.db")
    await run_migrations()
    
    # Insert a dummy repository to satisfy foreign keys
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO repositories (id, url, name, branch, status)
            VALUES ('repo-git-test', 'https://github.com/user/test-git.git', 'test-git', 'main', 'active')
            """
        )
        await conn.commit()


# =========================================================
# LANGUAGE DETECTOR TESTS
# =========================================================

def test_language_detection(tmp_path):
    """Verify that primary language detection counts suffixes correctly."""
    # Test directory with python files
    py_dir = tmp_path / "python_project"
    py_dir.mkdir()
    (py_dir / "app.py").write_text("print('python')")
    (py_dir / "utils.py").write_text("print('utils')")
    (py_dir / "index.js").write_text("console.log('js')")  # secondary
    
    detected = detect_primary_language(str(py_dir))
    assert detected == "python"

    # Test directory with javascript files
    js_dir = tmp_path / "js_project"
    js_dir.mkdir()
    (js_dir / "index.js").write_text("console.log('index')")
    (js_dir / "app.jsx").write_text("export default App")
    
    detected = detect_primary_language(str(js_dir))
    assert detected == "javascript"


# =========================================================
# BASE AGENT & INHERITANCE TESTS
# =========================================================

def test_base_agent_abstract():
    """Verify that BaseAgent is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseAgent("abstract_base")


def test_agent_inheritance_and_naming():
    """Verify that all agents correctly inherit from BaseAgent and set names."""
    agents = [
        (GitAgent(), "git"),
        (CodeReviewAgent(), "code_review"),
        (TestingAgent(), "testing"),
        (SecurityAgent(), "security"),
        (DockerAgent(), "docker"),
        (DeploymentAgent(), "deployment"),
        (MonitoringAgent(), "monitoring"),
        (RollbackAgent(), "rollback")
    ]
    
    for agent, expected_name in agents:
        assert isinstance(agent, BaseAgent)
        assert agent.name == expected_name
        assert agent.status == "idle"


# =========================================================
# GIT AGENT EXECUTION TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.agents.git_agent.git_changed_files")
@patch("src.agents.git_agent.git_branches")
@patch("src.agents.git_agent.git_log")
@patch("src.agents.git_agent.git_clone")
async def test_git_agent_execution_flow(
    mock_clone,
    mock_log,
    mock_branches,
    mock_changed,
    tmp_path
):
    """Verify that GitAgent runs clone, fetches info, detects language, and saves DB entry."""
    # Setup MCP mock outputs
    mock_clone.return_value = {
        "status": "success",
        "path": str(tmp_path / "repo-git-test"),
        "commit_sha": "abcdef123456",
        "commit_author": "Developer",
        "commit_message": "Commit message",
    }
    mock_log.return_value = [{"sha": "abcdef123456", "message": "Commit message"}]
    mock_branches.return_value = ["main", "feature"]
    mock_changed.return_value = {"modified": [], "untracked": []}
    
    # Create some dummy source files to trigger language detection
    repo_dir = tmp_path / "repo-git-test"
    repo_dir.mkdir()
    (repo_dir / "index.js").write_text("console.log()")
    
    # Instantiate GitAgent
    agent = GitAgent()
    context = {
        "repo_id": "repo-git-test",
        "repo_url": "https://github.com/user/test-git.git",
        "branch": "main",
        "workspace_path": str(repo_dir)
    }
    
    res = await agent.execute(context)
    
    # Verify execution output structures
    assert res["status"] == "completed"
    results = res["results"]
    assert results["repo_name"] == "test-git"
    assert results["language"] == "javascript"
    assert results["commit_sha"] == "abcdef123456"
    assert results["author"] == "Developer"
    
    # Verify that database was updated with the language and path
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT branch, language, local_path FROM repositories WHERE id = 'repo-git-test'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["branch"] == "main"
            assert row["language"] == "javascript"
            assert row["local_path"] == str(repo_dir)


@pytest.mark.asyncio
async def test_agent_execution_failure():
    """Verify that agent errors are intercepted and raise AgentException."""
    agent = GitAgent()
    
    # Run with empty context to trigger validation failure
    with pytest.raises(AgentException) as exc_info:
        await agent.execute({})
        
    assert "Missing required parameters" in exc_info.value.message
    assert agent.status == "failed"


# =========================================================
# CODE REVIEW AGENT TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.agents.code_review_agent.generate_structured_json")
async def test_code_review_agent_execution(mock_generate_json, tmp_path, monkeypatch):
    """Verify that CodeReviewAgent scans files, invokes Gemini, and writes output artifact."""
    # Setup test workspace and artifacts path
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    mock_generate_json.return_value = {
        "review_status": "passed",
        "complexity_score": "medium",
        "duplicate_code_detected": False,
        "architecture_summary": "Clean layout summary comments.",
        "code_smells": [
            {
                "file_path": "main.py",
                "line_number": 12,
                "severity": "medium",
                "description": "Long function needs refactoring.",
                "recommendation": "Break function into helpers."
            }
        ],
        "suggestions": ["Refactor main script."]
    }

    # Setup mock cloned repo folder
    cloned_dir = tmp_path / "workspaces" / "run-cr-test"
    cloned_dir.mkdir(parents=True, exist_ok=True)
    (cloned_dir / "main.py").write_text("def test():\n    print('hello')\n")

    agent = CodeReviewAgent()
    context = {
        "pipeline_run_id": "run-cr-test",
        "git_results": {
            "cloned_path": str(cloned_dir),
            "language": "python"
        }
    }

    res = await agent.execute(context)
    
    assert res["status"] == "completed"
    results = res["results"]
    assert results["review_status"] == "passed"
    assert results["complexity_score"] == "medium"
    assert len(results["code_smells"]) == 1
    assert results["code_smells"][0]["file_path"] == "main.py"

    # Verify that the JSON artifact was written successfully
    artifact_path = tmp_path / "artifacts" / "run-cr-test" / "code_review.json"
    assert artifact_path.exists()
    
    with open(artifact_path) as f:
        data = json.load(f)
        assert data["review_status"] == "passed"
        assert data["complexity_score"] == "medium"


# =========================================================
# TESTING AGENT TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.agents.testing_agent.execute_command")
async def test_testing_agent_python_pytest(mock_execute, tmp_path, monkeypatch):
    """Verify TestingAgent runs pytest, parses stdout summary/coverage, and writes reports."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    # Mock terminal command run output for Python pytest
    mock_execute.return_value = {
        "exit_code": 0,
        "stdout": """
============================= test session starts =============================
collected 15 items
tests/unit/test_demo.py PASSED
=== 15 passed in 2.50s ===
TOTAL                               100     10  90%
""",
        "stderr": "",
        "duration_seconds": 2.5
    }

    # Setup mock cloned folder without Node/Java trigger files
    cloned_dir = tmp_path / "workspaces" / "run-test-py"
    cloned_dir.mkdir(parents=True, exist_ok=True)
    (cloned_dir / "app.py").write_text("print('hello')")

    agent = TestingAgent()
    context = {
        "pipeline_run_id": "run-test-py",
        "git_results": {
            "cloned_path": str(cloned_dir),
            "language": "python"
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["test_status"] == "passed"
    assert results["framework_detected"] == "pytest"
    assert results["tests_run"] == 15
    assert results["tests_passed"] == 15
    assert results["tests_failed"] == 0
    assert results["coverage_percentage"] == 90.0

    # Verify report JSON
    artifact_path = tmp_path / "artifacts" / "run-test-py" / "testing_report.json"
    assert artifact_path.exists()


@pytest.mark.asyncio
@patch("src.agents.testing_agent.execute_command")
async def test_testing_agent_node_npm(mock_execute, tmp_path, monkeypatch):
    """Verify Node.js detection and Jest/Mocha summary parsing."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    mock_execute.return_value = {
        "exit_code": 0,
        "stdout": "Tests:       2 failed, 10 passed, 12 total\nTime: 1.5s",
        "stderr": "",
        "duration_seconds": 1.5
    }

    cloned_dir = tmp_path / "workspaces" / "run-test-node"
    cloned_dir.mkdir(parents=True, exist_ok=True)
    # Create trigger package.json file
    (cloned_dir / "package.json").write_text("{}")

    agent = TestingAgent()
    context = {
        "pipeline_run_id": "run-test-node",
        "git_results": {
            "cloned_path": str(cloned_dir),
            "language": "javascript"
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["test_status"] == "failed"  # Because we mocked 2 failed tests
    assert results["framework_detected"] == "npm"
    assert results["tests_run"] == 12
    assert results["tests_passed"] == 10
    assert results["tests_failed"] == 2


@pytest.mark.asyncio
@patch("src.agents.testing_agent.execute_command")
async def test_testing_agent_java_maven(mock_execute, tmp_path, monkeypatch):
    """Verify Java detection and surefire logs summary parsing."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    mock_execute.return_value = {
        "exit_code": 0,
        "stdout": "Tests run: 20, Failures: 1, Errors: 0, Skipped: 1",
        "stderr": "",
        "duration_seconds": 4.2
    }

    cloned_dir = tmp_path / "workspaces" / "run-test-java"
    cloned_dir.mkdir(parents=True, exist_ok=True)
    # Create trigger pom.xml file
    (cloned_dir / "pom.xml").write_text("<project></project>")

    agent = TestingAgent()
    context = {
        "pipeline_run_id": "run-test-java",
        "git_results": {
            "cloned_path": str(cloned_dir),
            "language": "java"
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["test_status"] == "failed"  # 1 failure
    assert results["framework_detected"] == "maven"
    assert results["tests_run"] == 20
    assert results["tests_passed"] == 18
    assert results["tests_failed"] == 1
    assert results["tests_skipped"] == 1


# =========================================================
# SECURITY AGENT TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.agents.security_agent.generate_structured_json")
@patch("src.agents.security_agent.execute_command")
async def test_security_agent_passed(mock_execute, mock_generate_json, tmp_path, monkeypatch):
    """Verify SecurityAgent handles successful scan runs, parses results, and passes with score >= 70."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    # Mock Bandit tool execute call
    mock_execute.return_value = {
        "exit_code": 0,
        "stdout": '{"results": []}',
        "stderr": "",
        "duration_seconds": 0.5
    }

    # Mock Gemini structured JSON response
    mock_generate_json.return_value = {
        "security_score": 95,
        "security_status": "passed",
        "vulnerabilities": [],
        "secret_leaks": [],
        "recommendations": ["Follow standard security rules."]
    }

    cloned_dir = tmp_path / "workspaces" / "run-sec-pass"
    cloned_dir.mkdir(parents=True, exist_ok=True)
    (cloned_dir / "app.py").write_text("print('test')")

    agent = SecurityAgent()
    context = {
        "pipeline_run_id": "run-sec-pass",
        "git_results": {
            "cloned_path": str(cloned_dir),
            "language": "python"
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["security_score"] == 95
    assert results["security_status"] == "passed"
    assert len(results["recommendations"]) == 1

    # Verify report JSON was created
    artifact_path = tmp_path / "artifacts" / "run-sec-pass" / "security_report.json"
    assert artifact_path.exists()


@pytest.mark.asyncio
@patch("src.agents.security_agent.generate_structured_json")
@patch("src.agents.security_agent.execute_command")
async def test_security_agent_failed_quality_gate(mock_execute, mock_generate_json, tmp_path, monkeypatch):
    """Verify SecurityAgent fails quality gate if score drops below 70."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "SECURITY_SCORE_THRESHOLD", 70)

    mock_execute.return_value = {
        "exit_code": 0,
        "stdout": '{"results": []}',
        "stderr": "",
        "duration_seconds": 0.5
    }

    # Gemini returns high risk score (50)
    mock_generate_json.return_value = {
        "security_score": 50,
        "security_status": "passed",  # Will be overridden to failed in code
        "vulnerabilities": [
            {
                "issue_type": "SQL Injection",
                "file_path": "db.py",
                "line_number": 42,
                "severity": "critical",
                "description": "User input concatenated directly in query.",
                "recommendation": "Use parameterized queries."
            }
        ],
        "secret_leaks": [],
        "recommendations": []
    }

    cloned_dir = tmp_path / "workspaces" / "run-sec-fail"
    cloned_dir.mkdir(parents=True, exist_ok=True)
    (cloned_dir / "db.py").write_text("query = 'SELECT * FROM users WHERE id = ' + user_id")

    agent = SecurityAgent()
    context = {
        "pipeline_run_id": "run-sec-fail",
        "git_results": {
            "cloned_path": str(cloned_dir),
            "language": "python"
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["security_score"] == 50
    assert results["security_status"] == "failed"
    assert len(results["vulnerabilities"]) == 1
    assert results["vulnerabilities"][0]["issue_type"] == "SQL Injection"


def test_security_agent_secret_detection_scanner(tmp_path):
    """Verify local secret regex scanner identifies hardcoded credentials and leaks."""
    cloned_dir = tmp_path / "workspaces" / "run-sec-secrets"
    cloned_dir.mkdir(parents=True, exist_ok=True)
    
    # Write exposed AWS key
    (cloned_dir / "aws_secrets.py").write_text("AWS_ACCESS_KEY = 'AKIA1234567890ABCDEF'")
    # Write exposed generic password
    (cloned_dir / "db_config.js").write_text("const db_pass = 'secret_password_123'")
    # Write safe placeholder line (should be ignored)
    (cloned_dir / "safe.js").write_text("const db_pass = 'your-secret-here'")

    agent = SecurityAgent()
    leaks = agent._scan_for_secrets(cloned_dir)

    assert len(leaks) == 2
    types = {l["type"] for l in leaks}
    assert "AWS Access Key" in types
    assert "Generic Key/Token" in types
    
    # Verify file paths are relative
    assert leaks[0]["file_path"] in ["aws_secrets.py", "db_config.js"]
    assert leaks[1]["file_path"] in ["aws_secrets.py", "db_config.js"]



