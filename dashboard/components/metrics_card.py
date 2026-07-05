# =========================================================
# ApexDeploy Dashboard Component - Metrics Card
# Reusable glassmorphic cards for KPIs and system statistics
# =========================================================

import streamlit as st


def render_metric_card(label: str, value: str, icon: str = "📈", subtitle: str = ""):
    """Renders a beautiful glassmorphic metrics card."""
    card_html = f"""
    <div class="glass-card" style="margin-bottom: 15px; padding: 20px; border-radius: 10px; background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.08); backdrop-filter: blur(10px);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div class="metric-label" style="font-size: 0.8rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em;">{label}</div>
            <div style="font-size: 1.4rem;">{icon}</div>
        </div>
        <div class="metric-value" style="font-size: 2rem; font-weight: 700; color: #818CF8; margin: 8px 0 2px 0;">{value}</div>
        {f'<div style="font-size: 0.75rem; color: #64748B;">{subtitle}</div>' if subtitle else ''}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
