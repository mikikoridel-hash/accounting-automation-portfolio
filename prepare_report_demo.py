
import csv
from pathlib import Path
from decimal import Decimal
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

ROOT = Path(__file__).resolve().parent

WORKBOOK = ROOT / "raw" / "WEO_2026-10-17.xlsx"
SEGMENTS = ROOT / "billing" / "ShiftSegments.csv"
INVOICE_MAP = ROOT / "billing" / "InvoiceMap.csv"

D = Decimal


def read_csv(path):
    with path.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        return list(csv.DictReader(
            line for line in f if line.strip()
        ))


def make_snapshot(wb, sheet_name, rows):
    if sheet_name in wb.sheetnames:
        raise ValueError(
            f"Invoice snapshot already exists: {sheet_name}"
        )

    if not rows:
        raise ValueError(
            f"No billing rows for {sheet_name}"
        )

    ws = wb.create_sheet(sheet_name)

    # Black invoice tab
    ws.sheet_properties.tabColor = "000000"

    headers = [
        "Shift ID",
        "Service Date",
        "Agency",
        "Facility",
        "Staff ID",
        "Role",
        "Unit",
        "RT Hrs",
        "OT Hrs",
        "DT Hrs",
        "Charge RT Hrs",
        "Charge OT Hrs",
        "Regular Rate",
        "OT Rate",
        "DT Rate",
        "Charge RT Premium",
        "Charge OT Premium",
        "Additional",
        "Additional Reason",
        "Calculated Total",
    ]

    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(
            bold=True, color="FFFFFF"
        )
        cell.fill = PatternFill(
            "solid", fgColor="000000"
        )

    total = D("0.00")

    for row in rows:
        rt = D(row["RT Hrs"])
        ot = D(row["OT Hrs"])
        dt = D(row["DT Hrs"])

        rt_rate = D(row["RT Rate"])
        ot_rate = D(row["OT Rate"])
        dt_rate = D(row["DT Rate"])

        amount = (
            rt * rt_rate
            + ot * ot_rate
            + dt * dt_rate
        ).quantize(D("0.01"))

        ws.append([
            row["Shift ID"],
            row["Service Date"],
            row["Agency"],
            row["Facility"],
            row["Staff ID"],
            "RN",
            row["Unit"],
            float(rt),
            float(ot),
            float(dt),
            0,
            0,
            float(rt_rate),
            float(ot_rate),
            float(dt_rate),
            0,
            0,
            0,
            "",
            float(amount),
        ])

        ws.cell(
            ws.max_row, 20
        ).number_format = '$#,##0.00'

        total += amount

    ws.freeze_panes = "A2"

    print(
        f"{sheet_name}: "
        f"{len(rows)} rows | ${total:,.2f}"
    )

    return total


def main():
    segments = read_csv(SEGMENTS)
    invoice_map = read_csv(INVOICE_MAP)

    wb = load_workbook(WORKBOOK)

    configurations = [
        (
            "DEMO-PV10004",
            "Cedar Original",
            D("1432.00"),
        ),
        (
            "DEMO-PV10005",
            "Cedar COR",
            D("100.00"),
        ),
    ]

    for invoice_number, source_tab, expected in configurations:
        matches = [
            row for row in invoice_map
            if row["Invoice Number"] == invoice_number
            and row["File Name"] == WORKBOOK.name
        ]

        if len(matches) != 1:
            raise ValueError(
                f"Invalid mapping: {invoice_number}"
            )

        mapping = matches[0]

        selected = [
            row for row in segments
            if row["SourceTab"] == source_tab
            and row["WEO"] == mapping["WEO"]
            and row["Facility"] == mapping["Facility"]
        ]

        actual = make_snapshot(
            wb,
            mapping["Sheet Name"],
            selected,
        )

        if actual != expected:
            raise ValueError(
                f"{invoice_number}: "
                f"Expected {expected}, got {actual}"
            )

    wb.save(WORKBOOK)

    print("PASS: historical invoice snapshots prepared")


if __name__ == "__main__":
    main()
