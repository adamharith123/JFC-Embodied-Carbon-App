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