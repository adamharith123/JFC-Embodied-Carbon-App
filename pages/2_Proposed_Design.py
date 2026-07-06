import streamlit as st
from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer

st.set_page_config(page_title="Proposed Design", page_icon="🏢", layout="wide")
apply_global_styles()

render_header("Proposed New Design", APP_SUBTITLE, APP_STATUS)

st.info("Step 3 will migrate the proposed design workflow here.")

render_footer()