
"""Phase 2A: extract selected billing rows."""
import argparse
import csv
from decimal import Decimal
from datetime import date
from ImportTool import ROOT, run


def extract(rows, weo, facility, agencies, tabs=()):
    date.fromisoformat(weo)
    agencies = set(agencies)

    if not agencies or not facility:
        raise ValueError(
            "Select a facility and at least one agency."
        )


    candidates = [
        r for r in rows
        if r['SourceFile'] == f'WEO_{weo}.xlsx'
        and r.get('Source Type') != 'Invoice Snapshot'
        and (not tabs or r['SourceTab'] in tabs)
    ]


    if any(r["Mapping Status"] != "OK"
           for r in candidates):
        raise ValueError(
            "Mapping QC required. Resolve it before extraction."
        )

    selected = [
        r for r in candidates
        if r["Facility Standard"] == facility
        and r["Agency Standard"] in agencies
    ]

    missing = agencies - {
        r["Agency Standard"] for r in selected
    }

    if missing:
        raise ValueError(
            "No matching rows for: " + ", ".join(sorted(missing))
        )

    if not selected:
        raise ValueError("No matching billing rows.")

    return selected


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=fields, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


def build(root, weo, facility, agencies, tabs=()):
    with (root / "output/CleanedData.csv").open(
        newline="", encoding="utf-8"
    ) as f:
        rows = list(csv.DictReader(f))

    selected = extract(
        rows, weo, facility, agencies, tabs
    )

    out = root / "invoice-output"
    out.mkdir(exist_ok=True)

    fields = [
        "WEO",
        "Facility Standard",
        "Agency Standard",
        "SourceFile",
        "SourceTab",
        "Shift ID",
        "Staff ID",
        "Role",
        "Unit",
        "Service Date",
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

    write_csv(
        out / "InvoiceRows.csv",
        fields,
        [{"WEO": weo, **r} for r in selected],
    )

    totals = []

    for agency in sorted(set(agencies)):
        group = [
            r for r in selected
            if r["Agency Standard"] == agency
        ]

        amount = sum(
            (Decimal(r["Calculated Total"]) for r in group),
            Decimal("0.00"),
        )

        totals.append({
            "Agency": agency,
            "Rows": len(group),
            "BillCheck": str(amount),
        })

    total = sum(
        (Decimal(r["BillCheck"]) for r in totals),
        Decimal("0.00"),
    )

    totals.append({
        "Agency": "TOTAL",
        "Rows": len(selected),
        "BillCheck": str(total),
    })

    write_csv(
        out / "BillCheck.csv",
        ["Agency", "Rows", "BillCheck"],
        totals,
    )

    print(
        f"WEO {weo} | {facility} | "
        f"{len(selected)} rows | BillCheck ${total}"
    )

    return selected, total


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--weo", required=True)
    parser.add_argument("--facility", required=True)
    parser.add_argument("--agencies", required=True)
    parser.add_argument("--tabs", default="")

    args = parser.parse_args()

    def split(value):
        return [
            v.strip() for v in value.split(",") if v.strip()
        ]

    run(ROOT)

    build(
        ROOT,
        args.weo,
        args.facility,
        split(args.agencies),
        split(args.tabs),
    )


if __name__ == "__main__":
    main()
