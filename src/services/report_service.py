# =========================================================
# ApexDeploy - Report Generator Service
# Generates JSON, Markdown, and HTML reports from DB metrics
# =========================================================

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config.settings import settings
from src.core.exceptions import ConfigurationException, ResourceNotFoundException
from src.db import (
    agent_result_repo,
    deployment_repo,
    monitoring_snapshot_repo,
    pipeline_run_repo,
    repository_repo,
    rollback_event_repo,
    security_finding_repo,
    stats,
)
from src.services.report_templates import (
    render_deployment_report_html,
    render_health_report_html,
    render_monitoring_report_html,
    render_rollback_report_html,
    render_security_report_html,
    render_testing_report_html,
)

logger = logging.getLogger("services.report")


class ReportService:
    """Consolidated report generation engine."""

    @property
    def reports_dir(self) -> Path:
        p = Path(settings.artifacts_path) / "reports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    async def generate_report(
        self,
        report_type: str,
        output_format: str,
        scope_id: Optional[str] = None,
    ) -> Tuple[Path, Any]:
        """Generates a report of a given type and format, saving it to the artifacts directory.

        Args:
            report_type: 'deployment', 'security', 'testing', 'monitoring', 'rollback', 'health'
            output_format: 'json', 'markdown', 'html'
            scope_id: Optional ID to filter the report (e.g. run_id, deployment_id, repo_id)

        Returns:
            Tuple[Path, Any]: The path to the saved file and the content generated.
        """
        report_type = report_type.lower()
        output_format = output_format.lower()

        if report_type not in ("deployment", "security", "testing", "monitoring", "rollback", "health"):
            raise ConfigurationException(f"Unsupported report type: {report_type}")

        if output_format not in ("json", "markdown", "html"):
            raise ConfigurationException(f"Unsupported output format: {output_format}")

        # 1. Gather raw data
        data = await self._gather_report_data(report_type, scope_id)

        # 2. Render content based on format
        content = ""
        if output_format == "json":
            content = json.dumps(data, indent=2)
        elif output_format == "markdown":
            content = self._render_markdown(report_type, data)
        elif output_format == "html":
            content = self._render_html(report_type, data)

        # 3. Save to file
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        scope_suffix = f"_{scope_id[:8]}" if scope_id else ""
        filename = f"{report_type}_report{scope_suffix}_{timestamp}.{output_format}"
        file_path = self.reports_dir / filename

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Report saved successfully to {file_path}")
        except Exception as e:
            logger.error(f"Failed to write report file to {file_path}: {e}", exc_info=True)
            raise

        # Return dict directly for JSON format to make API consumption easier
        returned_content = data if output_format == "json" else content
        return file_path, returned_content

    async def list_reports(self) -> List[Dict[str, Any]]:
        """List all generated reports in the artifacts directory."""
        reports = []
        if not self.reports_dir.exists():
            return []

        for p in self.reports_dir.iterdir():
            if p.is_file() and p.suffix in (".json", ".md", ".html", ".markdown"):
                stat = p.stat()
                created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                reports.append({
                    "filename": p.name,
                    "path": str(p.resolve()),
                    "size_bytes": stat.st_size,
                    "created_at": created_at,
                    "extension": p.suffix.lstrip("."),
                })
        # Order by creation date descending
        reports.sort(key=lambda x: x["created_at"], reverse=True)
        return reports

    # ------------------------------------------------------------------
    # Data Gathering
    # ------------------------------------------------------------------

    async def _gather_report_data(self, report_type: str, scope_id: Optional[str]) -> Dict[str, Any]:
        """Gather DB objects corresponding to the report type."""
        if report_type == "deployment":
            return await self._gather_deployment_data(scope_id)
        elif report_type == "security":
            return await self._gather_security_data(scope_id)
        elif report_type == "testing":
            return await self._gather_testing_data(scope_id)
        elif report_type == "monitoring":
            return await self._gather_monitoring_data(scope_id)
        elif report_type == "rollback":
            return await self._gather_rollback_data(scope_id)
        elif report_type == "health":
            return await self._gather_health_data(scope_id)
        return {}

    async def _gather_deployment_data(self, scope_id: Optional[str]) -> Dict[str, Any]:
        if scope_id:
            # Assume scope_id is pipeline_run_id or deployment_id
            try:
                # Try pipeline_run_id first
                deployments = await deployment_repo.get_by_pipeline_run(scope_id)
            except Exception:
                deployments = []
            if not deployments:
                try:
                    # Try direct deployment_id
                    d = await deployment_repo.get_by_id(scope_id)
                    deployments = [d]
                except Exception:
                    deployments = []
        else:
            deployments = await deployment_repo.list_all_ordered(limit=100)

        # Build stats
        summary = {"total": len(deployments), "running": 0, "stopped": 0, "failed": 0, "pending": 0}
        for d in deployments:
            status = d.get("status", "pending")
            if status in summary:
                summary[status] += 1
            else:
                summary["pending"] += 1

        return {"deployments": deployments, "summary": summary}

    async def _gather_security_data(self, scope_id: Optional[str]) -> Dict[str, Any]:
        if not scope_id:
            # Fetch overall findings across all runs
            findings = await security_finding_repo.list_all(order_by="found_at DESC", limit=150)
            severity_counts = {}
            for f in findings:
                sev = f.get("severity", "info")
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
        else:
            # Assume scope_id is pipeline_run_id
            findings = await security_finding_repo.get_by_pipeline_run(scope_id)
            severity_counts = await security_finding_repo.count_by_severity(scope_id)

        # Standardize severity counts keys
        for key in ("critical", "high", "medium", "low", "info"):
            if key not in severity_counts:
                severity_counts[key] = 0

        # Try to find corresponding agent execution meta
        agent_meta = {}
        if scope_id:
            try:
                results = await agent_result_repo.get_by_pipeline_run(scope_id)
                for r in results:
                    if r.get("agent_name") == "security":
                        agent_meta = r
                        break
            except Exception:
                pass

        return {
            "findings": findings,
            "severity_counts": severity_counts,
            "summary": {
                "total_findings": len(findings),
                "security_score": json.loads(agent_meta.get("result_json", "{}")).get("security_score", 100)
                if agent_meta else 100,
            },
        }

    async def _gather_testing_data(self, scope_id: Optional[str]) -> Dict[str, Any]:
        if not scope_id:
            raise ConfigurationException("Testing report requires a pipeline run scope_id.")

        # Find testing agent result for the run
        results = await agent_result_repo.get_by_pipeline_run(scope_id)
        test_result = None
        for r in results:
            if r.get("agent_name") == "testing":
                test_result = r
                break

        if not test_result:
            raise ResourceNotFoundException(f"No testing agent results found for run {scope_id}.")

        raw_json = test_result.get("result_json") or "{}"
        parsed = json.loads(raw_json)

        return {
            "pipeline_run_id": scope_id,
            "summary": {
                "total_tests": parsed.get("total_tests", 0),
                "passed": parsed.get("passed", 0),
                "failed": parsed.get("failed", 0),
                "coverage": parsed.get("coverage_percentage", 0),
                "duration": test_result.get("duration_seconds", 0.0),
                "test_status": test_result.get("status", "failed"),
            },
            "failures": parsed.get("failures", []),
        }

    async def _gather_monitoring_data(self, scope_id: Optional[str]) -> Dict[str, Any]:
        if not scope_id:
            # Retrieve active deployment to monitor
            active = await deployment_repo.get_active()
            if not active:
                raise ResourceNotFoundException("No active deployments to generate monitoring report.")
            scope_id = active[0]["id"]

        deployment = await deployment_repo.get_by_id(scope_id)
        snapshots = await monitoring_snapshot_repo.get_by_deployment(scope_id, limit=100)

        # Compute averages
        avg_cpu = 0.0
        avg_memory = 0.0
        avg_latency = 0.0
        latest_health = 100.0

        if snapshots:
            avg_cpu = sum(s.get("cpu_percent", 0.0) or 0.0 for s in snapshots) / len(snapshots)
            avg_memory = sum(s.get("memory_mb", 0.0) or 0.0 for s in snapshots) / len(snapshots)
            avg_latency = sum(s.get("latency_ms", 0.0) or 0.0 for s in snapshots) / len(snapshots)
            latest_health = snapshots[0].get("health_score", 100.0) or 100.0

        return {
            "deployment_id": scope_id,
            "deployment_info": deployment,
            "snapshots": snapshots,
            "summary": {
                "health_score": latest_health,
                "avg_cpu": avg_cpu,
                "avg_memory": avg_memory,
                "avg_latency": avg_latency,
            },
        }

    async def _gather_rollback_data(self, scope_id: Optional[str]) -> Dict[str, Any]:
        if scope_id:
            events = await rollback_event_repo.get_by_deployment(scope_id)
        else:
            events = await rollback_event_repo.get_recent(limit=100)

        summary: Dict[str, Any] = {
            "total": len(events),
            "completed": 0,
            "failed": 0,
            "triggered": 0,
            "success_rate": 0.0,
        }

        for e in events:
            status = e.get("status", "triggered")
            if status in summary:
                summary[status] += 1

        if summary["total"] > 0:
            summary["success_rate"] = (summary["completed"] / summary["total"]) * 100

        return {"events": events, "summary": summary}

    async def _gather_health_data(self, scope_id: Optional[str]) -> Dict[str, Any]:
        # Executive summary
        overview = await stats.get_overview_stats()
        pass_rate = await stats.get_pipeline_pass_rate()
        avg_duration = await stats.get_avg_pipeline_duration()
        severity_dist = await stats.get_security_severity_distribution()
        status_breakdown = await stats.get_deployment_status_breakdown()

        return {
            "overview": overview,
            "pipeline": {"pass_rate": pass_rate, "avg_duration": avg_duration},
            "security": {"severity_distribution": severity_dist},
            "deployments": {"status_breakdown": status_breakdown},
        }

    # ------------------------------------------------------------------
    # Markdown Rendering
    # ------------------------------------------------------------------

    def _render_markdown(self, report_type: str, data: Dict[str, Any]) -> str:
        """Render raw data into standard Github-Flavored Markdown."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        md = [
            f"# ApexDeploy — {report_type.replace('_', ' ').title()} Report",
            f"Generated at: `{now}`",
            "",
            "---",
            "",
        ]

        if report_type == "deployment":
            summary = data["summary"]
            md.extend([
                "## Summary",
                f"- **Total Deployments**: {summary['total']}",
                f"- **Running**: {summary['running']}",
                f"- **Stopped**: {summary['stopped']}",
                f"- **Failed**: {summary['failed']}",
                "",
                "## Deployments Table",
                "| ID | Image | Port | Status | Type | Deployed At |",
                "|---|---|---|---|---|---|",
            ])
            for d in data["deployments"]:
                dep_id = d.get("id", "")[:8]
                image = f"{d.get('image_name', '?')}:{d.get('image_tag', 'latest')}"
                md.append(
                    f"| `{dep_id}` | {image} | {d.get('port', '—')} | **{d.get('status', '—')}** | {d.get('deploy_type', '—')} | {d.get('deployed_at', '—')} |"
                )

        elif report_type == "security":
            summary = data["summary"]
            counts = data["severity_counts"]
            md.extend([
                "## Summary",
                f"- **Total Findings**: {summary['total_findings']}",
                f"- **Critical**: {counts.get('critical', 0)}",
                f"- **High**: {counts.get('high', 0)}",
                f"- **Medium**: {counts.get('medium', 0)}",
                f"- **Low**: {counts.get('low', 0)}",
                f"- **Info**: {counts.get('info', 0)}",
                "",
                "## Findings Detail",
                "| Severity | Category | File Path | Line | Description | Recommendation |",
                "|---|---|---|---|---|---|",
            ])
            for f in data["findings"]:
                md.append(
                    f"| **{f.get('severity', '—').upper()}** | {f.get('category', '—')} | `{f.get('file_path', '—')}` | {f.get('line_number', '—')} | {f.get('description', '—')} | {f.get('recommendation', '—')} |"
                )

        elif report_type == "testing":
            summary = data["summary"]
            md.extend([
                "## Summary",
                f"- **Status**: **{summary['test_status'].upper()}**",
                f"- **Total Tests**: {summary['total_tests']}",
                f"- **Passed**: {summary['passed']}",
                f"- **Failed**: {summary['failed']}",
                f"- **Coverage**: {summary['coverage']}%",
                f"- **Duration**: {summary['duration']:.2f}s",
                "",
            ])
            if data["failures"]:
                md.extend([
                    "## Failures",
                    "| Test Name | Error |",
                    "|---|---|",
                ])
                for f in data["failures"]:
                    md.append(f"| `{f.get('name', '—')}` | {f.get('error', '—')} |")

        elif report_type == "monitoring":
            summary = data["summary"]
            md.extend([
                "## Summary",
                f"- **Latest Health Score**: {summary['health_score']:.0f}/100",
                f"- **Average CPU Usage**: {summary['avg_cpu']:.1f}%",
                f"- **Average Memory**: {summary['avg_memory']:.1f} MB",
                f"- **Average Response Latency**: {summary['avg_latency']:.0f} ms",
                "",
                "## Resource Metrics Trend (Recent Snapshots)",
                "| Timestamp | CPU % | Memory MB | HTTP Status | Latency | Container Status |",
                "|---|---|---|---|---|---|",
            ])
            for s in data["snapshots"][-20:]:
                md.append(
                    f"| {s.get('captured_at', '—')} | {s.get('cpu_percent', 0.0):.1f}% | {s.get('memory_mb', 0.0):.1f} MB | {s.get('http_status', '—')} | {s.get('latency_ms', 0.0):.0f} ms | {s.get('container_status', '—')} |"
                )

        elif report_type == "rollback":
            summary = data["summary"]
            md.extend([
                "## Summary",
                f"- **Total Rollback Events**: {summary['total']}",
                f"- **Completed Successfully**: {summary['completed']}",
                f"- **Failed**: {summary['failed']}",
                f"- **Success Rate**: {summary['success_rate']:.1f}%",
                "",
                "## Event Log",
                "| ID | Reason | From Image | To Image | Status | Health Before | Health After | Triggered At |",
                "|---|---|---|---|---|---|---|---|",
            ])
            for e in data["events"]:
                evt_id = e.get("id", "")[:8]
                md.append(
                    f"| `{evt_id}` | {e.get('reason', '—')} | {e.get('from_image', '—')} | {e.get('to_image', '—')} | **{e.get('status', '—')}** | {e.get('health_score_before', '—')} | {e.get('health_score_after', '—')} | {e.get('triggered_at', '—')} |"
                )

        elif report_type == "health":
            overview = data["overview"]
            pipeline = data["pipeline"]
            security = data["security"]
            deployments = data["deployments"]
            md.extend([
                "## Platform KPI Overview",
                f"- **Active Repositories**: {overview.get('total_repositories', 0)}",
                f"- **Total Builds / Runs**: {overview.get('total_pipeline_runs', 0)}",
                f"- **Pipeline Pass Rate**: {pipeline.get('pass_rate', 0.0):.1f}%",
                f"- **Average Execution Time**: {pipeline.get('avg_duration', 0.0):.1f}s",
                f"- **Active Running Containers**: {overview.get('active_deployments', 0)}",
                f"- **Total Rollback Recoveries**: {overview.get('total_rollbacks', 0)}",
                f"- **Total Active Security Warnings**: {overview.get('total_security_findings', 0)}",
                "",
                "## Security Findings Distribution",
                f"- **Critical**: {security['severity_distribution'].get('critical', 0)}",
                f"- **High**: {security['severity_distribution'].get('high', 0)}",
                f"- **Medium**: {security['severity_distribution'].get('medium', 0)}",
                f"- **Low**: {security['severity_distribution'].get('low', 0)}",
                "",
                "## Deployment Container Breakdown",
            ])
            for status_key, cnt in deployments["status_breakdown"].items():
                md.append(f"- **{status_key.title()}**: {cnt}")

        return "\n".join(md)

    # ------------------------------------------------------------------
    # HTML Rendering Wrapper
    # ------------------------------------------------------------------

    def _render_html(self, report_type: str, data: Dict[str, Any]) -> str:
        """Render raw data using the styled HTML template methods."""
        if report_type == "deployment":
            return render_deployment_report_html(data)
        elif report_type == "security":
            return render_security_report_html(data)
        elif report_type == "testing":
            return render_testing_report_html(data)
        elif report_type == "monitoring":
            return render_monitoring_report_html(data)
        elif report_type == "rollback":
            return render_rollback_report_html(data)
        elif report_type == "health":
            return render_health_report_html(data)
        return ""


# Global singleton instance
report_service = ReportService()
