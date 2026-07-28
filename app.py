import calendar
import csv
import hashlib
import sqlite3
from datetime import date, datetime, timedelta
from io import StringIO

import pandas as pd
import streamlit as st  # <-- Iska hona zaroori hai

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & CUSTOM STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SN Clinic Management System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Global Text & Labels Black Color Fix */
    div[data-testid="stMetric"], 
    div[data-testid="stMetricLabel"], 
    div[data-testid="stMetricValue"], 
    div[data-testid="stMetricDelta"],
    .stMetric label,
    p, span, h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
    }

    /* Metric Cards Styling for Mobile & Desktop */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        padding: 12px 16px !important;
        border-radius: 10px !important;
        border: 1px solid #d1d5db !important;
        border-left: 6px solid #0284c7 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08) !important;
    }

    div[data-testid="stMetricValue"] {
        font-weight: 800 !important;
        color: #000000 !important;
    }

    div[data-testid="stMetricLabel"] {
        font-weight: 700 !important;
        color: #1a1a1a !important;
    }

    /* Tables Font Black Fix */
    div[data-testid="stDataFrame"] * {
        color: #000000 !important;
    }

    div[data-testid="stForm"], div.stTextInput {
        max-width: 600px !important;
        margin: 0 auto;
    }
    </style>
""",
    unsafe_allow_html=True,
)
