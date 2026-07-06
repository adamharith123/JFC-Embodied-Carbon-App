import streamlit as st
from utils.constants import APP_NAME, APP_STATUS, APP_SUBTITLE
from utils.styles import apply_global_styles, render_header, render_footer
from utils.database_loader import database_status_summary

st.set_page_config(page_title="Home", page_icon="🏠", layout="wide")
apply_global_styles()

render_header(APP_NAME, APP_SUBTITLE, APP_STATUS)

st.markdown("## Home")
st.write("This is the main application overview.")

st.markdown("## Database Status")

status = database_status_summary()

for name, info in status.items():
    if info["exists"]:
        st.success(f"{name}: loaded")
    else:
        st.warning(f"{name}: missing")

render_footer()
