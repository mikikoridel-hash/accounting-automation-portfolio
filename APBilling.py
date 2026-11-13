
import csv
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "ap-output"

D = Decimal
VMS_RATE = D("0.05")


def read_csv(path):
    with path.open(
        encoding="utf-8-sig", newline=""
    ) as f:
        reader = csv.DictReader(
            line for line in f if line.strip()
        )

        return [
            {
                k.strip(): (v or "").strip()
                for k, v in row.items()
            }
            for row in reader
        ]


def write_csv(path, rows):
    path.parent.mkdir(
        parents=True, exist_ok=True
    )

    with path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(rows[0])
        )

        writer.writeheader()
        writer.writerows(rows)


def money(value):
    amount = D(str(value))

    if not amount.is_finite():
        raise ValueError(
            f"Invalid amount: {value}"
        )

    return amount.quantize(
        D("0.01"),
        rounding=ROUND_HALF_UP,
    )


def normalize(value):
    return value.strip().casefold()


def load_agency_map(path):
    rows = read_csv(path)
    mapping = {}

    # Reuse the existing AR agency mapping.
    # First column = raw name
    # Second column = standard name
    for row in rows:
        values = list(row.values())
        raw, standard = values[:2]

        key = normalize(raw)

        if key in mapping and mapping[key] != standard:
            raise ValueError(
                f"Conflicting agency mapping: {raw}"
            )

        mapping[key] = standard

        # Standard names are also valid inputs.
        standard_key = normalize(standard)

        if (
            standard_key in mapping
            and mapping[standard_key] != standard
        ):
            raise ValueError(
                f"Conflicting standard name: {standard}"
            )

        mapping[standard_key] = standard

    return mapping


def load_vendor_map(path):
    mapping = {}

    required = [
        "Agency Standard",
        "Vendor ID",
        "COGS Account ID",
        "Terms ID",
        "AP Account ID",
        "VMS Fee Account ID",
    ]

    for row in read_csv(path):
        for field in required:
            if not row.get(field):
                raise ValueError(
                    f"Missing vendor mapping field: {field}"
                )

        key = normalize(row["Agency Standard"])

        if key in mapping:
            raise ValueError(
                f"Duplicate vendor mapping: {key}"
            )

        mapping[key] = row

    return mapping


def build_vendor_bills(rows, agency_map, vendor_map):
    if not rows:
        raise ValueError("No approved invoices")

    bills = []
    csv_rows = []
    seen = set()

    for row in rows:
        raw_agency = row["Agency Name"]
        agency_key = normalize(raw_agency)

        if agency_key not in agency_map:
            raise ValueError(
                f"Unknown agency: {raw_agency}"
            )

        agency = agency_map[agency_key]
        vendor = vendor_map.get(normalize(agency))

        if not vendor:
            raise ValueError(
                f"Missing vendor mapping: {agency}"
            )

        vendor_id = vendor["Vendor ID"]
        invoice_no = row["Vendor Invoice Number"]

        if not invoice_no:
            raise ValueError(
                f"Missing vendor invoice number: {agency}"
            )

        duplicate_key = (
            vendor_id,
            normalize(invoice_no),
        )

        if duplicate_key in seen:
            raise ValueError(
                f"Duplicate vendor invoice: {duplicate_key}"
            )

        seen.add(duplicate_key)

        approval_date = date.fromisoformat(
            row["Approval Date"]
        )

        weo = date.fromisoformat(row["WEO"])

        gross = money(row["Total"])
        fee = money(gross * VMS_RATE)
        net = money(gross - fee)

        external_id = (
            f"VB-{vendor_id}-{invoice_no}-"
            f"{approval_date.isoformat()}"
        )

        memo = (
            f'NP: {row["NP ID"]} | '
            f'Super: {row["Super Invoice Number"]} | '
            f'Client: {row["Client Invoice"]} | '
            f'{row["Facility"]} | '
            f'WEO: {weo.isoformat()}'
        )

        # Bill-level summary
        bills.append({
            "External ID": external_id,
            "Vendor ID": vendor_id,
            "Agency": agency,
            "Vendor Invoice Number": invoice_no,
            "Approval Date": approval_date.isoformat(),
            "WEO": weo.isoformat(),
            "Facility": row["Facility"],
            "Gross Amount": str(gross),
            "VMS Fee": str(-fee),
            "Net Payable": str(net),
        })

        # Fields shared by both expense lines
        header = {
            "External ID": external_id,
            "Vendor ID": vendor_id,
            "Reference No": invoice_no,
            "Bill Date": approval_date.isoformat(),
            "Terms ID": vendor["Terms ID"],
            "AP Account ID": vendor["AP Account ID"],
            "Memo": memo,
        }

        # Line 1: Gross agency expense
        csv_rows.append({
            **header,
            "Line ID": 1,
            "Expense Account ID": vendor["COGS Account ID"],
            "Expense Amount": str(gross),
            "Expense Memo": "Agency Invoice",
        })

        # Line 2: Negative VMS fee
        csv_rows.append({
            **header,
            "Line ID": 2,
            "Expense Account ID": vendor["VMS Fee Account ID"],
            "Expense Amount": str(-fee),
            "Expense Memo": "VMS Fee 5%",
        })

        if money(gross - fee) != net:
            raise ValueError(
                f"Bill reconciliation failed: {external_id}"
            )

    gross_total = sum(
        (D(r["Gross Amount"]) for r in bills),
        D("0.00"),
    )

    fee_total = sum(
        (D(r["VMS Fee"]) for r in bills),
        D("0.00"),
    )

    net_total = sum(
        (D(r["Net Payable"]) for r in bills),
        D("0.00"),
    )

    csv_total = sum(
        (D(r["Expense Amount"]) for r in csv_rows),
        D("0.00"),
    )

    if gross_total + fee_total != net_total:
        raise ValueError(
            "Batch reconciliation failed"
        )

    if csv_total != net_total:
        raise ValueError(
            "CSV total does not match net payable"
        )

    if len(csv_rows) != len(bills) * 2:
        raise ValueError(
            "Incorrect number of expense lines"
        )

    reconciliation = [{
        "Vendor Bills": len(bills),
        "CSV Lines": len(csv_rows),
        "Gross Total": str(gross_total),
        "VMS Fee Total": str(fee_total),
        "Net Payable": str(net_total),
        "CSV Total": str(csv_total),
        "Difference": str(csv_total - net_total),
        "Status": "PASS",
    }]

    return bills, csv_rows, reconciliation


def main():
    OUT.mkdir(exist_ok=True)

    export_path = OUT / "VendorBill_Import.csv"

    # Do not leave a previous export available
    # if the current input fails validation.
    export_path.unlink(missing_ok=True)

    rows = read_csv(
        ROOT / "ap" / "ApprovedAgencyInvoices.csv"
    )

    agency_map = load_agency_map(
        ROOT / "mapping" / "AgencyMap.csv"
    )

    vendor_map = load_vendor_map(
        ROOT / "ap" / "VendorMap.csv"
    )

    bills, csv_rows, reconciliation = build_vendor_bills(
        rows,
        agency_map,
        vendor_map,
    )

    write_csv(
        OUT / "VendorBillSummary.csv",
        bills,
    )

    write_csv(
        OUT / "APReconciliation.csv",
        reconciliation,
    )

    write_csv(
        export_path,
        csv_rows,
    )

    result = reconciliation[0]

    print("PASS: AP Billing Automation")
    print(f'Vendor Bills: {result["Vendor Bills"]}')
    print(f'CSV Lines: {result["CSV Lines"]}')
    print(f'Gross Total: ${result["Gross Total"]}')
    print(f'VMS Fee: ${result["VMS Fee Total"]}')
    print(f'Net Payable: ${result["Net Payable"]}')
    print(f'CSV Total: ${result["CSV Total"]}')


if __name__ == "__main__":
    main()
