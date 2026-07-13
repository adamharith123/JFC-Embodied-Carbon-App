import streamlit as st
from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer

st.set_page_config(page_title="Reports", page_icon="📄", layout="wide")
apply_global_styles()

render_header("Reports", APP_SUBTITLE, APP_STATUS)

st.info("Report generation will be added later.")

render_footer()