
"""Phase 4: Weekly invoice batch builder."""

import csv
from pathlib import Path
from decimal import Decimal
from datetime import date

from NSMaster import build_lines, money

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "batch-output"


def add_invoice(header, rows, replace=False):

    invoice = header["Invoice Number"].strip()

    if not invoice:
        raise ValueError("Invoice Number is required.")

    billing_date = date.fromisoformat(
        header["Invoice Date"]
    ).isoformat()

    OUT.mkdir(exist_ok=True)

    batch_path = OUT / f"WeeklyBatch_{billing_date}.csv"

    # Build invoice lines.
    lines = build_lines(header, rows)

    if not lines:
        raise ValueError("No invoice lines to export.")

    expected = money(header["Expected Total"])

    actual = sum(
        (money(r["Amount"]) for r in lines),
        Decimal("0.00"),
    )

    difference = actual - expected

    print(f"\nInvoice: {invoice}")
    print(f"Expected Total: ${expected:.2f}")
    print(f"Actual Total: ${actual:.2f}")
    print(f"Difference: ${difference:.2f}")

    # Stop before changing the existing batch.
    if difference != 0:
        print("FAIL - EXPORT BLOCKED")
        print("Existing batch remains unchanged.")
        return False

    fields = list(lines[0].keys())
    existing = []

    # Load invoices already added to this batch.
    if batch_path.exists():
        with batch_path.open(
            newline="", encoding="utf-8"
        ) as f:
            reader = csv.DictReader(f)

            if reader.fieldnames != fields:
                raise ValueError(
                    "Batch column structure does not match."
                )

            existing = list(reader)

    already_added = any(
        r["Invoice Number"] == invoice
        for r in existing
    )

    # Prevent accidental duplicate exports.
    if already_added and not replace:
        print("BLOCKED - Invoice already in batch.")
        return False

    # Explicit replacement of an existing invoice.
    if already_added and replace:
        existing = [
            r for r in existing
            if r["Invoice Number"] != invoice
        ]

        print("Replacing existing invoice lines.")

    combined = existing + lines

    # Write safely before replacing the batch file.
    temp_path = batch_path.with_suffix(".tmp")

    with temp_path.open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=fields
        )
        writer.writeheader()
        writer.writerows(combined)

    temp_path.replace(batch_path)

    invoice_count = len({
        r["Invoice Number"] for r in combined
    })

    batch_total = sum(
        (money(r["Amount"]) for r in combined),
        Decimal("0.00"),
    )

    print("PASS - Invoice added to batch.")
    print(f"Batch file: {batch_path.name}")
    print(f"Invoice count: {invoice_count}")
    print(f"Line count: {len(combined)}")
    print(f"Batch total: ${batch_total:.2f}")

    return True
