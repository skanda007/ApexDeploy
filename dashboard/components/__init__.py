# =========================================================
# ApexDeploy Dashboard Components - Exporter
# =========================================================

import streamlit as st
from dashboard.components.sidebar import render_sidebar
from dashboard.components.metrics_card import render_metric_card
from dashboard.components.status_badge import render_status_badge, get_status_badge_html


def inject_custom_css():
    """Injects core glassmorphic dark-theme styles into active Streamlit viewports."""
    st.markdown("""
    <style>
        /* Global CSS modifications */
        .stApp {
            background-color: #0F172A;
            color: #E2E8F0;
        }
        
        /* Glassmorphic card styling */
        .glass-card {
            background: rgba(30, 41, 59, 0.45);
            border-radius: 12px;
            padding: 24px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(12px);
            margin-bottom: 20px;
        }
        
        .metric-value {
            font-size: 2.2rem;
            font-weight: 700;
            color: #818CF8;
            margin: 5px 0;
        }
        
        .metric-label {
            font-size: 0.85rem;
            color: #94A3B8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Status indicators for raw text rendering */
        .status-badge-online {
            display: inline-block;
            padding: 4px 8px;
            background-color: rgba(16, 185, 129, 0.15);
            color: #10B981;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        
        .status-badge-offline {
            display: inline-block;
            padding: 4px 8px;
            background-color: rgba(239, 68, 68, 0.15);
            color: #EF4444;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        /* Interactive buttons styling */
        .stButton>button {
            background-color: #4F46E5 !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 8px 16px !important;
            transition: all 0.3s ease !important;
        }
        
        .stButton>button:hover {
            background-color: #6366F1 !important;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }
    </style>
    """, unsafe_allow_html=True)
