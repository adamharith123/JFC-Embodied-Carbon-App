import streamlit as st

from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import (
    apply_global_styles,
    render_header,
    render_footer,
)

from components.proposed_design.project_information import (
    render_project_information,
)

from components.proposed_design.building_characteristics import (
    render_building_characteristics,
)

from components.proposed_design.design_parameters import (
    render_design_parameters,
)

from components.proposed_design.generated_systems import (
    render_generated_systems,
)


st.set_page_config(
    page_title="Proposed Design",
    page_icon="🏢",
    layout="wide",
)

apply_global_styles()

render_header(
    "Proposed Design",
    APP_SUBTITLE,
    APP_STATUS,
)

render_project_information()

render_building_characteristics()

render_design_parameters()



st.divider()

render_generated_systems()

render_footer()
