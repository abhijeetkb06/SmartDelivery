"""
SmartDelivery - myQ Smart Delivery Intelligence
Main Streamlit application with 3 tabs: My myQ, myQ Command Center, Vector Search & AI Copilot.
"""

import sys
from pathlib import Path

# Ensure app/ is on the path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import streamlit_shadcn_ui as ui
from streamlit_autorefresh import st_autorefresh
from styles import THEME_CSS
import config
import couchbase_client as cb

st.set_page_config(
    page_title="myQ Smart Delivery Intelligence",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject theme CSS ──
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ── Header ──
st.markdown("""<div class="app-header">
    <h1>myQ Smart Delivery Intelligence</h1>
    <p>AI-powered package delivery monitoring for your garage &mdash; powered by Couchbase</p>
</div>""", unsafe_allow_html=True)


# ── Connect to Couchbase (cached) ──
@st.cache_resource
def init_cluster():
    return cb.get_cluster()


try:
    cluster = init_cluster()
    st.markdown(
        '<div style="text-align:center;margin-top:-1rem;margin-bottom:1rem;">'
        '<span class="connection-dot"></span>'
        '<span style="color:#166534;font-size:0.75rem;font-weight:500;">'
        'Connected to Couchbase Capella</span></div>',
        unsafe_allow_html=True,
    )
except Exception as e:
    st.error(f"Failed to connect to Couchbase: {e}")
    st.info("Check CB_CONN_STR, CB_USERNAME, CB_PASSWORD in your .env file.")
    st.stop()


# ── Tabs (shadcn-ui) ──
selected_tab = ui.tabs(
    options=["My myQ", "myQ Command Center", "Vector Search & AI Copilot"],
    default_value="My myQ",
    key="main_tabs",
)

st.markdown("")

if selected_tab == "My myQ":
    import tab_home
    tab_home.render(cluster)
elif selected_tab == "myQ Command Center":
    # Auto-refresh when Command Center is active and generator is running (or just started)
    metrics = cb.get_pipeline_metrics(cluster)
    gen_live = (metrics and metrics.get("running", False)) or st.session_state.get("gen_starting", False)
    if gen_live:
        st_autorefresh(interval=config.AUTO_REFRESH_MS, key="ops_autorefresh")
        # Clear the starting flag once metrics confirm the generator is live
        if metrics and metrics.get("running", False):
            st.session_state.pop("gen_starting", None)
    import tab_ops
    tab_ops.render(cluster)
else:
    import tab_search_copilot
    tab_search_copilot.render(cluster)
