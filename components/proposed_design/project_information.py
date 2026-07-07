import streamlit as st


def render_project_information():
    """
    Render the project information section.
    """

    st.subheader("Project Information")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input(
            "Project Name",
            key="project_name",
            placeholder="Enter project name",
        )

    with col2:
        st.number_input(
            "Building Area (m²)",
            min_value=0.0,
            step=100.0,
            key="building_area",
        )

    st.text_area(
        "Assessment Notes",
        key="assessment_notes",
        height=120,
        placeholder="Optional notes...",
    )

    st.divider()
    