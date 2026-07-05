# =========================================================
# ApexDeploy Dashboard Component - Status Badge
# Renders colored badges for pipeline and container states
# =========================================================

import streamlit as st


def get_status_badge_html(status_text: str) -> str:
    """Returns HTML for a state badge with suitable colors based on input."""
    status_lower = status_text.lower()
    
    # Define colors
    if status_lower in ("passed", "running", "healthy", "online", "active"):
        bg = "rgba(16, 185, 129, 0.15)"
        fg = "#10B981"
        border = "rgba(16, 185, 129, 0.3)"
        dot = "●"
    elif status_lower in ("failed", "unhealthy", "offline", "error"):
        bg = "rgba(239, 68, 68, 0.15)"
        fg = "#EF4444"
        border = "rgba(239, 68, 68, 0.3)"
        dot = "●"
    elif status_lower in ("rolled_back", "rolled back", "rollback"):
        bg = "rgba(245, 158, 11, 0.15)"
        fg = "#F59E0B"
        border = "rgba(245, 158, 11, 0.3)"
        dot = "⏪"
    elif status_lower in ("queued", "pending", "building", "stopped"):
        bg = "rgba(100, 116, 139, 0.15)"
        fg = "#94A3B8"
        border = "rgba(100, 116, 139, 0.3)"
        dot = "○"
    else:
        bg = "rgba(129, 140, 248, 0.15)"
        fg = "#818CF8"
        border = "rgba(129, 140, 248, 0.3)"
        dot = "◆"

    return f"""
    <span style="
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        background-color: {bg};
        color: {fg};
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid {border};
    ">
        <span>{dot}</span> {status_text.upper()}
    </span>
    """


def render_status_badge(status_text: str):
    """Directly renders a status badge in Streamlit using st.markdown."""
    st.markdown(get_status_badge_html(status_text), unsafe_allow_html=True)
