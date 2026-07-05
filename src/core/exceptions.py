# =========================================================
# ApexDeploy - Core Exceptions
# Unified exception hierarchy for the entire platform
# =========================================================

from typing import Any, Dict, Optional


class ApexException(Exception):
    """Base exception for all ApexDeploy errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DatabaseException(ApexException):
    """Raised when a database query or operation fails."""
    pass


class AgentException(ApexException):
    """Raised when an agent execution fails, times out, or encounters errors."""
    pass


class PipelineException(ApexException):
    """Raised when pipeline workflow execution fails or gets aborted."""
    pass


class DockerException(ApexException):
    """Raised when Docker container operations, image builds, or daemon communication fail."""
    pass


class DeploymentException(ApexException):
    """Raised when the application deployment fails to initiate or complete."""
    pass


class MCPException(ApexException):
    """Raised when an MCP tool wrapper encounters an error (path violation, command failure, API error)."""
    pass


class ConfigurationException(ApexException):
    """Raised when configuration variables or inputs are invalid."""
    pass


class ResourceNotFoundException(ApexException):
    """Raised when a requested resource (repo, deployment, pipeline, etc.) is missing."""
    pass
