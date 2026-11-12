
"""Phase 5: Segmented billing and correction invoices."""

import csv
from pathlib import Path
from decimal import Decimal

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "segment-output"


def load_rows():
    path = ROOT / "billing/ShiftSegments.csv"

    with path.open(
        newline="", encoding="utf-8-sig"
    ) as f:
        reader = csv.DictReader(
            line for line in f if line.strip()
        )
        rows = list(reader)

    # A shift may contain multiple billing lines.
    # Only duplicate Line IDs are rejected.
    ids = [r["Line ID"] for r in rows]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate Line ID detected.")

    return rows


def select_rows(rows, weo, facility, agencies, tabs):

    selected = [
        r.copy() for r in rows
        if r["WEO"] == weo
        and r["Facility"] == facility
        and r["Agency"] in agencies
        and r["SourceTab"] in tabs
    ]

    if not selected:
        raise ValueError("No matching invoice rows.")

    return selected


def calculate(rows):

    for r in rows:
        total = Decimal("0.00")

        for kind in ["RT", "OT", "DT"]:

            hours = Decimal(r[f"{kind} Hrs"])
            rate = Decimal(r[f"{kind} Rate"])

            amount = (hours * rate).quantize(
                Decimal("0.01")
            )

            r[f"{kind} Amount"] = f"{amount:.2f}"

            total += amount

        r["Total Bill"] = f"{total:.2f}"

    return rows


def summarize(rows):

    units = {}

    for r in rows:

        unit = r["Unit"]

        if unit not in units:
            units[unit] = {
                "Unit": unit,
                "RT Hours": Decimal("0"),
                "RT Amount": Decimal("0.00"),
                "OT Hours": Decimal("0"),
                "OT Amount": Decimal("0.00"),
                "DT Hours": Decimal("0"),
                "DT Amount": Decimal("0.00"),
                "Total Bill": Decimal("0.00"),
            }

        summary = units[unit]

        for kind in ["RT", "OT", "DT"]:
            summary[f"{kind} Hours"] += Decimal(
                r[f"{kind} Hrs"]
            )

            summary[f"{kind} Amount"] += Decimal(
                r[f"{kind} Amount"]
            )

        summary["Total Bill"] += Decimal(
            r["Total Bill"]
        )

    return list(units.values())


def write_csv(path, rows):

    with path.open(
        "w", newline="", encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f, fieldnames=list(rows[0].keys())
        )

        writer.writeheader()
        writer.writerows(rows)


def create_invoice(rows, name, tab):

    selected = select_rows(
        rows,
        "2026-10-17",
        "Pineview Medical",
        ["Cedar Staffing"],
        [tab],
    )

    details = calculate(selected)
    summary = summarize(details)

    detail_total = sum(
        (Decimal(r["Total Bill"]) for r in details),
        Decimal("0.00"),
    )

    summary_total = sum(
        (r["Total Bill"] for r in summary),
        Decimal("0.00"),
    )

    if detail_total != summary_total:
        raise ValueError("Summary total mismatch.")

    write_csv(
        OUT / f"{name}_Details.csv",
        details,
    )

    write_csv(
        OUT / f"{name}_UnitSummary.csv",
        summary,
    )

    print(f"\n{name} INVOICE")
    print(f"Source Tab: {tab}")
    print(f"Detail rows: {len(details)}")
    print(f"BillCheck: ${detail_total:.2f}")

    return detail_total


def main():

    OUT.mkdir(exist_ok=True)

    rows = load_rows()

    original = create_invoice(
        rows, "Original", "Cedar Original"
    )

    correction = create_invoice(
        rows, "Correction", "Cedar COR"
    )

    # Verify the expected demo totals.
    assert original == Decimal("1432.00")
    assert correction == Decimal("100.00")

    print("\nALL SEGMENT CHECKS PASSED")


if __name__ == "__main__":
    main()
