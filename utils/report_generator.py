from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ARUP_RED = colors.HexColor("#D71920")
SOFT_GREY = colors.HexColor("#F3F4F6")
MID_GREY = colors.HexColor("#666666")
DARK_GREY = colors.HexColor("#202020")
WHITE = colors.white


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=DARK_GREY,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=MID_GREY,
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=DARK_GREY,
            spaceBefore=8,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=DARK_GREY,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=MID_GREY,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=MID_GREY,
            alignment=TA_CENTER,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=DARK_GREY,
            alignment=TA_CENTER,
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=6.5,
            leading=8,
            textColor=WHITE,
            alignment=TA_CENTER,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=6.3,
            leading=7.5,
            textColor=DARK_GREY,
        ),
    }


def _safe_text(value: Any) -> str:
    if value is None:
        return "None"
    try:
        if pd.isna(value):
            return "None"
    except (TypeError, ValueError):
        pass
    return str(value)


def _format_number(value: Any, decimals: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _safe_text(value)
    return f"{number:,.{decimals}f}"


def _footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = doc.pagesize
    canvas.setStrokeColor(colors.HexColor("#D9D9D9"))
    canvas.line(doc.leftMargin, 14 * mm, width - doc.rightMargin, 14 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MID_GREY)
    canvas.drawString(
        doc.leftMargin,
        9 * mm,
        "Generated using the Fire Safety Embodied Carbon App",
    )
    canvas.drawRightString(
        width - doc.rightMargin,
        9 * mm,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def _header(story: list, title: str) -> None:
    styles = _styles()
    story.append(Paragraph(title, styles["title"]))
    story.append(
        Paragraph(
            "Fire Safety Embodied Carbon App<br/>"
            "Developed by Jacaranda Flame Consulting in collaboration with ARUP",
            styles["subtitle"],
        )
    )


def _project_info_table(project_name: str, generated_at: datetime) -> Table:
    styles = _styles()
    data = [
        [Paragraph("<b>Project Name</b>", styles["body"]), Paragraph(_safe_text(project_name), styles["body"])],
        [Paragraph("<b>Generated</b>", styles["body"]), Paragraph(generated_at.strftime("%d %B %Y, %I:%M %p"), styles["body"])],
    ]
    table = Table(data, colWidths=[42 * mm, 128 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), SOFT_GREY),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E5E5")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _metric_cards(summary: dict[str, Any]) -> Table:
    styles = _styles()
    labels = ["A1-A3", "A4", "A5", "Total"]
    cards = []
    for label in labels:
        value = _format_number(summary.get(label, 0), 2)
        cards.append(
            Table(
                [
                    [Paragraph(label, styles["metric_label"])],
                    [Paragraph(f"{value} kgCO2e", styles["metric_value"])],
                ],
                colWidths=[42 * mm],
                rowHeights=[10 * mm, 13 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), SOFT_GREY if label != "Total" else colors.HexColor("#FBEAEA")),
                        ("BOX", (0, 0), (-1, -1), 0.7, ARUP_RED if label == "Total" else colors.HexColor("#D9D9D9")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                ),
            )
        )
    return Table([[cards[0], cards[1]], [cards[2], cards[3]]], colWidths=[87 * mm, 87 * mm], rowHeights=[27 * mm, 27 * mm])


def _normalise_fire_results(results_df: pd.DataFrame) -> pd.DataFrame:
    df = results_df.copy()
    desired = [
        "Apparatus",
        "Product Type",
        "Quantity",
        "Spacing Area",
        "A1-A3",
        "A4",
        "A5",
        "Total",
    ]
    if "Spacing Area" not in df.columns:
        insert_at = min(3, len(df.columns))
        df.insert(insert_at, "Spacing Area", None)
    for col in desired:
        if col not in df.columns:
            df[col] = None
    return df[desired]


def _dataframe_table(
    df: pd.DataFrame,
    col_widths: list[float],
    numeric_columns: set[str] | None = None,
) -> Table:
    styles = _styles()
    numeric_columns = numeric_columns or set()

    header = [Paragraph(str(col), styles["table_header"]) for col in df.columns]
    rows = [header]
    for _, row in df.iterrows():
        rendered = []
        for col in df.columns:
            value = row[col]
            text = _format_number(value, 4) if col in numeric_columns and _safe_text(value) != "None" else _safe_text(value)
            rendered.append(Paragraph(text, styles["table_cell"]))
        rows.append(rendered)

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), ARUP_RED),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CFCFCF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for row_index in range(1, len(rows)):
        if row_index % 2 == 0:
            style_commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#FAFAFA")))
    table.setStyle(TableStyle(style_commands))
    return table


def _bar_chart(
    categories: list[str],
    series: list[list[float]],
    series_names: list[str],
    title: str,
    width: float = 170 * mm,
    height: float = 78 * mm,
) -> Drawing:
    drawing = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 18 * mm
    chart.y = 15 * mm
    chart.width = width - 35 * mm
    chart.height = height - 28 * mm
    chart.data = series
    chart.categoryAxis.categoryNames = [str(x) for x in categories]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.labels.angle = 20 if len(categories) > 4 else 0
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.forceZero = 1
    chart.barWidth = 7
    chart.groupSpacing = 10

    palette = [ARUP_RED, colors.HexColor("#666666"), colors.HexColor("#9E9E9E")]
    for index in range(len(series)):
        chart.bars[index].fillColor = palette[index % len(palette)]

    drawing.add(chart)

    if len(series_names) > 1:
        legend = Legend()
        legend.x = width - 55 * mm
        legend.y = height - 10 * mm
        legend.fontName = "Helvetica"
        legend.fontSize = 7
        legend.colorNamePairs = [
            (palette[i % len(palette)], series_names[i])
            for i in range(len(series_names))
        ]
        drawing.add(legend)

    styles = _styles()
    drawing.add(
        Drawing(0, 0)
    )
    return drawing



def _plotly_image(figure: Any, width: float = 170 * mm, height: float = 82 * mm):
    if figure is None:
        return None
    try:
        png_bytes = figure.to_image(
            format="png",
            width=1200,
            height=620,
            scale=1,
        )
    except Exception:
        return None
    image = Image(BytesIO(png_bytes))
    image.drawWidth = width
    image.drawHeight = height
    return image


def generate_fire_design_report(
    project_name: str,
    summary: dict[str, Any],
    results_df: pd.DataFrame,
    apparatus_figure: Any = None,
    lifecycle_figure: Any = None,
    generated_at: datetime | None = None,
) -> bytes:
    generated_at = generated_at or datetime.now()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title="Fire Safety Embodied Carbon Report",
        author="Jacaranda Flame Consulting",
    )
    styles = _styles()
    story: list = []

    _header(story, "Fire Safety Embodied Carbon Report")
    story.append(Paragraph("Project Information", styles["section"]))
    story.append(_project_info_table(project_name, generated_at))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Embodied Carbon Summary", styles["section"]))
    story.append(_metric_cards(summary))
    story.append(Spacer(1, 6 * mm))

    normalised = _normalise_fire_results(results_df)
    story.append(Paragraph("Calculation Results", styles["section"]))
    story.append(
        _dataframe_table(
            normalised,
            col_widths=[44 * mm, 43 * mm, 22 * mm, 26 * mm, 25 * mm, 20 * mm, 20 * mm, 25 * mm],
            numeric_columns={"Quantity", "A1-A3", "A4", "A5", "Total"},
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("Carbon Analysis Dashboard", styles["section"]))

    apparatus_totals = (
        normalised.groupby("Apparatus", dropna=False)["Total"].sum().reset_index()
        if not normalised.empty
        else pd.DataFrame(columns=["Apparatus", "Total"])
    )
    story.append(Paragraph("Embodied Carbon by Apparatus", styles["body"]))
    apparatus_image = _plotly_image(apparatus_figure)
    if apparatus_image is not None:
        story.append(apparatus_image)
    elif not apparatus_totals.empty:
        story.append(
            _bar_chart(
                apparatus_totals["Apparatus"].astype(str).tolist(),
                [apparatus_totals["Total"].astype(float).tolist()],
                ["Total"],
                "Embodied Carbon by Apparatus",
            )
        )
    story.append(Spacer(1, 5 * mm))

    lifecycle_categories = ["A1-A3", "A4", "A5"]
    lifecycle_values = [float(summary.get(key, 0) or 0) for key in lifecycle_categories]
    story.append(Paragraph("Embodied Carbon by Lifecycle Stage", styles["body"]))
    lifecycle_image = _plotly_image(lifecycle_figure)
    if lifecycle_image is not None:
        story.append(lifecycle_image)
    else:
        story.append(
            _bar_chart(
                lifecycle_categories,
                [lifecycle_values],
                ["kgCO2e"],
                "Embodied Carbon by Lifecycle Stage",
            )
        )

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def generate_comparison_report(
    project_name: str,
    label_a: str,
    version_a: dict[str, Any],
    label_b: str,
    version_b: dict[str, Any],
    category_totals_df: pd.DataFrame,
    overall_figure: Any = None,
    category_figure: Any = None,
    generated_at: datetime | None = None,
) -> bytes:
    generated_at = generated_at or datetime.now()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title="Fire Safety Embodied Carbon Comparison Report",
        author="Jacaranda Flame Consulting",
    )
    styles = _styles()
    story: list = []

    _header(story, "Fire Safety Embodied Carbon Comparison Report")

    story.append(Paragraph("Project", styles["section"]))
    story.append(_project_info_table(project_name, generated_at))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Version Summary", styles["section"]))
    version_summary_data = [
        [
            Paragraph("<b>Version</b>", styles["body"]),
            Paragraph("<b>Timestamp</b>", styles["body"]),
            Paragraph("<b>Total Embodied Carbon</b>", styles["body"]),
        ],
        [
            Paragraph(label_a, styles["body"]),
            Paragraph(_safe_text(version_a.get("timestamp")), styles["body"]),
            Paragraph(f"{float(version_a.get('summary', {}).get('Total', 0) or 0):,.2f} kgCO2e", styles["body"]),
        ],
        [
            Paragraph(label_b, styles["body"]),
            Paragraph(_safe_text(version_b.get("timestamp")), styles["body"]),
            Paragraph(f"{float(version_b.get('summary', {}).get('Total', 0) or 0):,.2f} kgCO2e", styles["body"]),
        ],
    ]
    version_table = Table(version_summary_data, colWidths=[90 * mm, 70 * mm, 70 * mm])
    version_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ARUP_RED),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CFCFCF")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#FAFAFA")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(version_table)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Overall Comparison", styles["section"]))
    overall_image = _plotly_image(overall_figure)
    if overall_image is not None:
        story.append(overall_image)
    else:
        story.append(
            _bar_chart(
                [label_a, label_b],
                [[
                    float(version_a.get("summary", {}).get("Total", 0) or 0),
                    float(version_b.get("summary", {}).get("Total", 0) or 0),
                ]],
                ["Total"],
                "Overall Comparison",
            )
        )
    story.append(PageBreak())

    story.append(Paragraph("Comparison by Category", styles["section"]))
    sorted_df = category_totals_df.sort_values("Category").reset_index(drop=True)
    if not sorted_df.empty:
        category_image = _plotly_image(category_figure)
        if category_image is not None:
            story.append(category_image)
        else:
            story.append(
                _bar_chart(
                    sorted_df["Category"].astype(str).tolist(),
                    [
                        sorted_df[label_a].astype(float).tolist(),
                        sorted_df[label_b].astype(float).tolist(),
                    ],
                    [label_a, label_b],
                    "Comparison by Category",
                )
            )
        story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Category Breakdown Table", styles["section"]))
    story.append(
        _dataframe_table(
            sorted_df,
            col_widths=[90 * mm, 70 * mm, 70 * mm],
            numeric_columns={label_a, label_b},
        )
    )

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()