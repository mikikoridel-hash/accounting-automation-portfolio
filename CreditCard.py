import csv
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "credit-card"
OUTPUT = ROOT / "cc-output"

CENT = Decimal("0.01")

EXPORT_FIELDS = [
    "Date",
    "Vendor Internal ID",
    "Expense Acct Internal ID",
    "Amount",
    "Memo",
    "Line Description",
    "Credit Card Acct Internal ID",
    "Reference #",
]

REVIEW_FIELDS = [
    "Source File",
    "Source Row",
    "Date",
    "Description",
    "Card Member",
    "Account #",
    "Amount",
    "Reason",
]

SUMMARY_FIELDS = [
    "Account",
    "Raw Count",
    "Raw Total",
    "Import Count",
    "Import Total",
    "Manual Count",
    "Manual Total",
    "Missing Mapping Count",
    "Missing Mapping Total",
    "Difference",
    "Status",
]


def read_csv(path):
    with path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        return [
            {
                key.strip(): (value or "").strip()
                for key, value in row.items()
            }
            for row in reader
            if any(row.values())
        ]


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w", encoding="utf-8", newline=""
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=fields
        )
        writer.writeheader()
        writer.writerows(rows)


def money(value):
    amount = Decimal(value)

    if not amount.is_finite():
        raise ValueError("Invalid amount")

    return amount.quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def load_vendor_map():
    rows = read_csv(DATA / "VendorMap.csv")
    mapping = {}

    for row in rows:
        key = row["Vendor Key"].upper()

        if not key:
            raise ValueError("Empty Vendor Key")

        if key in mapping:
            raise ValueError(
                f"Duplicate Vendor Key: {key}"
            )

        mapping[key] = row

    return mapping


def load_card_map():
    rows = read_csv(DATA / "CardAccountMap.csv")
    mapping = {}

    for row in rows:
        account = row["Card Account Number"]

        if account in mapping:
            raise ValueError(
                f"Duplicate card account: {account}"
            )

        if not row["Credit Card Account Internal ID"]:
            raise ValueError(
                f"Missing card account ID: {account}"
            )

        if not row["Reference Prefix"]:
            raise ValueError(
                f"Missing reference prefix: {account}"
            )

        mapping[account] = row

    return mapping


def find_vendor(description, vendor_map):
    description = description.upper()

    matches = [
        key for key in vendor_map
        if key in description
    ]

    if not matches:
        return None

    # Prefer the most specific matching key.
    matches.sort(key=len, reverse=True)

    if (
        len(matches) > 1
        and len(matches[0]) == len(matches[1])
    ):
        raise ValueError(
            f"Ambiguous vendor mapping: {description}"
        )

    return vendor_map[matches[0]]


def review_row(row, source, row_number, reason):
    return {
        "Source File": source,
        "Source Row": row_number,
        "Date": row["Date"],
        "Description": row["Description"],
        "Card Member": row["Card Member"],
        "Account #": row["Account #"],
        "Amount": row["Amount"],
        "Reason": reason,
    }


def process_account(
    source_file,
    expected_account,
    vendor_map,
    card_map,
):
    source_rows = read_csv(source_file)

    card = card_map[expected_account]
    account_name = card["Account Name"]
    account_id = card[
        "Credit Card Account Internal ID"
    ]
    prefix = card["Reference Prefix"]

    export_rows = []
    manual_rows = []
    missing_rows = []

    sequence = Counter()

    raw_total = Decimal("0.00")
    import_total = Decimal("0.00")
    manual_total = Decimal("0.00")
    missing_total = Decimal("0.00")

    for row_number, row in enumerate(
        source_rows, start=2
    ):
        description = row["Description"]
        cardholder = row["Card Member"]
        amount = money(row["Amount"])
        raw_total += amount

        if row["Account #"] != expected_account:
            raise ValueError(
                f"Unexpected account in "
                f"{source_file.name}, row {row_number}"
            )

        # Validate the transaction date.
        date = datetime.strptime(
            row["Date"], "%m/%d/%Y"
        )

        # Payments and refunds are manual entries.
        # Check these before vendor mapping.
        if "PAYMENT" in description.upper():
            manual_rows.append(
                review_row(
                    row,
                    source_file.name,
                    row_number,
                    "Payment",
                )
            )
            manual_total += amount
            continue

        if amount < 0:
            manual_rows.append(
                review_row(
                    row,
                    source_file.name,
                    row_number,
                    "Refund / Credit",
                )
            )
            manual_total += amount
            continue

        # Identify vendor and expense account.
        vendor = find_vendor(
            description, vendor_map
        )

        if vendor is None:
            missing_rows.append(
                review_row(
                    row,
                    source_file.name,
                    row_number,
                    "Missing Vendor Key",
                )
            )
            missing_total += amount
            continue

        if (
            not vendor["Vendor Internal ID"]
            or not vendor["Expense Account Internal ID"]
        ):
            missing_rows.append(
                review_row(
                    row,
                    source_file.name,
                    row_number,
                    "Incomplete Vendor Mapping",
                )
            )
            missing_total += amount
            continue

        # Cardholders share the same parent account.
        # Preserve the cardholder name in the memo.
        date_key = date.strftime("%Y%m%d")
        sequence[date_key] += 1

        reference = (
            f"{prefix}-{date_key}-"
            f"{sequence[date_key]:03d}"
        )

        export_rows.append({
            "Date": date.strftime("%m/%d/%Y"),
            "Vendor Internal ID":
                vendor["Vendor Internal ID"],
            "Expense Acct Internal ID":
                vendor["Expense Account Internal ID"],
            "Amount": str(amount),
            "Memo": cardholder,
            "Line Description":
                f"{description} | {cardholder}",
            "Credit Card Acct Internal ID":
                account_id,
            "Reference #": reference,
        })

        import_total += amount

    # Final export QC.
    missing_export = sum(
        not row["Vendor Internal ID"]
        or not row["Expense Acct Internal ID"]
        for row in export_rows
    )

    payment_export = sum(
        "PAYMENT" in row[
            "Line Description"
        ].upper()
        for row in export_rows
    )

    negative_export = sum(
        money(row["Amount"]) < 0
        for row in export_rows
    )

    references = [
        row["Reference #"]
        for row in export_rows
    ]

    duplicate_references = (
        len(references) - len(set(references))
    )

    difference = (
        raw_total
        - import_total
        - manual_total
        - missing_total
    )

    count_difference = (
        len(source_rows)
        - len(export_rows)
        - len(manual_rows)
        - len(missing_rows)
    )

    passed = (
        not missing_rows
        and missing_export == 0
        and payment_export == 0
        and negative_export == 0
        and duplicate_references == 0
        and difference == 0
        and count_difference == 0
    )

    status = "PASS" if passed else "BLOCKED"

    print()
    print(f"{account_name} — Export Check Complete")
    print(
        f"Missing Mapping rows: {len(missing_rows)}"
    )
    print(
        f"Missing Vendor IDs in export: "
        f"{missing_export}"
    )
    print(
        f"PAYMENT rows found: {payment_export}"
    )
    print(
        f"Negative Amount rows found: "
        f"{negative_export}"
    )
    print(
        f"Duplicate references: "
        f"{duplicate_references}"
    )
    print(f"Manual Entry rows: {len(manual_rows)}")
    print(f"Reconciliation Difference: {difference}")
    print(f"Status: {status}")

    summary = {
        "Account": account_name,
        "Raw Count": len(source_rows),
        "Raw Total": str(raw_total),
        "Import Count": len(export_rows),
        "Import Total": str(import_total),
        "Manual Count": len(manual_rows),
        "Manual Total": str(manual_total),
        "Missing Mapping Count": len(missing_rows),
        "Missing Mapping Total": str(missing_total),
        "Difference": str(difference),
        "Status": status,
    }

    return {
        "export": export_rows,
        "manual": manual_rows,
        "missing": missing_rows,
        "summary": summary,
        "passed": passed,
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Remove old import files so a failed run
    # cannot leave an outdated export behind.
    for filename in [
        "AMEX_A_Import.csv",
        "AMEX_B_Import.csv",
    ]:
        (OUTPUT / filename).unlink(
            missing_ok=True
        )

    vendor_map = load_vendor_map()
    card_map = load_card_map()

    result_a = process_account(
        DATA / "AMEX_Account_A.csv",
        "DEMO-1001",
        vendor_map,
        card_map,
    )

    result_b = process_account(
        DATA / "AMEX_Account_B.csv",
        "DEMO-2002",
        vendor_map,
        card_map,
    )

    # Keep review and reconciliation files
    # even when the import batch is blocked.
    write_csv(
        OUTPUT / "MissingVendor_QC.csv",
        REVIEW_FIELDS,
        result_a["missing"] + result_b["missing"],
    )

    write_csv(
        OUTPUT / "ManualEntry_Review.csv",
        REVIEW_FIELDS,
        result_a["manual"] + result_b["manual"],
    )

    write_csv(
        OUTPUT / "CC_Reconciliation.csv",
        SUMMARY_FIELDS,
        [
            result_a["summary"],
            result_b["summary"],
        ],
    )

    # Do not release import files unless
    # both accounts pass all QC checks.
    if not (
        result_a["passed"]
        and result_b["passed"]
    ):
        raise SystemExit(
            "Import blocked. Review QC files "
            "and correct missing mappings."
        )

    write_csv(
        OUTPUT / "AMEX_A_Import.csv",
        EXPORT_FIELDS,
        result_a["export"],
    )

    write_csv(
        OUTPUT / "AMEX_B_Import.csv",
        EXPORT_FIELDS,
        result_b["export"],
    )

    print()
    print("Both AMEX accounts passed QC.")
    print("NetSuite import files created.")


if __name__ == "__main__":
    main()
