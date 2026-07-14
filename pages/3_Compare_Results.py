import streamlit as st
import pandas as pd

from utils.constants import APP_SUBTITLE, APP_STATUS
from utils.styles import apply_global_styles, render_header, render_footer
from utils.project_store import get_project_names, get_project_versions
from utils.charts import (
    create_category_comparison_chart,
    create_overall_comparison_chart,
)

# ==========================================================
# Page Configuration
# ==========================================================

st.set_page_config(
    page_title="Compare Results",
    page_icon="⚖️",
    layout="wide",
)

apply_global_styles()

render_header("Compare Results", APP_SUBTITLE, APP_STATUS)

st.markdown(
    "Compare the embodied carbon results of any two saved versions of the "
    "same project - for example a Deemed-to-Satisfy design against a "
    "Performance-Based design, or two design iterations of either kind. "
    "Versions are not required to be purely DtS or purely PBD - a version "
    "with a mixture of both is compared exactly the same way."
)

st.divider()

# ==========================================================
# Version Selection
# ==========================================================


def version_label(v):
    note = (v["version_notes"] or "").strip().splitlines()
    preview = note[0][:60] if note else "No notes"
    return f"Version {v['version']} — {preview}"


projects = get_project_names()

if not projects:
    st.info("No projects found yet. Create and save an assessment on the Fire Design page first.")
    st.stop()

project_name = st.selectbox("Project", projects, key="compare_project")

versions = get_project_versions(project_name)
# Only versions with actual results can be meaningfully compared.
versions = [v for v in versions if v["results"]]

if len(versions) < 2:
    st.info(
        "This project needs at least two saved versions with calculated "
        "results before they can be compared. Save another version on the "
        "Fire Design page first."
    )
    st.stop()

version_options = {version_label(v): v for v in versions}

col1, col2 = st.columns(2)

with col1:
    label_a = st.selectbox("Version A", list(version_options.keys()), index=0, key="compare_version_a")

with col2:
    default_b_index = 1 if len(version_options) > 1 else 0
    label_b = st.selectbox(
        "Version B", list(version_options.keys()), index=default_b_index, key="compare_version_b"
    )

if label_a == label_b:
    st.warning("Select two different versions to compare.")
    st.stop()

version_a = version_options[label_a]
version_b = version_options[label_b]

st.divider()

# ==========================================================
# Build Category-Level Totals
# ==========================================================


def build_subcategory_to_category_map(design_rows):
    return {row.get("Subcategory"): row.get("Category") for row in design_rows}


def build_category_totals(version_data):
    """
    Sums each version's saved results by fire safety category, using
    the version's own saved design rows to map each result (recorded
    per subcategory/apparatus) back to its parent category. This
    means comparison works for any already-saved version, without
    depending on the Fire Design page's current category taxonomy.
    """

    sub_to_cat = build_subcategory_to_category_map(version_data["design"])

    results_df = pd.DataFrame(version_data["results"])

    if results_df.empty:
        return pd.DataFrame(columns=["Category", "Total"])

    results_df["Category"] = results_df["Apparatus"].map(sub_to_cat).fillna("Uncategorised")

    return results_df.groupby("Category", as_index=False)["Total"].sum()


totals_a = build_category_totals(version_a).rename(columns={"Total": label_a})
totals_b = build_category_totals(version_b).rename(columns={"Total": label_b})

category_totals_df = pd.merge(totals_a, totals_b, on="Category", how="outer").fillna(0)

# ==========================================================
# Version Metadata
# ==========================================================

meta_col1, meta_col2 = st.columns(2)

with meta_col1:
    st.markdown(f"**{label_a}**")
    st.caption(version_a["timestamp"])
    st.metric("Total Embodied Carbon", f"{version_a['summary'].get('Total', 0):,.2f} kgCO₂e")

with meta_col2:
    st.markdown(f"**{label_b}**")
    st.caption(version_b["timestamp"])
    st.metric("Total Embodied Carbon", f"{version_b['summary'].get('Total', 0):,.2f} kgCO₂e")

st.divider()

# ==========================================================
# Charts
# ==========================================================

st.subheader("Overall Comparison")

fig_overall = create_overall_comparison_chart(
    version_a["summary"].get("Total", 0),
    version_b["summary"].get("Total", 0),
    label_a,
    label_b,
)

if fig_overall is not None:
    st.plotly_chart(fig_overall, use_container_width=True)

st.subheader("Comparison by Category")

fig_category = create_category_comparison_chart(category_totals_df, label_a, label_b)

if fig_category is not None:
    st.plotly_chart(fig_category, use_container_width=True)
else:
    st.info("Neither version has any calculated results to compare yet.")

st.divider()

st.subheader("Underlying Numbers")

st.dataframe(
    category_totals_df.sort_values("Category"),
    use_container_width=True,
    hide_index=True,
)

render_footer()
