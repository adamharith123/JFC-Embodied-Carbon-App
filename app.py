import streamlit as st

from utils.constants import APP_NAME, APP_VERSION, APP_STATUS, APP_SUBTITLE
from utils.styles import apply_global_styles, render_header, render_footer
from utils.session import initialise_session_state, load_databases_into_session


# ==========================================================
# PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🚒",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()
initialise_session_state()

if not st.session_state.get("databases_loaded", False):
    load_databases_into_session()


# ==========================================================
# HERO
# ==========================================================

render_header(
    title=APP_NAME,
    subtitle=APP_SUBTITLE,
    status=f"{APP_VERSION} · {APP_STATUS}",
)


# ==========================================================
# WELCOME
# ==========================================================

st.markdown("## Welcome")

st.markdown(
    """
The **Fire Safety Embodied Carbon App** estimates the upfront embodied carbon
of fire safety systems in buildings.

The application integrates engineering databases to automate fire safety
system selection, apparatus quantification and embodied carbon assessment.
"""
)

st.divider()


# ==========================================================
# ASSESSMENT METHODS
# ==========================================================

st.markdown("## Assessment Methods")

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.markdown(
        """
<div class="nav-card" style="text-align:center;">
<h3>📘</h3>
<h4>Deemed-to-Satisfy (DtS)</h4>
</div>
""",
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
<div class="nav-card" style="text-align:center;">
<h3>⚙️</h3>
<h4>Performance Solution</h4>
</div>
""",
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
<div class="nav-card" style="text-align:center;">
<h3>🏢</h3>
<h4>Existing Building</h4>
</div>
""",
        unsafe_allow_html=True,
    )


st.markdown("")

st.button(
    "🔥 Start Fire Design Assessment",
    type="primary",
    use_container_width=True,
)


render_footer()
