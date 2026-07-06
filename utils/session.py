import streamlit as st
from utils.database_loader import load_all_databases


def initialise_session_state():
    defaults = {
        "project_name": "JFC Fire Safety Assessment",
        "assessment_type": "Proposed new design",
        "results_df": None,
        "quantity_df": None,
        "assumptions_df": None,
        "databases_loaded": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def load_databases_into_session():
    st.session_state.databases = load_all_databases()
    st.session_state.databases_loaded = True