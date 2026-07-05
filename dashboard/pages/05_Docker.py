import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Docker Page
# Container lifecycle manager with build status and image tracking
# =========================================================

import requests
import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go

from dashboard.components import inject_custom_css, render_sidebar, render_metric_card, get_status_badge_html

st.set_page_config(
    page_title="ApexDeploy - Docker Manager",
    page_icon="🐳",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("🐳 Docker & Container Manager")
st.caption("Track container builds, image inventories, runtime statuses, and port bindings.")

# Fetch deployments
try:
    res = requests.get(f"{API_URL}/api/deployments", timeout=2)
    deployments = res.json() if res.status_code == 200 else []
except Exception:
    deployments = []

# KPI summary row
running = [d for d in deployments if d["status"] == "running"]
stopped = [d for d in deployments if d["status"] == "stopped"]
failed = [d for d in deployments if d["status"] == "failed"]
rolled_back = [d for d in deployments if d["status"] == "rolled_back"]

col1, col2, col3, col4 = st.columns(4)
with col1:
    render_metric_card("Running", str(len(running)), "🟢", "Active containers")
with col2:
    render_metric_card("Stopped", str(len(stopped)), "⏹️", "Stopped containers")
with col3:
    render_metric_card("Failed", str(len(failed)), "❌", "Build or runtime errors")
with col4:
    render_metric_card("Rolled Back", str(len(rolled_back)), "⏪", "Auto-reverted deploys")

st.markdown("---")

# Deployment status distribution chart
if deployments:
    st.markdown("### 📊 Container Status Distribution")
    chart_col, list_col = st.columns([1, 2])

    with chart_col:
        status_counts = {}
        for d in deployments:
            s = d["status"]
            status_counts[s] = status_counts.get(s, 0) + 1

        fig = go.Figure(data=[go.Pie(
            labels=list(status_counts.keys()),
            values=list(status_counts.values()),
            hole=0.45,
            marker=dict(colors=[
                '#10B981' if s == 'running' else
                '#EF4444' if s == 'failed' else
                '#F59E0B' if s == 'rolled_back' else
                '#64748B'
                for s in status_counts.keys()
            ]),
            textinfo='label+value'
        )])
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E2E8F0',
            height=280,
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

    with list_col:
        st.markdown("### 📦 Container Registry")
        for d in deployments:
            image_label = f"{d.get('image_name', 'unknown')}:{d.get('image_tag', 'latest')}"
            port_label = f"Port {d.get('port', 'N/A')}"
            deployed_at = (d.get("deployed_at") or "N/A").split("T")[0]

            st.markdown(f"""
            <div class="glass-card" style="padding: 16px; margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong style="color: #818CF8;">{image_label}</strong>
                        <br/>
                        <span style="font-size: 0.8rem; color: #94A3B8;">
                            Container: <code>{(d.get('container_id') or 'N/A')[:12]}</code>
                            &nbsp;|&nbsp; {port_label}
                            &nbsp;|&nbsp; Deployed: {deployed_at}
                        </span>
                    </div>
                    <div>{get_status_badge_html(d['status'])}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Stop button for running deployments
            if d["status"] == "running":
                if st.button(f"⏹️ Stop {d['id'][:8]}", key=f"stop_{d['id']}"):
                    try:
                        stop_res = requests.post(f"{API_URL}/api/deployments/{d['id']}/stop")
                        if stop_res.status_code == 200:
                            st.success(f"Container {d['id'][:8]} stopped.")
                            st.rerun()
                        else:
                            st.error(f"Stop failed: {stop_res.json().get('detail', 'Error')}")
                    except Exception as e:
                        st.error(f"Backend error: {e}")
else:
    st.info("No container deployments found. Trigger a pipeline from the Repositories page to create one.")
