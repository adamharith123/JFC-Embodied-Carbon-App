import streamlit as st
from utils.quantification_engine import quantify_sprinklers

from utils.database_loader import (
    load_standards_database,
)

from utils.design_engine import (
    get_required_systems,
)


def render_generated_systems():

    st.subheader("Generated Fire Safety Systems")

    if st.button(
        "Generate Proposed Design",
        type="primary",
        use_container_width=True,
    ):

        db = load_standards_database()
        
        
        building_class = st.session_state.get(
            "building_class"
        )
        

        systems = get_required_systems(
            building_class,
            db["building_class"],
        )

        inputs = {
            "floor_area": st.session_state["floor_area"],
            "hazard": st.session_state["sprinkler_hazard"],
        }

        sprinkler_results = quantify_sprinklers(inputs)

        st.session_state[
            "generated_systems"
        ] = systems

        st.session_state["sprinkler_results"] = sprinkler_results

    if "generated_systems" in st.session_state:

        df = st.session_state[
            "generated_systems"
        ]

        if df.empty:

            st.warning(
                "No applicable systems found."
            )

        else:

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )
            results = st.session_state["sprinkler_results"]

            st.divider()

            st.subheader("Sprinkler Quantification")

            col1, col2 = st.columns(2)

            col1.metric(
                "Spacing Area",
                f'{results["spacing_area"]} m²/head'
            )

            col2.metric(
                "Sprinkler Heads",
                results["sprinkler_heads"]
            )

    else:

        st.info(
            "Click Generate Proposed Design."
        )
        