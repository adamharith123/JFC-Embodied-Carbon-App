import streamlit as st
from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
apply_global_styles()

render_header("Settings", APP_SUBTITLE, APP_STATUS)

st.info("General settings will be added later.")

render_footer()
