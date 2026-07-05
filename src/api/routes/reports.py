# =========================================================
# ApexDeploy - Reports Router
# API endpoints for report generation, listing, and downloading
# =========================================================

import logging
import mimetypes
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from src.api.schemas.report import ReportListItem, ReportRequest, ReportResponse
from src.db import agent_result_repo
from src.services.report_service import report_service

logger = logging.getLogger("api.reports")
router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/generate", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(payload: ReportRequest):
    """Triggers the report generator service for the specified type, format, and scope."""
    try:
        file_path, content = await report_service.generate_report(
            report_type=payload.report_type,
            output_format=payload.output_format,
            scope_id=payload.scope_id,
        )

        now = datetime.now(timezone.utc).isoformat()
        return ReportResponse(
            report_type=payload.report_type,
            output_format=payload.output_format,
            filename=file_path.name,
            path=str(file_path.resolve()),
            created_at=now,
            content=content,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate {payload.report_type} report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {e}",
        )


@router.get("/list", response_model=List[ReportListItem])
async def list_reports():
    """Lists all previously archived reports stored in the artifacts directory."""
    try:
        reports = await report_service.list_reports()
        return [ReportListItem(**r) for r in reports]
    except Exception as e:
        logger.error(f"Failed to list archived reports: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list reports: {e}",
        )


@router.get("/run/{run_id}")
async def get_run_report_summary(run_id: str):
    """Gathers and maps generated agent results and artifacts for a pipeline run."""
    try:
        rows = await agent_result_repo.get_by_pipeline_run(run_id)
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No reports found for this pipeline run.",
            )

        reports = {}
        for row in rows:
            reports[row["agent_name"]] = {
                "status": row["status"],
                "result": row["result_json"],
                "artifact_path": row["artifact_path"],
                "duration_seconds": row["duration_seconds"],
                "created_at": row["created_at"],
            }
        return reports
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch reports for run {run_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}",
        )


@router.get("/download")
async def download_artifact_file(path: str):
    """Serves a static artifact report file from the workspace/artifacts storage directory."""
    try:
        file_path = Path(path).resolve()

        # Security protection check to ensure path is inside the project root folder
        project_root = Path.cwd().resolve()
        if not str(file_path).startswith(str(project_root)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Directory traversal blocked.",
            )

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requested artifact report file does not exist on disk.",
            )

        # Detect media type dynamically
        media_type, _ = mimetypes.guess_type(str(file_path))
        if not media_type:
            media_type = "application/octet-stream"

        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type=media_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file {path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File transfer error: {e}",
        )
