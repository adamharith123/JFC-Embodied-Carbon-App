import streamlit as st

from utils.constants import APP_NAME,APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer


st.set_page_config(
    page_title="Help",
    page_icon="❓",
    layout="wide",
)

apply_global_styles()

render_header(
    APP_NAME,
    APP_SUBTITLE,
    APP_STATUS,
)


# ==========================================================
# CALCULATION METHODOLOGY
# ==========================================================

st.markdown("## Calculation Methodology")

st.markdown(
    """
The Fire Safety Embodied Carbon App estimates the upfront embodied carbon (A1–A5)
associated with fire safety systems in buildings.

The application integrates engineering databases, Australian Standards and
embodied carbon data to support sustainable fire safety design decision-making.
Carbon results are presented through intuitive tables, charts and engineering
summaries.
"""
)

st.divider()


# ==========================================================
# OVERALL WORKFLOW
# ==========================================================

st.markdown("## Overall Workflow")


def render_workflow():

    st.markdown(
        """
        <style>

        .workflow-box {
            background-color: white;
            border: 1px solid #d0d7de;
            border-radius: 10px;
            padding: 15px;
            margin: 5px auto;
            text-align: center;
            width: 70%;
            font-size: 17px;
            font-weight: 600;
        }

        .workflow-arrow {
            text-align: center;
            font-size: 28px;
            color: #777;
            margin: 3px;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    workflow = [

        (
            "01 | Building Design Inputs",
            """
Defines the building characteristics required for assessment,
including building classification, floor area and relevant design parameters.
""",
        ),

        (
            "02 | Fire Safety System Selection",
            """
Users select the proposed fire safety measures incorporated
within the building design.
""",
        ),

        (
            "03 | Standards Compliance Verification",
            """
The selected fire safety systems are assessed against
the National Construction Code (NCC) and Australian Standards.
""",
        ),

        (
            "04 | Embodied Carbon Database Matching",
            """
Fire safety components are matched with the embodied carbon
database to obtain material quantities and emission factors.
""",
        ),

        (
            "05 | Lifecycle Carbon Calculation",
            """
Embodied carbon is calculated across lifecycle stages
A1–A3, A4 and A5.
""",
        ),

        (
            "06 | Carbon Breakdown & Visualisation",
            """
Results are presented through engineering tables,
system breakdowns and lifecycle charts.
""",
        ),

        (
            "07 | Design Comparison / Decision Support",
            """
Outputs support engineers and designers in comparing
design options and reducing embodied carbon.
""",
        ),
    ]

    for i, (title, description) in enumerate(workflow):

        st.markdown(
            f"""
            <div class="workflow-box">
                {title}
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("ⓘ Learn More"):
            st.write(description)

        if i < len(workflow) - 1:
            st.markdown(
                '<div class="workflow-arrow">↓</div>',
                unsafe_allow_html=True,
            )


render_workflow()

st.divider()


# ==========================================================
# METHODOLOGY ASSUMPTIONS
# ==========================================================

st.markdown("## Methodology Assumptions")

st.markdown(
    """
- Scope limited to upfront embodied carbon (A1–A5).
- Lifecycle stages include A1–A3 (Product), A4 (Transport) and A5 (Construction & Installation).
- Engineering databases are editable to support future updates.
- Embodied carbon calculations are performed automatically using Python.
"""
)

st.divider()


# ==========================================================
# REFERENCES
# ==========================================================

st.markdown("## References")

st.markdown(
    """
- National Construction Code (NCC)

- Australian Standards

- National Material Emission Factors Database

- NSW Embodied Carbon Databook

- FireCarbonApp Engineering Databases
"""
)

st.divider()


# ==========================================================
# VERSION HISTORY
# ==========================================================

st.markdown("## Version History")

st.markdown(
    """
**FireCarbonApp v6.0**

Prototype

**Release:** Winter 2026

**Developed by:** Jacaranda Flame Consulting

**In collaboration with:** ARUP
"""
)

render_footer()
