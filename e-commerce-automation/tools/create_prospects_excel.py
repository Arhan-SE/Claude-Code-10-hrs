import json
import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter

INPUT_FILE = "ecommerce_prospects.json"
OUTPUT_FILE = "ecommerce_prospects.xlsx"

COLUMNS = [
    ("Brand Name",          "brand_name"),
    ("Website",             "website"),
    ("Industry",            "industry"),
    ("Revenue",             "revenue"),
    ("Company Size",        "company_size"),
    ("Headquarters",        "headquarters"),
    ("Founded",             "founded"),
    ("Key Products",        "key_products"),
    ("Social Media",        "social_media"),
    ("Support Channels",    "support_channels"),
    ("Pain Points",         "pain_points"),
    ("Decision Maker",      "decision_maker"),
    ("Tech Stack",          "tech_stack"),
    ("Personalization",     "personalization"),
]

HEADER_BG   = "1F3864"   # dark navy
HEADER_FG   = "FFFFFF"
ALT_ROW_BG  = "EEF2F7"   # light blue-grey
ACCENT_BG   = "FFF2CC"   # soft yellow for Personalization column

thin_side = Side(style="thin", color="CCCCCC")
thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)


def col_widths():
    return {
        "Brand Name":       22,
        "Website":          32,
        "Industry":         22,
        "Revenue":          22,
        "Company Size":     18,
        "Headquarters":     20,
        "Founded":          10,
        "Key Products":     40,
        "Social Media":     38,
        "Support Channels": 30,
        "Pain Points":      50,
        "Decision Maker":   38,
        "Tech Stack":       28,
        "Personalization":  60,
    }


def flatten_social(val):
    if isinstance(val, dict):
        return " | ".join(f"{k}: {v}" for k, v in val.items())
    return str(val) if val else ""


def get_value(record, key):
    val = record.get(key, "")
    if key == "social_media":
        return flatten_social(val)
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val) if val is not None else ""


def build_excel(data, output_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ecommerce Prospects"

    widths = col_widths()
    header_font  = Font(name="Calibri", bold=True, color=HEADER_FG, size=11)
    header_fill  = PatternFill("solid", fgColor=HEADER_BG)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    alt_fill     = PatternFill("solid", fgColor=ALT_ROW_BG)
    accent_fill  = PatternFill("solid", fgColor=ACCENT_BG)
    normal_align = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # --- Header row ---
    for col_idx, (col_label, _) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_label)
        cell.font   = header_font
        cell.fill   = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = widths[col_label]

    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    # --- Data rows ---
    personalization_col = next(
        i + 1 for i, (label, _) in enumerate(COLUMNS) if label == "Personalization"
    )

    for row_idx, record in enumerate(data, start=2):
        is_alt = (row_idx % 2 == 0)
        for col_idx, (col_label, field_key) in enumerate(COLUMNS, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=get_value(record, field_key))
            cell.alignment = normal_align
            cell.border    = thin_border
            cell.font      = Font(name="Calibri", size=10)

            if col_idx == personalization_col:
                cell.fill = accent_fill
                cell.font = Font(name="Calibri", size=10, italic=True)
            elif is_alt:
                cell.fill = alt_fill

        ws.row_dimensions[row_idx].height = 80

    # --- Auto-filter on header ---
    ws.auto_filter.ref = ws.dimensions

    wb.save(output_path)
    print(f"Saved: {output_path}  ({len(data)} records)")


if __name__ == "__main__":
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    build_excel(data, OUTPUT_FILE)
