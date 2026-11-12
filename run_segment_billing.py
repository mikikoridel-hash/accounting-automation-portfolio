
"""Connect segmented invoices to NS Master and Weekly Batch."""

import csv
from decimal import Decimal

import SegmentInvoice as segment
import WeeklyBatch as batch

from NSMaster import load_header


# Fictional NetSuite Item mapping for this demo.
ITEM_MAP = {
    "ICU-CHARGE": {
        "REG": "430",
        "OT": "431",
        "DT": "432",
    },
    "ICU-CHARGE-PRECEPTOR": {
        "REG": "440",
        "OT": "441",
        "DT": "442",
    },
    "ICU-PRECEPTOR": {
        "REG": "450",
        "OT": "451",
        "DT": "452",
    },
}


def convert_to_invoice_input(summary):

    rows = []

    for r in summary:

        unit = r["Unit"]

        if unit not in ITEM_MAP:
            raise ValueError(
                f"Missing Item mapping: {unit}"
            )

        items = ITEM_MAP[unit]

        rows.append({
            "Unit": unit,
            "REG Hours": str(r["RT Hours"]),
            "REG Amount": str(r["RT Amount"]),
            "OT Hours": str(r["OT Hours"]),
            "OT Amount": str(r["OT Amount"]),
            "DT Hours": str(r["DT Hours"]),
            "DT Amount": str(r["DT Amount"]),
            "Additional Amount": "0.00",
            "REG Item": items["REG"],
            "OT Item": items["OT"],
            "DT Item": items["DT"],
            "Additional Item": "900",
        })

    return rows


def process_invoice(source_rows, invoice_number, source_tab):

    header = load_header(invoice_number)

    selected = segment.select_rows(
        source_rows,
        header["WEO"],
        header["Facility"],
        ["Cedar Staffing"],
        [source_tab],
    )

    details = segment.calculate(selected)
    summary = segment.summarize(details)

    invoice_input = convert_to_invoice_input(summary)

    segment.write_csv(
        segment.OUT / f"{invoice_number}_Details.csv",
        details,
    )

    segment.write_csv(
        segment.OUT / f"{invoice_number}_InvoiceInput.csv",
        invoice_input,
    )

    print(f"\nProcessing {invoice_number}")
    print(f"Source Tab: {source_tab}")
    print(f"Work Week: {header['WEO']}")
    print(f"Billing Date: {header['Invoice Date']}")
    print(f"Detail Rows: {len(details)}")

    if not batch.add_invoice(header, invoice_input):
        raise RuntimeError(
            f"Invoice blocked: {invoice_number}"
        )


def verify_batch(path, invoice_number, expected):

    with path.open(
        newline="", encoding="utf-8"
    ) as f:
        rows = list(csv.DictReader(f))

    numbers = {
        r["Invoice Number"] for r in rows
    }

    if numbers != {invoice_number}:
        raise RuntimeError(
            "Unexpected invoice in weekly batch."
        )

    total = sum(
        (Decimal(r["Amount"]) for r in rows),
        Decimal("0.00"),
    )

    if total != expected:
        raise RuntimeError("Batch total mismatch.")

    print(f"\nVerified: {path.name}")
    print(f"Invoice: {invoice_number}")
    print(f"Total: ${total:.2f}")


def main():

    segment.OUT.mkdir(exist_ok=True)
    batch.OUT.mkdir(exist_ok=True)

    # Start fresh output for this isolated demo.
    for day in ["2026-11-09", "2026-11-16"]:
        path = batch.OUT / f"WeeklyBatch_{day}.csv"
        path.unlink(missing_ok=True)

    source_rows = segment.load_rows()

    # First billing: Original shift segments.
    process_invoice(
        source_rows,
        "DEMO-PV10004",
        "Cedar Original",
    )

    # Later billing: Additional approved DT only.
    process_invoice(
        source_rows,
        "DEMO-PV10005",
        "Cedar COR",
    )

    verify_batch(
        batch.OUT / "WeeklyBatch_2026-11-09.csv",
        "DEMO-PV10004",
        Decimal("1432.00"),
    )

    verify_batch(
        batch.OUT / "WeeklyBatch_2026-11-16.csv",
        "DEMO-PV10005",
        Decimal("100.00"),
    )

    print("\nALL SEGMENT BILLING CHECKS PASSED")


if __name__ == "__main__":
    main()
