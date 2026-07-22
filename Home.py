import glob

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
    status=APP_STATUS,
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

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown(
        """
<div class="nav-card" style="text-align:center;">
<h3>📚</h3>
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



st.markdown("")

if st.button(
    "🔥 Start Fire Design Assessment",
    type="primary",
    width='stretch',
):
    # Looked up by its "2_" prefix rather than hardcoded, so renaming
    # the file (e.g. to add/change its sidebar icon) can't silently
    # break this button.
    fire_design_pages = glob.glob("pages/2_*.py")

    if fire_design_pages:
        st.switch_page(fire_design_pages[0])
    else:
        st.error("Fire Design page not found. Check it hasn't been moved or renamed to something outside the pages/2_* pattern.")

from utils.network_info import get_app_url, generate_qr_code_bytes

# ==========================================================
# Connect Here
# ==========================================================

with st.expander("📶 Connect Here (for other devices on this network)", expanded=False):

    app_url = get_app_url(port=8501)

    col1, col2 = st.columns([1, 2])

    with col1:
        qr_bytes = generate_qr_code_bytes(app_url)
        st.image(qr_bytes, width=200)

    with col2:
        st.markdown("**Scan this QR code on your iPad's camera app**, or type the address below into Safari:")
        st.code(app_url, language=None)
        st.caption(
            "Make sure your device is connected to the same WiFi network as this host machine."
        )

render_footer()