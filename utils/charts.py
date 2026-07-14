"""
FireCarbonApp v6
Chart Utilities

Reusable Plotly charts for the application.

No Streamlit code should exist in this module.
"""

import pandas as pd
import plotly.express as px


# ==========================================================
# Embodied Carbon by Apparatus
# ==========================================================

def create_apparatus_pie_chart(results_df):
    """
    Create a pie chart showing total embodied carbon by apparatus.

    Duplicate apparatus are automatically grouped together.
    """

    if results_df.empty:
        return None

    chart_df = (
        results_df
        .groupby("Apparatus", as_index=False)["Total"]
        .sum()
        .sort_values("Total", ascending=False)
    )

    fig = px.pie(
        chart_df,
        names="Apparatus",
        values="Total",
        hole=0.45,
        title="Embodied Carbon by Apparatus",
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
    )

    fig.update_layout(
        legend_title="Fire Safety System",
        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20,
        ),
    )

    return fig


# ==========================================================
# Lifecycle Breakdown
# ==========================================================

def create_lifecycle_bar_chart(summary):
    """
    Create a bar chart showing embodied carbon by lifecycle stage.
    """

    chart_df = pd.DataFrame({

        "Lifecycle Stage": [
            "A1-A3",
            "A4",
            "A5",
        ],

        "Embodied Carbon (kgCO₂e)": [

            summary["A1-A3"],

            summary["A4"],

            summary["A5"],

        ],

    })

    fig = px.bar(

        chart_df,

        x="Lifecycle Stage",

        y="Embodied Carbon (kgCO₂e)",

        text="Embodied Carbon (kgCO₂e)",

        title="Embodied Carbon by Lifecycle Stage",

    )

    fig.update_traces(

        texttemplate="%{text:.2f}",

        textposition="outside",

    )

    fig.update_layout(

        showlegend=False,

        margin=dict(

            l=20,

            r=20,

            t=60,

            b=20,

        ),

    )

    return fig


# ==========================================================
# Version Comparison Charts
# ==========================================================

def create_category_comparison_chart(category_totals_df, label_a, label_b):
    """
    Grouped bar chart comparing two versions' total embodied carbon
    (A1-A3 + A4 + A5) per fire safety category.

    category_totals_df must have columns: "Category", label_a, label_b.
    """

    if category_totals_df.empty:
        return None

    chart_df = category_totals_df.melt(
        id_vars="Category",
        value_vars=[label_a, label_b],
        var_name="Version",
        value_name="Embodied Carbon (kgCO₂e)",
    )

    fig = px.bar(
        chart_df,
        x="Category",
        y="Embodied Carbon (kgCO₂e)",
        color="Version",
        barmode="group",
        title="Embodied Carbon by Category",
    )

    fig.update_layout(
        xaxis_tickangle=-30,
        legend_title=None,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig


def create_overall_comparison_chart(total_a, total_b, label_a, label_b):
    """
    Simple two-bar chart comparing whole-building total embodied
    carbon between two versions.
    """

    chart_df = pd.DataFrame({
        "Version": [label_a, label_b],
        "Embodied Carbon (kgCO₂e)": [total_a, total_b],
    })

    fig = px.bar(
        chart_df,
        x="Version",
        y="Embodied Carbon (kgCO₂e)",
        color="Version",
        text="Embodied Carbon (kgCO₂e)",
        title="Total Embodied Carbon",
    )

    fig.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside",
    )

    fig.update_layout(
        showlegend=False,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig
