import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Logs Page
# Live event log viewer and application log file browser
# =========================================================

import requests
import streamlit as st
import json
from pathlib import Path

from dashboard.components import inject_custom_css, render_sidebar

st.set_page_config(
    page_title="ApexDeploy - System Logs",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("📜 System Logs & Event Stream")
st.caption("Browse real-time event bus logs, application log files, and pipeline execution traces.")

# Tab layout: Event Log vs File Logs
tab_events, tab_files = st.tabs(["📡 Event Bus Log", "📂 Log Files"])

# ---- Tab 1: Database Event Log ----
with tab_events:
    st.markdown("### Recent Event Bus Activity")
    st.caption("Events emitted by pipeline stages, agents, and the orchestrator via the internal event bus.")

    # Fetch from event_log table via a lightweight inline query
    # (No dedicated API route for event_log yet, so we reuse pipeline details)
    try:
        runs_res = requests.get(f"{API_URL}/api/pipeline/runs", timeout=2)
        runs = runs_res.json() if runs_res.status_code == 200 else []
    except Exception:
        runs = []

    if runs:
        # Combine agent result timestamps into a synthetic event log
        events = []
        for run in runs[:5]:
            try:
                detail = requests.get(f"{API_URL}/api/pipeline/runs/{run['id']}", timeout=1.5)
                if detail.status_code == 200:
                    d = detail.json()
                    # Pipeline-level event
                    events.append({
                        "timestamp": run.get("started_at", ""),
                        "type": "PIPELINE_STARTED",
                        "source": "orchestrator",
                        "detail": f"Pipeline {run['id'][:8]} started for {d.get('repo_name', '?')}"
                    })
                    # Agent result events
                    for ar in d.get("agent_results", []):
                        events.append({
                            "timestamp": ar.get("created_at", ""),
                            "type": f"AGENT_{ar['status'].upper()}",
                            "source": ar["agent_name"],
                            "detail": f"{ar['agent_name']} agent {ar['status']} in {round(ar.get('duration_seconds', 0) or 0, 2)}s"
                        })
                    # Pipeline completion
                    if run.get("completed_at"):
                        events.append({
                            "timestamp": run.get("completed_at", ""),
                            "type": f"PIPELINE_{run['status'].upper()}",
                            "source": "orchestrator",
                            "detail": f"Pipeline {run['id'][:8]} finished — {run['status']} in {round(run.get('duration_seconds', 0) or 0, 1)}s"
                        })
            except Exception:
                pass

        # Sort by timestamp descending
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        if events:
            for evt in events[:50]:
                ts = (evt["timestamp"] or "").split(".")[0].replace("T", " ")
                etype = evt["type"]
                source = evt["source"]
                detail = evt["detail"]

                # Color coding
                if "COMPLETED" in etype or "PASSED" in etype:
                    color = "#10B981"
                elif "FAILED" in etype:
                    color = "#EF4444"
                elif "STARTED" in etype:
                    color = "#3B82F6"
                else:
                    color = "#818CF8"

                st.markdown(f"""
                <div style="padding: 8px 12px; margin-bottom: 6px; border-left: 3px solid {color};
                            background: rgba(30,41,59,0.4); border-radius: 0 6px 6px 0;">
                    <span style="color: #64748B; font-size: 0.75rem;">{ts}</span>
                    &nbsp;&nbsp;
                    <span style="color: {color}; font-weight: 600; font-size: 0.8rem;">{etype}</span>
                    &nbsp;&nbsp;
                    <span style="color: #94A3B8; font-size: 0.8rem;">({source})</span>
                    <br/>
                    <span style="color: #E2E8F0; font-size: 0.85rem;">{detail}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No events recorded yet.")
    else:
        st.info("No pipeline runs found. Events are generated when pipelines execute.")

# ---- Tab 2: Log File Browser ----
with tab_files:
    st.markdown("### Application Log Files")
    st.caption("Browse structured log files generated by the application on disk.")

    # Scan log directory
    log_dir = Path("logs")
    if not log_dir.exists():
        st.info("Logs directory not found. Application logs appear after the backend starts.")
        st.stop()

    # Gather all .log files
    log_files = sorted(log_dir.rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not log_files:
        st.info("No log files found in the logs/ directory.")
    else:
        selected_file = st.selectbox(
            "Select Log File",
            log_files,
            format_func=lambda p: str(p.relative_to(log_dir))
        )

        if selected_file:
            # Controls
            ctrl_c1, ctrl_c2 = st.columns([1, 3])
            with ctrl_c1:
                tail_lines = st.number_input("Tail lines", min_value=10, max_value=1000, value=100)
            with ctrl_c2:
                filter_text = st.text_input("Filter (contains)", placeholder="ERROR, WARNING...")

            try:
                with open(selected_file, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()

                # Take last N lines
                display_lines = all_lines[-tail_lines:]

                # Apply optional filter
                if filter_text:
                    display_lines = [ln for ln in display_lines if filter_text.lower() in ln.lower()]

                st.markdown(f"**Showing {len(display_lines)} lines from `{selected_file.name}`**")

                # Color-coded display
                log_html_parts = []
                for line in display_lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if "ERROR" in stripped or "CRITICAL" in stripped:
                        color = "#EF4444"
                    elif "WARNING" in stripped:
                        color = "#F59E0B"
                    elif "INFO" in stripped:
                        color = "#94A3B8"
                    elif "DEBUG" in stripped:
                        color = "#64748B"
                    else:
                        color = "#CBD5E1"

                    # Escape HTML characters
                    safe = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    log_html_parts.append(
                        f'<div style="font-family: monospace; font-size: 0.78rem; '
                        f'color: {color}; padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.03);">'
                        f'{safe}</div>'
                    )

                log_html = "\n".join(log_html_parts)
                st.markdown(
                    f'<div style="max-height: 500px; overflow-y: auto; background: rgba(15,23,42,0.8); '
                    f'border-radius: 8px; padding: 12px; border: 1px solid rgba(255,255,255,0.06);">'
                    f'{log_html}</div>',
                    unsafe_allow_html=True
                )
            except Exception as e:
                st.error(f"Failed to read log file: {e}")
