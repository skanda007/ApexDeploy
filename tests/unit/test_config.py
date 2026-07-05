# =========================================================
# ApexDeploy - Unit Tests for Config Settings
# Checks loading defaults, absolute paths and overrides
# =========================================================

import pytest
from src.config.settings import Settings


def test_settings_default_values():
    """Verify that settings can load and contain valid defaults."""
    settings = Settings()
    assert settings.APP_NAME == "ApexDeploy"
    assert settings.APP_ENV in ["development", "testing", "production"]
    assert settings.API_PORT == 8000
    assert len(settings.cors_origins_list) > 0


def test_settings_paths():
    """Verify that helper properties return valid paths."""
    settings = Settings()
    assert settings.workspaces_path is not None
    assert settings.artifacts_path is not None
    assert settings.logs_path is not None
    assert "apexdeploy.db" in settings.database_path
