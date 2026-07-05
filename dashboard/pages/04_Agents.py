import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# =========================================================
# ApexDeploy Dashboard - Agents Page
# Displays active agent descriptions, tool sets, and SQLite memory states
# =========================================================

import requests
import streamlit as st
import json

from dashboard.components import inject_custom_css, render_sidebar

st.set_page_config(
    page_title="ApexDeploy - Agent Registry",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_custom_css()
render_sidebar()

API_URL = "http://localhost:8000"

st.title("🤖 Multi-Agent Registry & Memory")
st.caption("Inspect roles, capability scopes, and workspace memory checkpoints of individual AI agents.")

# Core description of the agents
agents_info = {
    "git": {
        "title": "🤖 Git Agent",
        "description": "Handles codebase ingestion. Clones repository sources, resolves target branches, scans changesets, and generates project structure metadata.",
        "tools": ["Git MCP", "Filesystem MCP", "language_detector utility"]
    },
    "code_review": {
        "title": "🔍 Code Review Agent",
        "description": "Reviews source files. Analyzes architectural layout complexity, checks duplicate lines, and queries Gemini models to generate code smells reports.",
        "tools": ["Gemini API", "Filesystem MCP", "Source parsing metrics"]
    },
    "testing": {
        "title": "🧪 Testing Agent",
        "description": "Executes workspace test suites automatically. Discovers test setups (pytest, npm, mvn) and logs execution durations, warnings, and code coverage percentages.",
        "tools": ["Terminal MCP", "pytest", "coverage.py"]
    },
    "security": {
        "title": "🛡️ Security Agent",
        "description": "Scans workspace files for vulnerabilities. Performs static dependency checking, credentials/secrets scanning, and runs Bandit vulnerability audits.",
        "tools": ["Bandit", "Regular expressions", "Filesystem scan"]
    },
    "docker": {
        "title": "🐳 Docker Agent",
        "description": "Orchestrates container packaging. Generates optimized Dockerfiles and docker-compose configurations, and compiles builds without requiring pre-existing accounts.",
        "tools": ["Docker Engine SDK", "Dockerfile builder templates"]
    },
    "deployment": {
        "title": "🚀 Deployment Agent",
        "description": "Executes local container spin-up. Adapts to specified deployment types, creates bridge networks, and returns active container IDs and host mappings.",
        "tools": ["Docker Python SDK", "Deployment Adapter interfaces"]
    },
    "monitoring": {
        "title": "📊 Monitoring Agent",
        "description": "Tracks telemetry of active deployments. Measures CPU, Memory usage, connection response codes, latency trends, and generates continuous health scores.",
        "tools": ["psutil", "HTTP endpoint probe", "Container logs aggregator"]
    },
    "rollback": {
        "title": "⏪ Rollback Agent",
        "description": "Acts as the platform's self-healing circuit. If monitoring health scores drop below healthy threshold, undeploys current version and re-activates last healthy build.",
        "tools": ["Docker Engine SDK", "SQLite deployments state history"]
    }
}

agent_tabs = st.tabs([info["title"] for info in agents_info.values()])

for idx, (agent_key, info) in enumerate(agents_info.items()):
    with agent_tabs[idx]:
        st.markdown(f"### {info['title']}")
        st.write(info["description"])
        st.markdown("**Tools Utilized**:")
        for tool in info["tools"]:
            st.markdown(f"- `{tool}`")

# Memory State inspect Section
st.markdown("---")
st.markdown("### 💾 Persistent Agent Memory Snapshots")
st.caption("Inspect state values passed between pipeline runs in the SQLite memory table.")

try:
    memory_res = requests.get(f"{API_URL}/api/agents/memory")
    if memory_res.status_code == 200:
        memories = memory_res.json()
    else:
        memories = []
except Exception as e:
    st.error(f"Failed to query agent memory API: {e}")
    memories = []

if memories:
    for mem in memories:
        with st.expander(f"🧠 {mem['agent_name'].upper()} - Key: `{mem['key']}` (Type: {mem['memory_type']})"):
            st.caption(f"Created: {mem['created_at']}")
            try:
                val = json.loads(mem["value_json"])
                st.json(val)
            except Exception:
                st.code(mem["value_json"])
else:
    st.info("No active memories stored in database yet. Memories are populated when agent pipelines execute.")
