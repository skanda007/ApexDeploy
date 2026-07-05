# =========================================================
# ApexDeploy - Report API Schemas
# Pydantic schemas validating report generation requests/responses
# =========================================================

from typing import Any, Optional
from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """Payload to trigger report generation."""

    report_type: str = Field(
        ...,
        description="Type of report: 'deployment', 'security', 'testing', 'monitoring', 'rollback', 'health'",
        examples=["security"],
    )
    output_format: str = Field(
        "html",
        description="Format of report: 'json', 'markdown', 'html'",
        examples=["html"],
    )
    scope_id: Optional[str] = Field(
        None,
        description="Optional filter ID (e.g. pipeline run ID, deployment ID, or repository ID)",
        examples=["run-1234"],
    )


class ReportResponse(BaseModel):
    """Response returned after report is generated."""

    report_type: str
    output_format: str
    filename: str
    path: str
    created_at: str
    content: Optional[Any] = Field(
        None,
        description="Structured dictionary for JSON format, or raw string content for markdown/html",
    )


class ReportListItem(BaseModel):
    """Metadata representing a previously generated report file."""

    filename: str
    path: str
    size_bytes: int
    created_at: str
    extension: str
