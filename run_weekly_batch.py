
"""Build a downloadable weekly batch demo."""

import csv
from decimal import Decimal

from NSMaster import load_header, read_csv
from WeeklyBatch import add_invoice, ROOT, OUT


def make_header(base, number, expected, weo):
    from datetime import date, timedelta

    header = base.copy()

    end = date.fromisoformat(weo)
    start = end - timedelta(days=6)

    header.update({
        "Invoice Number": number,
        "Expected Total": expected,
        "WEO": weo,
        "Line Date": weo,
        "Service Date Range": (
            f"{start:%m/%d/%Y} - {end:%m/%d/%Y}"
        ),
    })

    return header


def make_rows(reg_amount, ot_amount):
    return [{
        "Unit": "Med-Surg",
        "REG Hours": "8",
        "REG Amount": reg_amount,
        "OT Hours": "4",
        "OT Amount": ot_amount,
        "DT Hours": "0",
        "DT Amount": "0.00",
        "Additional Amount": "0.00",
        "REG Item": "350",
        "OT Item": "351",
        "DT Item": "352",
        "Additional Item": "900",
    }]


def main():

    # Invoice 1: Use the existing NS MASTER data.
    h1 = load_header("DEMO-PV10001")

    rows1 = read_csv(
        ROOT / "billing/InvoiceInput.csv"
    )

    # Additional fictional invoices for this demo.
    h2 = make_header(
        h1, "DEMO-PV10002",
        "1500.00", "2026-10-24"
    )

    h3 = make_header(
        h1, "DEMO-PV10003",
        "1200.00", "2026-10-31"
    )

    batch_path = OUT / (
        f"WeeklyBatch_{h1['Invoice Date']}.csv"
    )

    # Start a fresh batch in this demo only.
    OUT.mkdir(exist_ok=True)
    batch_path.unlink(missing_ok=True)

    print("=== START NEW WEEKLY BATCH ===")

    if not add_invoice(h1, rows1):
        raise SystemExit(1)

    if not add_invoice(
        h2, make_rows("1000.00", "500.00")
    ):
        raise SystemExit(1)

    # Simulate an incorrect invoice input.
    before = batch_path.read_bytes()

    if add_invoice(
        h3, make_rows("800.00", "500.00")
    ):
        raise RuntimeError(
            "Incorrect invoice was accepted."
        )

    if batch_path.read_bytes() != before:
        raise RuntimeError(
            "Existing batch was modified."
        )

    print("Existing invoices protected.")

    # Correct the invoice and try again.
    if not add_invoice(
        h3, make_rows("800.00", "400.00")
    ):
        raise SystemExit(1)

    # Verify accidental duplicate export is blocked.
    before = batch_path.read_bytes()

    if add_invoice(
        h3, make_rows("800.00", "400.00")
    ):
        raise RuntimeError(
            "Duplicate invoice was accepted."
        )

    if batch_path.read_bytes() != before:
        raise RuntimeError(
            "Batch changed after duplicate attempt."
        )

    with batch_path.open(
        newline="", encoding="utf-8"
    ) as f:
        rows = list(csv.DictReader(f))

    total = sum(
        (Decimal(r["Amount"]) for r in rows),
        Decimal("0.00"),
    )

    count = len({
        r["Invoice Number"] for r in rows
    })

    if count != 3 or total != Decimal("4774.00"):
        raise RuntimeError(
            "Unexpected final batch result."
        )

    print("\n=== FINAL WEEKLY BATCH ===")
    print(f"File: {batch_path.name}")
    print(f"Invoices: {count}")
    print(f"Lines: {len(rows)}")
    print(f"Total: ${total:.2f}")
    print("BATCH READY")


if __name__ == "__main__":
    main()
