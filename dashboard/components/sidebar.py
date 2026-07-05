# =========================================================
# ApexDeploy Dashboard Component - Sidebar
# Dynamic health checks, backend connections, and agent state tracker
# =========================================================

import psutil
import requests
import streamlit as st

API_URL = "http://localhost:8000"


def render_sidebar():
    """Renders the common navigation sidebar and systems status check."""
    st.sidebar.image("https://img.icons8.com/nolan/128/bot.png", width=70)
    st.sidebar.title("Configuration")

    # 1. API Health Check
    try:
        response = requests.get(f"{API_URL}/api/health/details", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            st.sidebar.markdown(
                '**Backend API:** <span class="status-badge-online">● ONLINE</span>',
                unsafe_allow_html=True
            )
            st.sidebar.success(f"Connected to {health_data.get('environment', 'prod')} environment")

            # Show CPU/Memory from API detailed check
            sys_info = health_data.get("system", {})
            cpu = sys_info.get("cpu_percent", 0)
            mem = sys_info.get("memory", {}).get("percent", 0)

            st.sidebar.markdown("---")
            st.sidebar.markdown("### Host Performance")
            st.sidebar.write(f"🖥️ CPU Usage: **{cpu}%**")
            st.sidebar.progress(cpu / 100.0)
            st.sidebar.write(f"💾 Memory Usage: **{mem}%**")
            st.sidebar.progress(mem / 100.0)
        else:
            raise Exception("API returned non-200 status")
    except requests.exceptions.Timeout:
        # Detailed check timed out — try simple health ping as fallback
        try:
            simple = requests.get(f"{API_URL}/api/health", timeout=2)
            if simple.status_code == 200:
                st.sidebar.markdown(
                    '**Backend API:** <span class="status-badge-online">● ONLINE</span>',
                    unsafe_allow_html=True
                )
                st.sidebar.info("Backend running (detailed metrics unavailable)")
                cpu = psutil.cpu_percent()
                mem = psutil.virtual_memory().percent
                st.sidebar.markdown("---")
                st.sidebar.markdown("### Host Performance")
                st.sidebar.write(f"🖥️ CPU Usage: **{cpu}%**")
                st.sidebar.progress(cpu / 100.0)
                st.sidebar.write(f"💾 Memory Usage: **{mem}%**")
                st.sidebar.progress(mem / 100.0)
            else:
                raise Exception("Simple health check failed")
        except Exception:
            st.sidebar.markdown(
                '**Backend API:** <span class="status-badge-offline">○ OFFLINE</span>',
                unsafe_allow_html=True
            )
            st.sidebar.error("FastAPI Backend not responding on Port 8000.")
    except Exception:
        st.sidebar.markdown(
            '**Backend API:** <span class="status-badge-offline">○ OFFLINE</span>',
            unsafe_allow_html=True
        )
        st.sidebar.error("FastAPI Backend not responding on Port 8000.")

        # Local fallback system performance
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Host Performance")
        st.sidebar.write(f"🖥️ CPU Usage: **{cpu}%**")
        st.sidebar.progress(cpu / 100.0)
        st.sidebar.write(f"💾 Memory Usage: **{mem}%**")
        st.sidebar.progress(mem / 100.0)

    # 2. Agent Status Registry
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Agent Registry")

    # Fetch status of active pipelines to dynamically determine agent busy states
    try:
        pipeline_res = requests.get(f"{API_URL}/api/pipeline/runs", timeout=1)
        if pipeline_res.status_code == 200 and pipeline_res.json():
            runs = pipeline_res.json()
            active_run = next((r for r in runs if r["status"] == "running"), None)
        else:
            active_run = None
    except Exception:
        active_run = None

    if active_run:
        stage = active_run.get("current_stage", "running")
        st.sidebar.info(f"Pipeline running: `{active_run['id'][:8]}`")

        # Mark active stage agent as working
        st.sidebar.caption(f"🤖 Git Agent: **{'Working' if stage == 'git' else 'Idle'}**")
        st.sidebar.caption(f"🔍 Review Agent: **{'Working' if stage == 'analysis' else 'Idle'}**")
        st.sidebar.caption(f"🧪 Testing Agent: **{'Working' if stage == 'analysis' else 'Idle'}**")
        st.sidebar.caption(f"🛡️ Security Agent: **{'Working' if stage == 'analysis' else 'Idle'}**")
        st.sidebar.caption(f"🐳 Docker Agent: **{'Working' if stage == 'docker' else 'Idle'}**")
        st.sidebar.caption(f"🚀 Deploy Agent: **{'Working' if stage == 'deployment' else 'Idle'}**")
        st.sidebar.caption(f"📊 Monitor Agent: **{'Working' if stage == 'monitoring' else 'Idle'}**")
        st.sidebar.caption(f"⏪ Rollback Agent: **{'Working' if stage == 'rollback' else 'Idle'}**")
    else:
        st.sidebar.caption("🤖 Git Agent: **Idle**")
        st.sidebar.caption("🔍 Review Agent: **Idle**")
        st.sidebar.caption("🧪 Testing Agent: **Idle**")
        st.sidebar.caption("🛡️ Security Agent: **Idle**")
        st.sidebar.caption("🐳 Docker Agent: **Idle**")
        st.sidebar.caption("🚀 Deploy Agent: **Idle**")
        st.sidebar.caption("📊 Monitor Agent: **Idle**")
        st.sidebar.caption("⏪ Rollback Agent: **Idle**")

    st.sidebar.markdown("---")
    st.sidebar.caption("ApexDeploy © 2026")
    st.sidebar.caption("Kaggle AI Agents Capstone Project")
