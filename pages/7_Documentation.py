import streamlit as st
from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer

st.set_page_config(page_title="Documentation", page_icon="📚", layout="wide")
apply_global_styles()

render_header("Documentation", APP_SUBTITLE, APP_STATUS)

st.markdown("## Methodology Notes")

st.markdown(
    """
    - Scope: upfront embodied carbon only.
    - Lifecycle stages: A1-A3, A4 and A5.
    - Database-driven architecture.
    - Excel workbooks are editable engineering databases.
    - Python performs the calculations.
    """
)

render_footer()