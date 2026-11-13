
import csv
from pathlib import Path
from collections import Counter
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

from InvoiceReport import format_report

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "report-output"

HEADERS = [
    "Agency",
    "Clinician",
    "INVOICE#",
    "Type",
    "Dept Code/Unit",
    "Shift Date",
    "REG",
    "OT",
    "DT",
    "Total",
]


def read_csv(path):
    with path.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        return list(csv.DictReader(f))


def main():
    rows = read_csv(
        OUT / "InvoiceReportData.csv"
    )

    invoice_map = read_csv(
        ROOT / "billing" / "InvoiceMap.csv"
    )

    if not rows:
        raise ValueError("No invoice report data")

    wb = Workbook()

    report = wb.active
    report.title = "Report"

    data = wb.create_sheet("Data")
    invoice = wb.create_sheet("Invoice")

    # -----------------------------
    # Data sheet
    # -----------------------------

    data.append(HEADERS + ["Lookup Key"])

    counts = Counter()

    for row in format_report(rows):
        inv = row["INVOICE#"]
        counts[inv] += 1

        values = []

        for h in HEADERS:
            value = row[h]

            if h == "Shift Date":
                value = date.fromisoformat(value)

            elif h in ("REG", "OT", "DT", "Total"):
                value = float(Decimal(value))

            values.append(value)

        values.append(f"{inv}|{counts[inv]}")

        data.append(values)

    data.column_dimensions["K"].hidden = True

    for r in range(2, data.max_row + 1):
        data.cell(r, 6).number_format = "mm/dd/yyyy"
        data.cell(r, 10).number_format = '$#,##0.00'

    # -----------------------------
    # Invoice mapping sheet
    # -----------------------------

    invoice.append([
        "File Name",
        "WEO",
        "Sheet Name",
        "Invoice Number",
        "Facility",
        "Submission Date",
    ])

    available = set(counts)

    for row in sorted(
        invoice_map,
        key=lambda r: (
            r["WEO"],
            r["Invoice Number"]
        ),
    ):
        if row["Invoice Number"] not in available:
            continue

        invoice.append([
            row["File Name"],
            date.fromisoformat(row["WEO"]),
            row["Sheet Name"],
            row["Invoice Number"],
            row["Facility"],
            date.fromisoformat(
                row["Submission Date"]
            ),
        ])

    for r in range(2, invoice.max_row + 1):
        invoice.cell(r, 2).number_format = "mm/dd/yyyy"
        invoice.cell(r, 6).number_format = "mm/dd/yyyy"

    # -----------------------------
    # Report sheet
    # -----------------------------

    last_invoice = invoice.max_row
    last_data = data.max_row

    report["A1"] = "Invoice #"
    report["B1"] = invoice["D2"].value

    report["B1"].fill = PatternFill(
        "solid", fgColor="FFFF00"
    )

    report["B1"].font = Font(bold=True)

    # Dropdown of available invoices
    options = sorted(available)

    validation = DataValidation(
        type="list",
        formula1='"' + ",".join(options) + '"'
    )

    validation.showErrorMessage = True
    validation.error = "Select a valid invoice number"

    report.add_data_validation(validation)
    validation.add(report["B1"])

    lookup = (
        f'MATCH($B$1,Invoice!$D$2:$D${last_invoice},0)'
    )

    weo = (
        f'INDEX(Invoice!$B$2:$B${last_invoice},{lookup})'
    )

    report.merge_cells("A2:J2")

    report["A2"] = (
        f'=IFERROR("Week: "&'
        f'TEXT({weo}-6,"mm/dd/yyyy")&'
        f'" - "&TEXT({weo},"mm/dd/yyyy"),"")'
    )

    report["A3"] = (
        f'=IFERROR(INDEX('
        f'Invoice!$E$2:$E${last_invoice},'
        f'{lookup}),"")'
    )

    report["C3"] = "=$B$1"

    report["J3"] = (
        f'=SUMIF(Data!$C$2:$C${last_data},'
        f'$B$1,Data!$J$2:$J${last_data})'
    )

    report["J3"].number_format = '$#,##0.00'

    for col, header in enumerate(HEADERS, 1):
        report.cell(4, col, header)

    # Display enough rows for the largest invoice.
    max_rows = max(counts.values())

    for r in range(5, 5 + max_rows):
        lookup_key = (
            f'MATCH($B$1&"|"&ROWS($A$5:A{r}),'
            f'Data!$K$2:$K${last_data},0)'
        )

        for col in range(1, 11):
            letter = chr(64 + col)

            report.cell(
                r, col,
                f'=IFERROR(INDEX('
                f'Data!${letter}$2:'
                f'${letter}${last_data},'
                f'{lookup_key}),"")'
            )

        report.cell(r, 6).number_format = "mm/dd/yyyy"

        for col in (7, 8, 9):
            report.cell(r, col).number_format = "0.00"

        report.cell(r, 10).number_format = '$#,##0.00'

    # -----------------------------
    # Formatting
    # -----------------------------

    gray = PatternFill(
        "solid", fgColor="D9D9D9"
    )

    for row in report.iter_rows(
        min_row=2, max_row=4,
        min_col=1, max_col=10
    ):
        for cell in row:
            cell.fill = gray
            cell.font = Font(bold=True)

    widths = [24, 22, 22, 10, 30, 16, 10, 10, 10, 16]

    for col, width in enumerate(widths, 1):
        letter = chr(64 + col)

        report.column_dimensions[letter].width = width
        data.column_dimensions[letter].width = width

    for col, width in zip(
        "ABCDEF", [32, 16, 32, 24, 26, 18]
    ):
        invoice.column_dimensions[col].width = width

    for ws in (data, invoice):
        for cell in ws[1]:
            cell.fill = gray
            cell.font = Font(bold=True)

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    report.freeze_panes = "A5"

    for cell in report[4]:
        cell.alignment = Alignment(
            horizontal="center"
        )

    report.sheet_view.showGridLines = False

    path = OUT / "InvoiceReport.xlsx"

    wb.save(path)

    print(f"Excel Invoice Report generated: {path}")
    print(f"Available invoices: {len(available)}")


if __name__ == "__main__":
    main()
