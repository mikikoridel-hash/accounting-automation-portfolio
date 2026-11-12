
"""Phase 3B: NS Master reconciliation and CSV export."""

import argparse
import csv
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "ns-output"



def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [
            name.strip() for name in reader.fieldnames
        ]
        return list(reader)



def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def money(value):
    amount = Decimal(value)
    if not amount.is_finite():
        raise ValueError("Invalid amount.")
    return amount


def load_header(invoice_number):
    rows = read_csv(ROOT / "billing/InvoiceHistory.csv")

    matches = [
        r for r in rows
        if r["Invoice Number"] == invoice_number
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Expected one matching invoice: {invoice_number}. "
            f"Found {len(matches)}."
        )

    header = matches[0].copy()

    weo = date.fromisoformat(header["WEO"])
    start = weo - timedelta(days=6)

    header["Service Date Range"] = (
        f"{start:%m/%d/%Y} - {weo:%m/%d/%Y}"
    )
    header["Line Date"] = header["WEO"]

    money(header["Expected Total"])

    return header


def build_lines(header, rows):
    lines = []

    for row in rows:
        for kind in ["REG", "OT", "DT", "Additional"]:

            amount = money(row[f"{kind} Amount"])

            if amount == 0:
                continue

            item = row[f"{kind} Item"].strip()

            if not item:
                raise ValueError(
                    f"Missing Item: {row['Unit']} / {kind}"
                )

            hours = (
                row[f"{kind} Hours"]
                if kind != "Additional"
                else "1"
            )

            lines.append({
                "Invoice Number": header["Invoice Number"],
                "Invoice Date": header["Invoice Date"],
                "Customer ID": header["Customer ID"],
                "Terms": header["Terms"],
                "Service Date Range": header["Service Date Range"],
                "Line Date": header["Line Date"],
                "Unit": row["Unit"],
                "Billing Type": kind,
                "Item": item,
                "Quantity": hours,
                "Amount": f"{amount:.2f}",
            })

    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--invoice", required=True)
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)

    export_path = OUT / "NetSuite_Import.csv"

    # Remove any previous export before checking.
    export_path.unlink(missing_ok=True)

    header = load_header(args.invoice)

    write_csv(
        OUT / "InvoiceHeader.csv",
        list(header.keys()),
        [header],
    )

    rows = read_csv(ROOT / "billing/InvoiceInput.csv")

    if not rows:
        raise ValueError("InvoiceInput is empty.")

    lines = build_lines(header, rows)

    expected = money(header["Expected Total"])

    actual = sum(
        (money(r["Amount"]) for r in lines),
        Decimal("0.00"),
    )

    difference = actual - expected

    passed = difference == 0 and bool(lines)
    status = "PASS" if passed else "FAIL"

    report = {
        "Invoice Number": args.invoice,
        "Expected Total": f"{expected:.2f}",
        "Actual Total": f"{actual:.2f}",
        "Difference": f"{difference:.2f}",
        "Status": status,
    }

    write_csv(
        OUT / "Reconciliation.csv",
        list(report.keys()),
        [report],
    )

    print("NS MASTER - CHECK AMOUNT TOTAL")
    print("-" * 40)

    for key, value in report.items():
        print(f"{key}: {value}")

    if not passed:
        print("EXPORT BLOCKED: Check invoice amounts.")
        print("NetSuite CSV was NOT created.")
        raise SystemExit(1)

    write_csv(
        export_path,
        list(lines[0].keys()),
        lines,
    )

    print("EXPORT SUCCESS: NetSuite_Import.csv")


if __name__ == "__main__":
    main()
