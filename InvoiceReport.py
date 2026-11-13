
import csv
import argparse
from pathlib import Path
from decimal import Decimal

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "report-output"


def read_csv(path):
    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        lines = (line for line in f if line.strip())
        return list(csv.DictReader(lines))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)


def build_report_data(cleaned_rows, invoice_map):
    mapping = {}

    for row in invoice_map:
        key = (
            row["File Name"].strip(),
            row["Sheet Name"].strip(),
        )

        if key in mapping:
            raise ValueError(
                f"Duplicate invoice mapping: {key}"
            )

        mapping[key] = row

    report_rows = []

    for row in cleaned_rows:
        key = (
            row["SourceFile"].strip(),
            row["SourceTab"].strip(),
        )

        if key not in mapping:
            continue

        invoice = mapping[key]

        if (
            row["Facility Standard"].strip()
            != invoice["Facility"].strip()
        ):
            raise ValueError(
                f"Facility mismatch: {key}"
            )

        report_rows.append({
            "Invoice Number": invoice["Invoice Number"],
            "WEO": invoice["WEO"],
            "Submission Date": invoice["Submission Date"],
            **{
                k: v for k, v in row.items()
                if k not in (
                    "Invoice Number",
                    "WEO",
                    "Submission Date",
                )
            },
        })

    report_rows.sort(
        key=lambda r: (
            r["WEO"],
            r["Invoice Number"],
            r["Service Date"],
        )
    )

    return report_rows


def select_invoice(report_rows, invoice_number):
    selected = [
        row for row in report_rows
        if row["Invoice Number"] == invoice_number
    ]

    if not selected:
        raise ValueError(
            f"No report data found: {invoice_number}"
        )

    return selected


def format_report(rows):
    return [
        {
            "Agency": row["Agency Standard"],
            "Clinician": row["Staff ID"],
            "INVOICE#": row["Invoice Number"],
            "Type": row["Role"],
            "Dept Code/Unit": row["Unit"],
            "Shift Date": row["Service Date"],
            "REG": row["RT Hrs"],
            "OT": row["OT Hrs"],
            "DT": row["DT Hrs"],
            "Total": row["Calculated Total"],
        }
        for row in rows
    ]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--invoice",
        required=True,
        help="Invoice Number to report",
    )

    args = parser.parse_args()

    cleaned_rows = read_csv(
        ROOT / "output" / "CleanedData.csv"
    )

    invoice_map = read_csv(
        ROOT / "billing" / "InvoiceMap.csv"
    )

    report_rows = build_report_data(
        cleaned_rows, invoice_map
    )

    selected = select_invoice(
        report_rows, args.invoice
    )

    total = sum(
        Decimal(row["Calculated Total"])
        for row in selected
    )

    write_csv(
        OUT / "InvoiceReportData.csv",
        report_rows,
    )

    write_csv(
        OUT / "InvoiceReport.csv",
        selected,
    )


    write_csv(
        OUT / "ClientReport.csv",
        format_report(selected),
    )

    
    print(f"Invoice Number: {args.invoice}")
    print(f"Rows: {len(selected)}")
    print(f"Total: ${total:,.2f}")
    print("Invoice Report generated.")


if __name__ == "__main__":
    main()
