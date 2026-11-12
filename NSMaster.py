
"""Phase 3A: Load invoice header from InvoiceHistory."""

import argparse
import csv
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal

ROOT = Path(__file__).resolve().parent


def load_header(invoice_number):
    path = ROOT / "billing/InvoiceHistory.csv"

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

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

    expected = Decimal(header["Expected Total"])

    if not expected.is_finite():
        raise ValueError("Invalid expected total.")

    return header


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--invoice", required=True)
    args = parser.parse_args()

    header = load_header(args.invoice)

    out = ROOT / "ns-output"
    out.mkdir(exist_ok=True)

    with (out / "InvoiceHeader.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(header.keys())
        )
        writer.writeheader()
        writer.writerow(header)

    print("INVOICE HEADER")
    print("-" * 40)

    for key, value in header.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
