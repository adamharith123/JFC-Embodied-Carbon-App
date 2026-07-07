import streamlit as st


def render_design_parameters():

    st.subheader("Fire Safety Systems")

    with st.expander(
        "Sprinkler System",
        expanded=True,
    ):

        st.checkbox(
            "Include Sprinkler System",
            value=True,
            key="include_sprinklers",
        )

        st.info(
            "Engineering inputs for sprinkler quantity "
            "estimation will be loaded from the "
            "User Input workbook."
        )

    with st.expander("Fire Hydrant System"):
        st.write("Coming soon.")

    with st.expander("Fire Hose Reels"):
        st.write("Coming soon.")

    with st.expander("Portable Fire Extinguishers"):
        st.write("Coming soon.")

    with st.expander("Detection & Alarm"):
        st.write("Coming soon.")

    with st.expander("Emergency Lighting & Exit Signs"):
        st.write("Coming soon.")

    st.divider()