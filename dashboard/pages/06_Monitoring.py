import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Monitoring Page
# Live health scores, CPU/Memory trends, and latency graphs
# =========================================================

import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard.components import inject_custom_css, render_sidebar, render_metric_card, get_status_badge_html

st.set_page_config(
    page_title="ApexDeploy - Monitoring",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("📊 Health Monitoring & Telemetry")
st.caption("Continuous resource usage tracking, HTTP probe results, and automated health scoring.")

# Fetch deployments for selector
try:
    dep_res = requests.get(f"{API_URL}/api/deployments", timeout=2)
    deployments = dep_res.json() if dep_res.status_code == 200 else []
except Exception:
    deployments = []

# Filter active / recent deployments
active_deploys = [d for d in deployments if d["status"] in ("running", "stopped", "rolled_back")]

if not active_deploys:
    st.info("No deployments with monitoring data available. Deploy a container first.")
    st.stop()

# Selector
deploy_options = {
    f"{d.get('image_name','?')}:{d.get('image_tag','?')} — {d['id'][:8]} ({d['status']})": d["id"]
    for d in active_deploys
}
selected_label = st.selectbox("Select Deployment", list(deploy_options.keys()))
selected_id = deploy_options[selected_label]

# Fetch latest health score
try:
    health_res = requests.get(f"{API_URL}/api/monitoring/health-score/{selected_id}", timeout=2)
    latest_health = health_res.json() if health_res.status_code == 200 else None
except Exception:
    latest_health = None

# Fetch monitoring snapshots
try:
    snap_res = requests.get(f"{API_URL}/api/monitoring/snapshots/{selected_id}?limit=100", timeout=2)
    snapshots = snap_res.json() if snap_res.status_code == 200 else []
except Exception:
    snapshots = []

# Health Summary KPI Cards
if latest_health:
    h_score = latest_health.get("health_score", 0) or 0
    h_cpu = latest_health.get("cpu_percent", 0) or 0
    h_mem = latest_health.get("memory_mb", 0) or 0
    h_http = latest_health.get("http_status", 0) or 0
    h_latency = latest_health.get("latency_ms", 0) or 0

    # Pick color for health score
    score_color = "#10B981" if h_score >= 80 else "#F59E0B" if h_score >= 50 else "#EF4444"
    score_icon = "💚" if h_score >= 80 else "💛" if h_score >= 50 else "💔"

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card("Health Score", f"{h_score:.0f}%", score_icon, "Composite metric")
    with c2:
        render_metric_card("CPU Usage", f"{h_cpu:.1f}%", "🖥️", "Container CPU")
    with c3:
        render_metric_card("Memory", f"{h_mem:.1f} MB", "💾", "Container RSS")
    with c4:
        render_metric_card("HTTP Status", str(int(h_http)), "🌐", "Probe response")
    with c5:
        render_metric_card("Latency", f"{h_latency:.0f} ms", "⏱️", "Response time")
else:
    st.warning("No health score data available for this deployment yet.")

st.markdown("---")

# Time-series graphs
if snapshots:
    df = pd.DataFrame(snapshots)
    df["captured_at"] = pd.to_datetime(df["captured_at"])

    st.markdown("### 📈 Resource Usage Over Time")
    chart_c1, chart_c2 = st.columns(2)

    with chart_c1:
        st.markdown("#### CPU Usage (%)")
        fig_cpu = px.area(
            df, x="captured_at", y="cpu_percent",
            color_discrete_sequence=["#818CF8"]
        )
        fig_cpu.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E2E8F0',
            height=280,
            margin=dict(t=10, b=30, l=40, r=10),
            xaxis_title="", yaxis_title="CPU %",
            showlegend=False
        )
        fig_cpu.update_traces(fill='tozeroy', fillcolor='rgba(129,140,248,0.15)')
        st.plotly_chart(fig_cpu, use_container_width=True)

    with chart_c2:
        st.markdown("#### Memory Usage (MB)")
        fig_mem = px.area(
            df, x="captured_at", y="memory_mb",
            color_discrete_sequence=["#10B981"]
        )
        fig_mem.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E2E8F0',
            height=280,
            margin=dict(t=10, b=30, l=40, r=10),
            xaxis_title="", yaxis_title="Memory MB",
            showlegend=False
        )
        fig_mem.update_traces(fill='tozeroy', fillcolor='rgba(16,185,129,0.15)')
        st.plotly_chart(fig_mem, use_container_width=True)

    # Health score and latency
    st.markdown("### 🏥 Health Score & Latency Trend")
    hl_c1, hl_c2 = st.columns(2)

    with hl_c1:
        st.markdown("#### Health Score Trend")
        fig_health = go.Figure()
        fig_health.add_trace(go.Scatter(
            x=df["captured_at"], y=df["health_score"],
            mode='lines+markers',
            line=dict(color='#818CF8', width=2),
            marker=dict(size=4),
            fill='tozeroy',
            fillcolor='rgba(129,140,248,0.1)'
        ))
        # Add threshold lines
        fig_health.add_hline(y=80, line_dash="dot", line_color="#10B981",
                             annotation_text="Healthy", annotation_position="top right")
        fig_health.add_hline(y=50, line_dash="dot", line_color="#F59E0B",
                             annotation_text="Warning", annotation_position="top right")
        fig_health.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E2E8F0',
            height=280,
            margin=dict(t=10, b=30, l=40, r=10),
            xaxis_title="", yaxis_title="Score",
            showlegend=False,
            yaxis_range=[0, 105]
        )
        st.plotly_chart(fig_health, use_container_width=True)

    with hl_c2:
        st.markdown("#### HTTP Latency (ms)")
        fig_lat = px.bar(
            df, x="captured_at", y="latency_ms",
            color_discrete_sequence=["#F59E0B"]
        )
        fig_lat.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='#E2E8F0',
            height=280,
            margin=dict(t=10, b=30, l=40, r=10),
            xaxis_title="", yaxis_title="Latency ms",
            showlegend=False
        )
        st.plotly_chart(fig_lat, use_container_width=True)

    # Snapshots raw data table
    st.markdown("### 📋 Raw Monitoring Data")
    with st.expander("Show raw snapshot table"):
        display_df = df[["captured_at", "cpu_percent", "memory_mb", "memory_percent",
                         "http_status", "latency_ms", "container_status", "health_score"]].copy()
        display_df.columns = ["Timestamp", "CPU %", "Memory MB", "Memory %",
                              "HTTP Status", "Latency ms", "Container", "Health"]
        st.dataframe(display_df, width='stretch')
else:
    st.info("No monitoring snapshots recorded for this deployment. Monitoring captures happen during pipeline runs.")
