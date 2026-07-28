st.markdown(
    """
    <style>
    div[data-testid="stForm"], div.stTextInput {
        max-width: 600px !important;
        margin: 0 auto;
    }
    
    /* FIX FOR METRIC CARDS TEXT VISIBILITY IN MOBILE & DARK MODE */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa !important;
        padding: 12px !important;
        border-radius: 8px !important;
        border-left: 5px solid #0284c7 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    }
    
    /* Metric Label (Title) Text Color */
    div[data-testid="stMetricLabel"] label, div[data-testid="stMetricLabel"] p {
        color: #1e293b !important;
        font-weight: 600 !important;
        font-size: 14px !important;
    }
    
    /* Metric Value (Numbers) Text Color */
    div[data-testid="stMetricValue"] div {
        color: #0f172a !important;
        font-weight: bold !important;
    }
    
    /* Metric Delta (Sub-text like +3 Today) */
    div[data-testid="stMetricDelta"] div {
        font-weight: bold !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)
