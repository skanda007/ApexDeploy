# =========================================================
# ApexDeploy - Report HTML Template Engine
# Self-contained dark-theme HTML generation for report files
# =========================================================

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =========================================================
# Shared CSS base for all HTML reports
# =========================================================

_BASE_CSS = """
<style>
    :root {
        --bg-primary: #0F172A;
        --bg-card: rgba(30, 41, 59, 0.85);
        --bg-card-alt: rgba(51, 65, 85, 0.55);
        --text-primary: #E2E8F0;
        --text-secondary: #94A3B8;
        --text-muted: #64748B;
        --accent-primary: #818CF8;
        --accent-success: #34D399;
        --accent-warning: #FBBF24;
        --accent-danger: #F87171;
        --accent-info: #38BDF8;
        --border: rgba(148, 163, 184, 0.15);
        --radius: 12px;
        --shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
        background: var(--bg-primary);
        color: var(--text-primary);
        line-height: 1.7;
        padding: 32px;
    }

    .report-header {
        text-align: center;
        margin-bottom: 40px;
        padding-bottom: 24px;
        border-bottom: 1px solid var(--border);
    }

    .report-header h1 {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, var(--accent-primary), var(--accent-info));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 8px;
    }

    .report-header .subtitle {
        color: var(--text-secondary);
        font-size: 0.95rem;
    }

    .report-header .meta {
        color: var(--text-muted);
        font-size: 0.8rem;
        margin-top: 8px;
    }

    .stat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin-bottom: 32px;
    }

    .stat-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 20px;
        text-align: center;
        backdrop-filter: blur(12px);
        box-shadow: var(--shadow);
    }

    .stat-card .value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--accent-primary);
    }

    .stat-card .label {
        font-size: 0.8rem;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }

    .stat-card.success .value { color: var(--accent-success); }
    .stat-card.warning .value { color: var(--accent-warning); }
    .stat-card.danger .value { color: var(--accent-danger); }
    .stat-card.info .value { color: var(--accent-info); }

    .section {
        margin-bottom: 32px;
    }

    .section h2 {
        font-size: 1.3rem;
        font-weight: 600;
        color: var(--accent-primary);
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border);
    }

    .section h3 {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 12px;
    }

    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
        font-size: 0.9rem;
    }

    .data-table th {
        background: var(--bg-card-alt);
        color: var(--accent-primary);
        padding: 12px 16px;
        text-align: left;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
        border-bottom: 2px solid var(--border);
    }

    .data-table td {
        padding: 10px 16px;
        border-bottom: 1px solid var(--border);
        color: var(--text-primary);
    }

    .data-table tr:nth-child(even) td {
        background: rgba(30, 41, 59, 0.4);
    }

    .data-table tr:hover td {
        background: rgba(129, 140, 248, 0.08);
    }

    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }

    .badge-critical { background: rgba(248, 113, 113, 0.2); color: var(--accent-danger); }
    .badge-high { background: rgba(251, 146, 60, 0.2); color: #FB923C; }
    .badge-medium { background: rgba(251, 191, 36, 0.2); color: var(--accent-warning); }
    .badge-low { background: rgba(52, 211, 153, 0.2); color: var(--accent-success); }
    .badge-info { background: rgba(56, 189, 248, 0.2); color: var(--accent-info); }
    .badge-passed, .badge-completed, .badge-running, .badge-healthy {
        background: rgba(52, 211, 153, 0.2); color: var(--accent-success);
    }
    .badge-failed, .badge-unhealthy {
        background: rgba(248, 113, 113, 0.2); color: var(--accent-danger);
    }
    .badge-triggered, .badge-queued, .badge-pending {
        background: rgba(251, 191, 36, 0.2); color: var(--accent-warning);
    }

    .text-block {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 16px 20px;
        margin-bottom: 16px;
        color: var(--text-primary);
        font-size: 0.9rem;
        white-space: pre-wrap;
        word-break: break-word;
    }

    .footer {
        text-align: center;
        padding-top: 24px;
        margin-top: 40px;
        border-top: 1px solid var(--border);
        color: var(--text-muted);
        font-size: 0.75rem;
    }
</style>
"""


# =========================================================
# Building-block helper functions
# =========================================================


def _severity_badge(severity: str) -> str:
    """Return an HTML badge span for a severity level."""
    css_class = f"badge-{severity}" if severity else "badge-info"
    return f'<span class="badge {css_class}">{severity}</span>'


def _status_badge(status: str) -> str:
    """Return an HTML badge span for a status value."""
    css_class = f"badge-{status}" if status else "badge-info"
    return f'<span class="badge {css_class}">{status}</span>'


def _stat_card(value: Any, label: str, variant: str = "") -> str:
    """Return a single stat card div."""
    cls = f"stat-card {variant}" if variant else "stat-card"
    return f"""
    <div class="{cls}">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
    </div>
    """


def _table(headers: List[str], rows: List[List[str]]) -> str:
    """Build an HTML data table from headers and row data."""
    ths = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = ""
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        body_rows += f"<tr>{tds}</tr>\n"
    return f"""
    <table class="data-table">
        <thead><tr>{ths}</tr></thead>
        <tbody>{body_rows}</tbody>
    </table>
    """


def _wrap_html(title: str, subtitle: str, body: str) -> str:
    """Wrap report body content in a full HTML document."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ApexDeploy — {title}</title>
    {_BASE_CSS}
</head>
<body>
    <div class="report-header">
        <h1>🚀 ApexDeploy — {title}</h1>
        <div class="subtitle">{subtitle}</div>
        <div class="meta">Generated at {now}</div>
    </div>

    {body}

    <div class="footer">
        ApexDeploy • Autonomous Git-to-Cloud Resilience Engineer • Report generated at {now}
    </div>
</body>
</html>"""


# =========================================================
# Per-report-type HTML renderers
# =========================================================


def render_deployment_report_html(data: Dict[str, Any]) -> str:
    """Render a deployment report as a complete HTML document."""
    deployments = data.get("deployments", [])
    summary = data.get("summary", {})

    # Stat cards
    cards = "".join([
        _stat_card(summary.get("total", 0), "Total Deployments"),
        _stat_card(summary.get("running", 0), "Running", "success"),
        _stat_card(summary.get("stopped", 0), "Stopped", "warning"),
        _stat_card(summary.get("failed", 0), "Failed", "danger"),
    ])
    stat_grid = f'<div class="stat-grid">{cards}</div>'

    # Deployments table
    headers = ["ID", "Image", "Port", "Status", "Type", "Deployed At"]
    rows = []
    for d in deployments:
        dep_id = str(d.get("id", ""))[:8]
        image = f"{d.get('image_name', '?')}:{d.get('image_tag', 'latest')}"
        port = str(d.get("port", "—"))
        status = _status_badge(d.get("status", "unknown"))
        deploy_type = d.get("deploy_type", "local")
        deployed_at = str(d.get("deployed_at", "—")).split(".")[0].replace("T", " ")
        rows.append([dep_id, image, port, status, deploy_type, deployed_at])

    table_html = _table(headers, rows)

    body = f"""
    <div class="section">
        <h2>📊 Deployment Summary</h2>
        {stat_grid}
    </div>
    <div class="section">
        <h2>🚀 Deployment History</h2>
        {table_html}
    </div>
    """
    return _wrap_html("Deployment Report", "Complete deployment history and status overview", body)


def render_security_report_html(data: Dict[str, Any]) -> str:
    """Render a security report as a complete HTML document."""
    findings = data.get("findings", [])
    severity_counts = data.get("severity_counts", {})
    summary = data.get("summary", {})

    # Stat cards for severity
    cards = "".join([
        _stat_card(summary.get("total_findings", 0), "Total Findings"),
        _stat_card(severity_counts.get("critical", 0), "Critical", "danger"),
        _stat_card(severity_counts.get("high", 0), "High", "warning"),
        _stat_card(severity_counts.get("medium", 0), "Medium"),
        _stat_card(severity_counts.get("low", 0), "Low", "success"),
    ])
    stat_grid = f'<div class="stat-grid">{cards}</div>'

    # Findings table
    headers = ["Severity", "Category", "File", "Line", "Description", "Recommendation"]
    rows = []
    for f in findings:
        rows.append([
            _severity_badge(f.get("severity", "info")),
            f.get("category", "—"),
            f.get("file_path", "—"),
            str(f.get("line_number", "—")),
            f.get("description", "—"),
            f.get("recommendation", "—"),
        ])

    table_html = _table(headers, rows) if rows else '<div class="text-block">No security findings detected. ✅</div>'

    body = f"""
    <div class="section">
        <h2>🛡️ Security Summary</h2>
        {stat_grid}
    </div>
    <div class="section">
        <h2>📋 Findings Detail</h2>
        {table_html}
    </div>
    """
    return _wrap_html("Security Report", "Vulnerability analysis and security findings", body)


def render_testing_report_html(data: Dict[str, Any]) -> str:
    """Render a testing report as a complete HTML document."""
    summary = data.get("summary", {})

    total_tests = summary.get("total_tests") if summary.get("total_tests") is not None else 0
    passed = summary.get("passed") if summary.get("passed") is not None else 0
    failed = summary.get("failed") if summary.get("failed") is not None else 0
    
    coverage = summary.get("coverage")
    coverage_str = f"{coverage}" if coverage is not None else "0"
    
    duration = summary.get("duration")
    duration_str = f"{duration:.1f}" if duration is not None else "0.0"

    cards = "".join([
        _stat_card(total_tests, "Total Tests"),
        _stat_card(passed, "Passed", "success"),
        _stat_card(failed, "Failed", "danger"),
        _stat_card(f"{coverage_str}%", "Coverage"),
        _stat_card(f"{duration_str}s", "Duration", "info"),
    ])
    stat_grid = f'<div class="stat-grid">{cards}</div>'

    status_text = summary.get("test_status", "unknown")
    status_color = "var(--accent-success)" if status_text == "passed" else "var(--accent-danger)"
    status_block = f"""
    <div class="text-block" style="text-align: center; font-size: 1.2rem;">
        Test Suite Status: <strong style="color: {status_color};">{status_text.upper()}</strong>
    </div>
    """

    # Failure details
    failures = data.get("failures", [])
    failures_html = ""
    if failures:
        headers = ["Test Name", "Error Message"]
        rows = [[f.get("name", "—"), f.get("error", "—")] for f in failures]
        failures_html = f"""
        <div class="section">
            <h2>❌ Failed Tests</h2>
            {_table(headers, rows)}
        </div>
        """

    body = f"""
    <div class="section">
        <h2>🧪 Testing Summary</h2>
        {stat_grid}
        {status_block}
    </div>
    {failures_html}
    """
    return _wrap_html("Testing Report", "Automated test execution results and coverage", body)


def render_monitoring_report_html(data: Dict[str, Any]) -> str:
    """Render a monitoring report as a complete HTML document."""
    summary = data.get("summary", {})
    snapshots = data.get("snapshots", [])

    health_score = summary.get("health_score")
    health_score = health_score if health_score is not None else 0.0
    avg_cpu = summary.get("avg_cpu")
    avg_cpu = avg_cpu if avg_cpu is not None else 0.0
    avg_mem = summary.get("avg_memory")
    avg_mem = avg_mem if avg_mem is not None else 0.0
    avg_lat = summary.get("avg_latency")
    avg_lat = avg_lat if avg_lat is not None else 0.0

    cards = "".join([
        _stat_card(f"{health_score:.0f}", "Health Score",
                   "success" if health_score >= 80 else "danger"),
        _stat_card(f"{avg_cpu:.1f}%", "Avg CPU"),
        _stat_card(f"{avg_mem:.1f} MB", "Avg Memory"),
        _stat_card(f"{avg_lat:.0f} ms", "Avg Latency", "info"),
    ])
    stat_grid = f'<div class="stat-grid">{cards}</div>'

    # Snapshots table
    headers = ["Time", "CPU %", "Memory MB", "HTTP Status", "Latency ms", "Health Score", "Container"]
    rows = []
    for s in snapshots[-20:]:  # Last 20 snapshots
        cpu = s.get("cpu_percent")
        cpu_str = f"{cpu:.1f}" if cpu is not None else "—"
        mem = s.get("memory_mb")
        mem_str = f"{mem:.1f}" if mem is not None else "—"
        lat = s.get("latency_ms")
        lat_str = f"{lat:.0f}" if lat is not None else "—"
        hs = s.get("health_score")
        hs_str = f"{hs:.0f}" if hs is not None else "—"

        rows.append([
            str(s.get("captured_at", "—")).split(".")[0].replace("T", " "),
            cpu_str,
            mem_str,
            str(s.get("http_status") if s.get("http_status") is not None else "—"),
            lat_str,
            hs_str,
            str(s.get("container_status") if s.get("container_status") is not None else "—"),
        ])

    table_html = _table(headers, rows) if rows else '<div class="text-block">No monitoring data available.</div>'

    body = f"""
    <div class="section">
        <h2>📊 Monitoring Summary</h2>
        {stat_grid}
    </div>
    <div class="section">
        <h2>📈 Recent Snapshots</h2>
        {table_html}
    </div>
    """
    return _wrap_html("Monitoring Report", "Application health, resource usage, and performance metrics", body)


def render_rollback_report_html(data: Dict[str, Any]) -> str:
    """Render a rollback report as a complete HTML document."""
    events = data.get("events", [])
    summary = data.get("summary", {})

    success_rate = summary.get("success_rate")
    success_rate = success_rate if success_rate is not None else 0.0

    cards = "".join([
        _stat_card(summary.get("total", 0), "Total Rollbacks"),
        _stat_card(summary.get("completed", 0), "Successful", "success"),
        _stat_card(summary.get("failed", 0), "Failed", "danger"),
        _stat_card(f"{success_rate:.0f}%", "Success Rate",
                   "success" if success_rate >= 80 else "warning"),
    ])
    stat_grid = f'<div class="stat-grid">{cards}</div>'

    # Events table
    headers = ["ID", "Reason", "From → To", "Status", "Health Before", "Health After", "Triggered At"]
    rows = []
    for e in events:
        evt_id = str(e.get("id", ""))[:8]
        from_to = f"{e.get('from_image', '?')} → {e.get('to_image', '?')}"
        status = _status_badge(e.get("status", "unknown"))
        
        hb = e.get("health_score_before")
        h_before = f"{hb:.0f}" if hb is not None else "—"
        ha = e.get("health_score_after")
        h_after = f"{ha:.0f}" if ha is not None else "—"
        
        triggered = str(e.get("triggered_at", "—")).split(".")[0].replace("T", " ")
        rows.append([evt_id, e.get("reason", "—"), from_to, status, h_before, h_after, triggered])

    table_html = _table(headers, rows) if rows else '<div class="text-block">No rollback events recorded. ✅</div>'

    body = f"""
    <div class="section">
        <h2>⏪ Rollback Summary</h2>
        {stat_grid}
    </div>
    <div class="section">
        <h2>📋 Rollback Event History</h2>
        {table_html}
    </div>
    """
    return _wrap_html("Rollback Report", "Automated rollback events and recovery outcomes", body)


def render_health_report_html(data: Dict[str, Any]) -> str:
    """Render an overall health / executive summary report as HTML."""
    overview = data.get("overview", {})
    pipeline = data.get("pipeline", {})
    security = data.get("security", {})
    deployments_summary = data.get("deployments", {})
    monitoring = data.get("monitoring", {})

    pass_rate = pipeline.get("pass_rate")
    pass_rate = pass_rate if pass_rate is not None else 0.0

    # Top-level stats
    cards = "".join([
        _stat_card(overview.get("total_repositories", 0), "Repositories"),
        _stat_card(overview.get("total_pipeline_runs", 0), "Pipeline Runs"),
        _stat_card(f"{pass_rate:.0f}%", "Pass Rate",
                   "success" if pass_rate >= 80 else "warning"),
        _stat_card(overview.get("active_deployments", 0), "Active Deployments", "info"),
        _stat_card(overview.get("total_rollbacks", 0), "Total Rollbacks",
                   "success" if overview.get("total_rollbacks", 0) == 0 else "warning"),
        _stat_card(overview.get("total_security_findings", 0), "Security Findings",
                   "success" if overview.get("total_security_findings", 0) == 0 else "danger"),
    ])
    stat_grid = f'<div class="stat-grid">{cards}</div>'

    # Security breakdown
    severity_counts = security.get("severity_distribution", {})
    sec_cards = "".join([
        _stat_card(severity_counts.get("critical", 0), "Critical", "danger"),
        _stat_card(severity_counts.get("high", 0), "High", "warning"),
        _stat_card(severity_counts.get("medium", 0), "Medium"),
        _stat_card(severity_counts.get("low", 0), "Low", "success"),
    ])
    sec_grid = f'<div class="stat-grid">{sec_cards}</div>'

    # Deployment status breakdown
    dep_status = deployments_summary.get("status_breakdown", {})
    dep_cards = "".join([
        _stat_card(dep_status.get(s, 0), s.title(), v)
        for s, v in [("running", "success"), ("stopped", "warning"),
                     ("failed", "danger"), ("pending", "info")]
        if dep_status.get(s, 0) > 0
    ])
    dep_grid = f'<div class="stat-grid">{dep_cards}</div>' if dep_cards else ""

    avg_duration = pipeline.get("avg_duration")
    avg_duration = avg_duration if avg_duration is not None else 0.0

    body = f"""
    <div class="section">
        <h2>📊 Executive Overview</h2>
        {stat_grid}
    </div>
    <div class="section">
        <h2>⚡ Pipeline Performance</h2>
        <div class="text-block">
            Average Duration: <strong>{avg_duration:.1f}s</strong>
            &nbsp;|&nbsp; Pass Rate: <strong>{pass_rate:.1f}%</strong>
            &nbsp;|&nbsp; Passed: <strong>{overview.get('passed_runs', 0)}</strong>
            &nbsp;|&nbsp; Failed: <strong>{overview.get('failed_runs', 0)}</strong>
        </div>
    </div>
    <div class="section">
        <h2>🛡️ Security Posture</h2>
        {sec_grid}
    </div>
    <div class="section">
        <h2>🚀 Deployment Status</h2>
        {dep_grid if dep_grid else '<div class="text-block">No deployments recorded yet.</div>'}
    </div>
    """
    return _wrap_html("Overall Health Report", "Executive summary across all platform dimensions", body)
