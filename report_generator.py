"""
Report generation helpers - builds PDF and Excel reports from data pulled
off the backend API, then can notify the backend that a requested Report
document is ready (see Report model / /api/reports/:id/complete).

This is intentionally a standalone module (not wired into the daily
scheduler loop) so it can be invoked on demand, e.g. from a small Flask/
FastAPI endpoint the Node backend calls, or as a CLI:

    python report_generator.py --type oil-change --output out.pdf
"""

import os
import argparse
from datetime import datetime

import requests
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl import Workbook

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000/api")
SCHEDULER_API_KEY = os.getenv("SCHEDULER_API_KEY", "")
HEADERS = {"x-scheduler-key": SCHEDULER_API_KEY}


def fetch_oil_change_data():
    resp = requests.get(f"{API_BASE_URL}/oil-changes/due/today", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def build_pdf_report(rows: list[dict], output_path: str, title: str = "Oil Change Report"):
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    table_data = [["Machine", "Oil Change Date", "Next Due", "Reminder Sent"]]
    for r in rows:
        machine = (r.get("machine") or {}).get("machineName", "-")
        table_data.append(
            [
                machine,
                str(r.get("oilChangeDate", ""))[:10],
                str(r.get("nextOilChangeDate", ""))[:10],
                "Yes" if r.get("reminderSent") else "No",
            ]
        )

    table = Table(table_data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    return output_path


def build_excel_report(rows: list[dict], output_path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Oil Change Report"
    ws.append(["Machine", "Oil Change Date", "Next Due", "Reminder Sent"])

    for r in rows:
        machine = (r.get("machine") or {}).get("machineName", "-")
        ws.append(
            [
                machine,
                str(r.get("oilChangeDate", ""))[:10],
                str(r.get("nextOilChangeDate", ""))[:10],
                "Yes" if r.get("reminderSent") else "No",
            ]
        )

    wb.save(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Generate maintenance reports")
    parser.add_argument("--type", choices=["oil-change"], default="oil-change")
    parser.add_argument("--format", choices=["pdf", "excel"], default="pdf")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    rows = fetch_oil_change_data()
    ext = "pdf" if args.format == "pdf" else "xlsx"
    output_path = args.output or f"oil_change_report_{datetime.now().strftime('%Y%m%d')}.{ext}"

    if args.format == "pdf":
        build_pdf_report(rows, output_path)
    else:
        build_excel_report(rows, output_path)

    print(f"Report written to {output_path}")


if __name__ == "__main__":
    main()
