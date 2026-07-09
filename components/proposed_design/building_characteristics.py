import streamlit as st


def render_building_characteristics():
    """
    Render building inputs for a proposed design assessment.
    """

    st.subheader("Building Inputs")

    col1, col2 = st.columns(2)

    with col1:

        st.selectbox(
            "NCC Building Class",
            options=[
                "Class 2",
                "Class 3",
                "Class 5",
                "Class 6",
                "Class 7a",
                "Class 7b",
                "Class 8",
                "Class 9a",
                "Class 9b",
                "Class 9c",
            ],
            key="building_class",
        )

        st.number_input(
            "Total Building Floor Area (m²)",
            min_value=0.0,
            step=100.0,
            key="floor_area",
        )

        st.number_input(
            "Number of Storeys",
            min_value=1,
            step=1,
            key="storeys",
        )

        st.number_input(
            "Effective Height (m)",
            min_value=0.0,
            step=1.0,
            key="effective_height",
        )

    with col2:

        st.number_input(
            "Floor-to-floor Height (m)",
            min_value=0.0,
            step=0.1,
            key="floor_to_floor_height",
        )

        st.number_input(
            "Number of Exits",
            min_value=1,
            step=1,
            key="number_of_exits",
        )

        st.number_input(
            "Number of Stairs",
            min_value=0,
            step=1,
            key="number_of_stairs",
        )

        st.selectbox(
            "Sprinkler Hazard Classification",
            options=[
                "Light Hazard",
                "Ordinary Hazard",
                "High Hazard",
            ],
            key="sprinkler_hazard",
        )

    st.divider()
