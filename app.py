import streamlit as st

from utils.constants import APP_NAME, APP_VERSION, APP_STATUS, APP_SUBTITLE
from utils.styles import apply_global_styles, render_header, render_footer
from utils.session import initialise_session_state, load_databases_into_session
from utils.database_loader import database_status_summary

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

render_header(
    title=APP_NAME,
    subtitle=APP_SUBTITLE,
    status=f"{APP_VERSION} · {APP_STATUS}",
)

st.markdown("## Welcome")

st.markdown(
    """
    This application estimates the upfront embodied carbon of fire safety systems in buildings.

    The tool is designed around three editable engineering databases:

    - **Embodied Carbon Database**
    - **Australian Standards / NCC Database**
    - **Component Database**
    """
)

st.divider()

st.markdown("## Application Workflow")

st.markdown(
    """
    <div class="small-note">
    <strong>Workflow:</strong> Building information → Standards database → Quantity estimation → Carbon database → Embodied carbon calculation → Dashboard → Report.
    </div>
    """,
    unsafe_allow_html=True,
)

st.divider()

st.markdown("## Database Status")

status = database_status_summary()

cols = st.columns(3)

for col, (name, info) in zip(cols, status.items()):
    with col:
        if info["exists"]:
            st.success(f"{name} loaded")
        else:
            st.warning(f"{name} missing")

        st.caption(str(info["path"]))
        st.metric("Sheets", len(info["sheets"]))
        st.metric("Rows detected", info["rows"])

st.divider()

st.markdown("## Assessment Pathways")

c1, c2 = st.columns(2)

with c1:
    st.markdown(
        """
        <div class="nav-card">
            <h3>🏢 Proposed New Design</h3>
            <p>Estimate fire safety system quantities from building class, area, storeys and hazard classification.</p>
            <p><strong>Status:</strong> Ready for Step 3</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        """
        <div class="nav-card">
            <h3>📋 Existing Design</h3>
            <p>Input known fire safety system quantities from plans, BOQs or asset registers.</p>
            <p><strong>Status:</strong> Ready for Step 2</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_footer()