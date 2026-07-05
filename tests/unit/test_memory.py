# =========================================================
# ApexDeploy - Unit Tests for Memory Module
# Tests session memory, pipeline memory, and deployment history
# =========================================================

import pytest

from src.db.database import run_migrations, get_db_connection
from src.db.repositories import agent_memory_repo
from src.config.settings import settings


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch, tmp_path):
    """Initializes the database schema on an isolated temp database."""
    db_path = tmp_path / "test_apexdeploy_memory.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    await run_migrations()


# =========================================================
# MODULE IMPORT TESTS
# =========================================================

class TestMemoryModuleImports:
    """Verify that all memory modules are importable."""

    def test_import_session_memory(self):
        """Verify session_memory module imports without errors."""
        import src.memory.session_memory  # noqa: F401

    def test_import_pipeline_memory(self):
        """Verify pipeline_memory module imports without errors."""
        import src.memory.pipeline_memory  # noqa: F401

    def test_import_deployment_history(self):
        """Verify deployment_history module imports without errors."""
        import src.memory.deployment_history  # noqa: F401

    def test_import_memory_package(self):
        """Verify the memory package __init__ is importable."""
        import src.memory  # noqa: F401


# =========================================================
# AGENT MEMORY REPOSITORY (Database-backed Memory) TESTS
# =========================================================

class TestAgentMemoryDatabase:
    """Tests for the agent_memory_repo which provides persistent key-value storage."""

    @pytest.mark.asyncio
    async def test_store_and_recall(self):
        """Verify that storing and recalling a memory entry works correctly."""
        await agent_memory_repo.store(
            agent_name="git",
            memory_type="session",
            key="last_commit_sha",
            value="abc123def456",
            memory_id="mem-test-1"
        )

        result = await agent_memory_repo.recall("git", "last_commit_sha")
        assert result == "abc123def456"

    @pytest.mark.asyncio
    async def test_recall_nonexistent_key(self):
        """Verify that recalling a nonexistent key returns None."""
        result = await agent_memory_repo.recall("git", "nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_forget_removes_memory(self):
        """Verify that forgetting a key removes it from storage."""
        await agent_memory_repo.store(
            agent_name="security",
            memory_type="pipeline",
            key="last_scan_score",
            value="score_95",
            memory_id="mem-test-2"
        )

        # Confirm it exists
        val = await agent_memory_repo.recall("security", "last_scan_score")
        assert val == "score_95"

        # Forget
        await agent_memory_repo.forget("security", "last_scan_score")

        # Confirm it's gone
        val_after = await agent_memory_repo.recall("security", "last_scan_score")
        assert val_after is None

    @pytest.mark.asyncio
    async def test_overwrite_memory_entry(self):
        """Verify that storing a duplicate key overwrites the old value."""
        await agent_memory_repo.store(
            agent_name="docker",
            memory_type="session",
            key="last_image_id",
            value="sha256:old_image_123",
            memory_id="mem-test-3"
        )
        await agent_memory_repo.store(
            agent_name="docker",
            memory_type="session",
            key="last_image_id",
            value="sha256:new_image_456",
            memory_id="mem-test-4"
        )

        result = await agent_memory_repo.recall("docker", "last_image_id")
        assert result == "sha256:new_image_456"

    @pytest.mark.asyncio
    async def test_multiple_agents_independent_memory(self):
        """Verify that different agents maintain independent memory namespaces."""
        await agent_memory_repo.store(
            agent_name="git",
            memory_type="session",
            key="last_repo",
            value="repo-alpha",
            memory_id="mem-test-5"
        )
        await agent_memory_repo.store(
            agent_name="security",
            memory_type="session",
            key="last_repo",
            value="repo-beta",
            memory_id="mem-test-6"
        )

        git_val = await agent_memory_repo.recall("git", "last_repo")
        sec_val = await agent_memory_repo.recall("security", "last_repo")

        assert git_val == "repo-alpha"
        assert sec_val == "repo-beta"

    @pytest.mark.asyncio
    async def test_list_all_agent_memories(self):
        """Verify listing all memory entries for a specific agent."""
        await agent_memory_repo.store(
            agent_name="monitoring",
            memory_type="deployment",
            key="cpu_baseline",
            value="10.5",
            memory_id="mem-test-7"
        )
        await agent_memory_repo.store(
            agent_name="monitoring",
            memory_type="deployment",
            key="mem_baseline",
            value="256.0",
            memory_id="mem-test-8"
        )

        # Query all memory records for the monitoring agent
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT * FROM agent_memory WHERE agent_name = 'monitoring'"
            ) as cursor:
                rows = await cursor.fetchall()
                assert len(rows) >= 2
                keys = {row["key"] for row in rows}
                assert "cpu_baseline" in keys
                assert "mem_baseline" in keys

    @pytest.mark.asyncio
    async def test_forget_nonexistent_key_no_error(self):
        """Verify that forgetting a nonexistent key does not raise an error."""
        # This should not raise any exception
        await agent_memory_repo.forget("git", "definitely_not_stored")
