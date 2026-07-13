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
