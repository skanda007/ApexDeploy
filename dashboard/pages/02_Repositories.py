import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Repositories Page
# Register and trigger pipeline execution for Git repositories
# =========================================================

import requests
import streamlit as st
import pandas as pd

from dashboard.components import inject_custom_css, render_sidebar, get_status_badge_html

st.set_page_config(
    page_title="ApexDeploy - Repositories Manager",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("📁 Repositories Manager")
st.caption("Manage registered project directories and trigger automated DevOps builds.")

# Register new repository form
with st.expander("➕ Register New Git Repository", expanded=False):
    with st.form("repo_register_form"):
        col1, col2, col3 = st.columns([1.5, 2, 1])
        with col1:
            name = st.text_input("Project Name", placeholder="my-web-app")
        with col2:
            url = st.text_input("Git Source URL (Local Path or Remote Git URL)", placeholder="https://github.com/example/app.git")
        with col3:
            branch = st.text_input("Default Branch", value="main")
            
        submitted = st.form_submit_button("Register Repository")
        if submitted:
            if not name or not url:
                st.error("Project Name and Git Source URL are required.")
            else:
                try:
                    payload = {"name": name, "url": url, "branch": branch}
                    res = requests.post(f"{API_URL}/api/repositories", json=payload)
                    if res.status_code == 201:
                        st.success(f"Successfully registered repository '{name}'!")
                        st.rerun()
                    else:
                        st.error(f"Failed to register repository: {res.json().get('detail', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Error connecting to backend: {e}")

# Fetch repositories list
try:
    res = requests.get(f"{API_URL}/api/repositories")
    if res.status_code == 200:
        repos = res.json()
    else:
        repos = []
except Exception as e:
    st.error(f"Backend API offline: {e}")
    repos = []

if repos:
    st.markdown("### Registered Codebases")
    for repo in repos:
        with st.container():
            # Render a glassmorphic card for each repo
            st.markdown(f"""
            <div class="glass-card" style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin: 0; color: #818CF8;">{repo['name']}</h4>
                        <code style="font-size: 0.8rem; color: #94A3B8;">{repo['url']}</code>
                    </div>
                    <div>
                        {get_status_badge_html(repo['status'])}
                    </div>
                </div>
                <div style="margin-top: 15px; display: flex; gap: 40px; font-size: 0.85rem; color: #94A3B8;">
                    <div>Branch: <strong style="color: #E2E8F0;">{repo['branch']}</strong></div>
                    <div>Detected Language: <strong style="color: #E2E8F0;">{repo['language'] or 'Unknown'}</strong></div>
                    <div>Registered: <strong style="color: #E2E8F0;">{repo['created_at'].split('T')[0]}</strong></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action buttons for this repository
            col_run, col_del, _ = st.columns([1, 1, 4])
            with col_run:
                if st.button("🚀 Trigger Pipeline", key=f"run_{repo['id']}"):
                    try:
                        trigger_payload = {"repo_id": repo["id"], "branch": repo["branch"], "trigger": "manual"}
                        run_res = requests.post(f"{API_URL}/api/pipeline/trigger", json=trigger_payload)
                        if run_res.status_code == 202:
                            run_id = run_res.json().get("pipeline_run_id")
                            st.success(f"Pipeline triggered! Run ID: {run_id[:8]}")
                            st.info("Check progress on 'Pipeline' page.")
                        else:
                            st.error(f"Execution failed: {run_res.json().get('detail', 'Unknown error')}")
                    except Exception as e:
                        st.error(f"Failed to trigger: {e}")
            with col_del:
                if st.button("🗑️ Delete Repository", key=f"del_{repo['id']}"):
                    try:
                        del_res = requests.delete(f"{API_URL}/api/repositories/{repo['id']}")
                        if del_res.status_code == 204:
                            st.success("Repository deleted successfully.")
                            st.rerun()
                        else:
                            st.error("Failed to delete repository record.")
                    except Exception as e:
                        st.error(f"Delete failed: {e}")
            st.markdown("<br/>", unsafe_allow_html=True)
else:
    st.info("No repositories registered. Complete the form above to add a new project.")
