import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Pipeline Page
# Visualizer for active and historical pipeline execution runs
# =========================================================

import requests
import streamlit as st
import json
import pandas as pd

from dashboard.components import inject_custom_css, render_sidebar, get_status_badge_html

st.set_page_config(
    page_title="ApexDeploy - Pipeline Runs",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("🔄 Pipeline Runs")
st.caption("Inspect pipeline steps, execution times, quality gate statuses, and rollback events.")

# Fetch pipeline runs
try:
    res = requests.get(f"{API_URL}/api/pipeline/runs")
    if res.status_code == 200:
        runs = res.json()
    else:
        runs = []
except Exception as e:
    st.error(f"Backend API offline: {e}")
    runs = []

if not runs:
    st.info("No pipeline execution records found in database.")
else:
    # Sidebar selection for pipeline run
    run_options = {f"{r['repo_name']} - {r['id'][:8]} ({r['status'].upper()})": r["id"] for r in runs}
    selected_label = st.selectbox("Select Pipeline Run", list(run_options.keys()))
    selected_run_id = run_options[selected_label]

    # Fetch full run details
    try:
        details_res = requests.get(f"{API_URL}/api/pipeline/runs/{selected_run_id}")
        if details_res.status_code == 200:
            details = details_res.json()
        else:
            details = None
    except Exception as e:
        st.error(f"Failed to fetch run details: {e}")
        details = None

    if details:
        st.markdown(f"### Pipeline Run: `{details['id']}`")
        
        # Overview Cards
        meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
        with meta_col1:
            st.markdown(f"**Repository**: `{details['repo_name']}`")
        with meta_col2:
            st.markdown(f"**Trigger Source**: `{details['trigger']}`")
        with meta_col3:
            st.markdown(f"**Duration**: `{round(details['duration_seconds'] or 0, 1)} seconds`")
        with meta_col4:
            st.markdown(f"**Status**: {get_status_badge_html(details['status'])}", unsafe_allow_html=True)
            
        st.markdown("---")

        # Visual pipeline stages list
        st.markdown("### 🗺️ Stage Timeline")
        
        stages = ["git", "analysis", "docker", "deployment", "monitoring", "rollback"]
        stage_names = {
            "git": "📥 Git Repository Checkout",
            "analysis": "🔍 Quality Gates Analysis",
            "docker": "🐳 Container Containerization",
            "deployment": "🚀 Local Deployment",
            "monitoring": "📊 Health Probe Monitoring",
            "rollback": "⏪ Automated Failure Rollback"
        }
        
        # Build stage status details map
        agent_status_map = {res["agent_name"]: res for res in details.get("agent_results", [])}
        
        # Custom css steps display
        steps_cols = st.columns(len(stages))
        for idx, stage in enumerate(stages):
            with steps_cols[idx]:
                # Determine stage status
                stage_status = "pending"
                duration = 0
                
                # Check mapping for agents in that stage
                if stage == "git":
                    agent = agent_status_map.get("git")
                elif stage == "analysis":
                    # Check code_review, testing, and security
                    agents = [agent_status_map.get(n) for n in ["code_review", "testing", "security"]]
                    agent = next((a for a in agents if a), None)
                else:
                    agent = agent_status_map.get(stage)
                    
                if agent:
                    stage_status = agent["status"]
                    duration = agent["duration_seconds"] or 0
                
                st.markdown(f"""
                <div class="glass-card" style="padding: 15px; text-align: center; border-top: 4px solid {
                    '#10B981' if stage_status == 'completed' else
                    '#EF4444' if stage_status == 'failed' else
                    '#3B82F6' if stage_status == 'running' else
                    '#475569'
                };">
                    <div style="font-size: 0.85rem; font-weight: bold; margin-bottom: 5px;">{stage.upper()}</div>
                    <div>{get_status_badge_html(stage_status)}</div>
                    <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 8px;">{round(duration, 1)}s elapsed</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # Drill down details by Agent Result Tabs
        st.markdown("### 🤖 Agent Execution Summaries")
        
        agent_tabs = st.tabs([res["agent_name"].replace("_", " ").title() for res in details.get("agent_results", [])] or ["No Agent Results"])
        
        for idx, result in enumerate(details.get("agent_results", [])):
            with agent_tabs[idx]:
                st.write(f"⏱️ Execution Duration: **{round(result['duration_seconds'] or 0, 2)} seconds**")
                st.write(f"📁 Artifact Created: `{result['artifact_path'] or 'None'}`")
                
                # Display pretty JSON result payload
                try:
                    parsed_json = json.loads(result["result_json"])
                    st.json(parsed_json)
                except Exception:
                    st.code(result["result_json"])
                    
        # Context tab
        st.markdown("### 📄 Pipeline Context JSON")
        with st.expander("Show Context Details"):
            try:
                context_dict = json.loads(details["context_json"])
                st.json(context_dict)
            except Exception:
                st.write(details["context_json"])
