import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Settings Page
# Displays configuration, environment info, and system diagnostics
# =========================================================

import requests
import streamlit as st
import platform
import sys

from dashboard.components import inject_custom_css, render_sidebar

st.set_page_config(
    page_title="ApexDeploy - Settings",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("⚙️ System Settings & Configuration")
st.caption("Inspect runtime configuration, environment variables, and system diagnostics.")

# Fetch backend settings
try:
    settings_res = requests.get(f"{API_URL}/api/settings", timeout=2)
    backend_settings = settings_res.json() if settings_res.status_code == 200 else None
except Exception:
    backend_settings = None

# System Diagnostics Card
st.markdown("### 🖥️ System Diagnostics")
diag_c1, diag_c2, diag_c3, diag_c4 = st.columns(4)
with diag_c1:
    st.markdown(f"""
    <div class="glass-card" style="padding: 16px; text-align: center;">
        <div class="metric-label">Python Version</div>
        <div class="metric-value" style="font-size: 1.4rem;">{platform.python_version()}</div>
    </div>
    """, unsafe_allow_html=True)
with diag_c2:
    st.markdown(f"""
    <div class="glass-card" style="padding: 16px; text-align: center;">
        <div class="metric-label">Operating System</div>
        <div class="metric-value" style="font-size: 1.4rem;">{platform.system()}</div>
    </div>
    """, unsafe_allow_html=True)
with diag_c3:
    st.markdown(f"""
    <div class="glass-card" style="padding: 16px; text-align: center;">
        <div class="metric-label">Architecture</div>
        <div class="metric-value" style="font-size: 1.4rem;">{platform.machine()}</div>
    </div>
    """, unsafe_allow_html=True)
with diag_c4:
    st.markdown(f"""
    <div class="glass-card" style="padding: 16px; text-align: center;">
        <div class="metric-label">Backend API</div>
        <div class="metric-value" style="font-size: 1.4rem;">{'Online' if backend_settings else 'Offline'}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

if backend_settings:
    # Group settings by category
    categories = {
        "Application": ["APP_NAME", "APP_ENV", "APP_DEBUG", "APP_VERSION"],
        "Server": ["API_HOST", "API_PORT", "API_RELOAD", "API_WORKERS",
                    "DASHBOARD_HOST", "DASHBOARD_PORT", "API_URL"],
        "Database": ["DATABASE_URL", "DATABASE_ECHO"],
        "Docker": ["DOCKER_SOCKET", "DOCKER_TIMEOUT", "DOCKER_REGISTRY", "DOCKER_NETWORK"],
        "Git": ["GIT_CLONE_DEPTH", "GIT_TIMEOUT", "GITHUB_TOKEN"],
        "Directories": ["WORKSPACES_DIR", "ARTIFACTS_DIR"],
        "Logging": ["LOG_LEVEL", "LOG_DIR", "LOG_FORMAT", "LOG_MAX_SIZE_MB", "LOG_BACKUP_COUNT"],
        "Security": ["SECRET_KEY", "ALLOWED_HOSTS", "CORS_ORIGINS"],
        "Monitoring": ["HEALTH_CHECK_INTERVAL", "HEALTH_CHECK_TIMEOUT", "UNHEALTHY_THRESHOLD"],
        "Pipeline": ["PIPELINE_TIMEOUT", "MAX_CONCURRENT_PIPELINES", "PIPELINE_RETRY_COUNT"],
        "Telemetry": ["TELEMETRY_ENABLED", "METRICS_RETENTION_DAYS"],
        "Google AI": ["GOOGLE_API_KEY"],
    }

    st.markdown("### 📋 Configuration Settings")
    
    tab_list = list(categories.keys())
    tabs = st.tabs(tab_list)

    for idx, (cat_name, keys) in enumerate(categories.items()):
        with tabs[idx]:
            for key in keys:
                val = backend_settings.get(key, "—")
                # Mask sensitive keys
                is_masked = val == "********"
                display_val = val if not is_masked else "🔒 ********"

                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center;
                            padding: 8px 12px; margin-bottom: 4px;
                            border-bottom: 1px solid rgba(255,255,255,0.04);">
                    <span style="color: #94A3B8; font-size: 0.85rem; font-family: monospace;">{key}</span>
                    <span style="color: {'#EF4444' if is_masked else '#E2E8F0'}; font-size: 0.85rem;">
                        <code>{display_val}</code>
                    </span>
                </div>
                """, unsafe_allow_html=True)
else:
    st.warning("Backend API is offline. Start the FastAPI server to inspect configuration.")
    st.markdown("Start the backend with:")
    st.code("uvicorn src.main:app --reload --port 8000")

# Environment details
st.markdown("---")
st.markdown("### 🔧 Runtime Environment")
with st.expander("Show Python Environment Details"):
    st.write(f"**Executable**: `{sys.executable}`")
    st.write(f"**Platform**: `{sys.platform}`")
    st.write(f"**Version Info**: `{sys.version}`")
    st.write(f"**Prefix**: `{sys.prefix}`")

st.markdown("---")
st.caption("ApexDeploy © 2026 — Kaggle AI Agents Capstone Project")
