import streamlit as st

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
        st.write("Building Class:", building_class)

        systems = get_required_systems(
            building_class,
            db["building_class"],
        )

        st.session_state[
            "generated_systems"
        ] = systems

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

    else:

        st.info(
            "Click Generate Proposed Design."
        )
        