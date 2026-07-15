import base64
from pathlib import Path
import streamlit as st
from utils.constants import (
    ARUP_RED,
    ARUP_DARK_RED,
    SOFT_RED,
    CHARCOAL,
    LIGHT_GREY,
    MID_GREY,
    ARUP_LOGO,
    JFC_LOGO,
)


def image_to_base64(path: Path):
    if not path.exists():
        return None

    encoded = base64.b64encode(path.read_bytes()).decode()
    suffix = path.suffix.lower().replace(".", "")

    if suffix == "jpg":
        suffix = "jpeg"

    return f"data:image/{suffix};base64,{encoded}"


def apply_global_styles():
    st.markdown(
        f"""
<style>

/* ==========================================================
   GLOBAL COLOURS
========================================================== */

:root {{
    --arup-red: {ARUP_RED};
    --arup-dark-red: {ARUP_DARK_RED};
    --soft-red: {SOFT_RED};
    --charcoal: {CHARCOAL};
    --light-grey: {LIGHT_GREY};
    --mid-grey: {MID_GREY};
}}


/* ==========================================================
   STREAMLIT
========================================================== */


.block-container {{
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}}

[data-testid="stSidebar"] {{
    background-color: var(--soft-red);
}}


/* ==========================================================
   HEADINGS
========================================================== */

h1,
h2,
h3 {{
    color: var(--arup-red);
}}


/* ==========================================================
   HERO HEADER
========================================================== */

.hero {{
    background: linear-gradient(
        90deg,
        var(--charcoal),
        var(--arup-red)
    );

    padding: 1.3rem 1.6rem;

    border-radius: 18px;

    color: white;

    margin-bottom: 1.5rem;

    display: flex;

    justify-content: space-between;

    align-items: center;

    gap: 1rem;
}}

.hero-title {{
    margin: 0;
    font-size: 2rem;
    font-weight: 700;
    color: white;
}}

.hero-subtitle {{
    margin-top: 0.4rem;
    color: white;
    font-size: 1rem;
}}

.status-pill {{
    display: inline-block;

    margin-top: 0.7rem;

    padding: 0.3rem 0.8rem;

    border-radius: 999px;

    background: rgba(255,255,255,0.18);

    border: 1px solid rgba(255,255,255,0.35);

    color: white;

    font-size: 0.8rem;

    font-weight: 600;
}}


/* ==========================================================
   LOGOS
========================================================== */

.logo-row {{
    display: flex;
    gap: 0.8rem;
}}

.logo-card {{
    background: white;

    border-radius: 12px;

    min-width: 110px;

    height: 60px;

    display: flex;

    justify-content: center;

    align-items: center;

    padding: 0.4rem;
}}

.logo-card img {{
    object-fit: contain;
}}

.arup-logo {{
    max-height: 42px;
    max-width: 135px;
}}

.jfc-logo {{
    max-height: 60px;
    max-width: 140px;
}}


/* ==========================================================
   CARDS
========================================================== */

.nav-card {{

    background: white;

    border-radius: 16px;

    border-left: 6px solid var(--arup-red);

    padding: 1.1rem;

    box-shadow: 0 3px 10px rgba(0,0,0,0.08);

    min-height: 150px;
}}

.small-note {{

    background: var(--soft-red);

    border-left: 5px solid var(--arup-red);

    border-radius: 12px;

    padding: 1rem;
}}


/* ==========================================================
   BUTTONS
========================================================== */

.stButton > button {{

    background-color: var(--arup-red);

    color: white;

    border-radius: 10px;

    border: none;

    font-weight: 600;
}}

.stButton > button:hover {{

    background-color: var(--arup-dark-red);

    color: white;
}}


/* ==========================================================
   METRICS
========================================================== */

[data-testid="stMetric"] {{

    background: white;

    border-left: 6px solid var(--arup-red);

    border-radius: 14px;

    padding: 1rem;

    box-shadow: 0 3px 12px rgba(0,0,0,0.08);
}}


/* ==========================================================
   FOOTER
========================================================== */

.footer {{

    margin-top: 2rem;

    padding-top: 1rem;

    border-top: 1px solid #EAEAEA;

    color: var(--mid-grey);

    font-size: 0.85rem;
}}

</style>
""",
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str, status: str):
    jfc = image_to_base64(JFC_LOGO)
    arup = image_to_base64(ARUP_LOGO)

    jfc_html = f'<img class="jfc-logo" src="{jfc}" alt="JFC logo">' if jfc else "JFC"
    arup_html = f'<img class="arup-logo" src="{arup}" alt="ARUP logo">' if arup else "ARUP"

    st.markdown(
        f"""
        <div class="hero">
            <div>
                <p class="hero-title">{title}</p>
                <p class="hero-subtitle">{subtitle}</p>
                <span class="status-pill">{status}</span>
            </div>
            <div class="logo-row">
                <div class="logo-card">{jfc_html}</div>
                <div class="logo-card">{arup_html}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer():
    st.markdown(
        """
        <div class="footer">
            FireCarbonApp v6.0 · Jacaranda Flame Consulting · ARUP collaboration prototype
        </div>
        """,
        unsafe_allow_html=True,
    )