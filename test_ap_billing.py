
from decimal import Decimal

from APBilling import (
    ROOT,
    read_csv,
    load_agency_map,
    load_vendor_map,
    build_vendor_bills,
)

D = Decimal


def expect_error(func, message):
    try:
        func()
    except ValueError as e:
        assert message in str(e), str(e)
        print(f"PASS: blocked - {e}")
    else:
        raise AssertionError(
            f"Expected error: {message}"
        )


def main():
    rows = read_csv(
        ROOT / "ap" / "ApprovedAgencyInvoices.csv"
    )

    agency_map = load_agency_map(
        ROOT / "mapping" / "AgencyMap.csv"
    )

    vendor_map = load_vendor_map(
        ROOT / "ap" / "VendorMap.csv"
    )

    # ---------------------------------
    # Test 1: Normal AP batch
    # ---------------------------------

    bills, csv_rows, qc = build_vendor_bills(
        rows,
        agency_map,
        vendor_map,
    )

    assert len(bills) == 4
    assert len(csv_rows) == 8

    assert D(qc[0]["Gross Total"]) == D("5456.00")
    assert D(qc[0]["VMS Fee Total"]) == D("-272.80")
    assert D(qc[0]["Net Payable"]) == D("5183.20")
    assert D(qc[0]["CSV Total"]) == D("5183.20")
    assert D(qc[0]["Difference"]) == D("0.00")
    assert qc[0]["Status"] == "PASS"

    print("PASS: normal AP batch totals")

    # ---------------------------------
    # Test 2: Agency name variations
    # ---------------------------------

    cedar_names = [
        "CEDAR STAFFING",
        "Cedar Staffing",
        "Cedar Staff LLC",
    ]

    for name in cedar_names:
        sample = [{
            **rows[0],
            "Agency Name": name,
        }]

        b, lines, _ = build_vendor_bills(
            sample,
            agency_map,
            vendor_map,
        )

        assert b[0]["Vendor ID"] == "9001"
        assert b[0]["Agency"] == "Cedar Staffing"
        assert lines[0]["Expense Account ID"] == "5101"

    print("PASS: agency name normalization")

    # ---------------------------------
    # Test 3: Vendor-specific COGS
    # ---------------------------------

    for bill in bills:
        lines = [
            r for r in csv_rows
            if r["External ID"] == bill["External ID"]
        ]

        assert len(lines) == 2

        vendor_id = bill["Vendor ID"]

        expected_cogs = {
            "9001": "5101",
            "9002": "5102",
        }[vendor_id]

        assert (
            lines[0]["Expense Account ID"]
            == expected_cogs
        )

        assert (
            lines[1]["Expense Account ID"]
            == "5201"
        )

        assert (
            lines[0]["Vendor ID"]
            == lines[1]["Vendor ID"]
        )

        assert (
            lines[0]["External ID"]
            == lines[1]["External ID"]
        )

    print("PASS: vendor-specific COGS accounts")

    # ---------------------------------
    # Test 4: VMS Fee rounding
    # ---------------------------------

    sample = [{
        **rows[0],
        "Total": "100.10",
    }]

    b, lines, _ = build_vendor_bills(
        sample,
        agency_map,
        vendor_map,
    )

    assert D(b[0]["VMS Fee"]) == D("-5.01")
    assert D(b[0]["Net Payable"]) == D("95.09")

    assert D(lines[0]["Expense Amount"]) == D("100.10")
    assert D(lines[1]["Expense Amount"]) == D("-5.01")

    print("PASS: VMS Fee rounding")

    # ---------------------------------
    # Test 5: Unknown agency
    # ---------------------------------

    expect_error(
        lambda: build_vendor_bills(
            [{
                **rows[0],
                "Agency Name": "Unknown Agency",
            }],
            agency_map,
            vendor_map,
        ),
        "Unknown agency",
    )

    # ---------------------------------
    # Test 6: Missing vendor mapping
    # ---------------------------------

    expect_error(
        lambda: build_vendor_bills(
            [rows[0]],
            agency_map,
            {},
        ),
        "Missing vendor mapping",
    )

    # ---------------------------------
    # Test 7: Duplicate vendor invoice
    # ---------------------------------

    duplicate = {
        **rows[0],
        "Agency Name": "Cedar Staff LLC",
    }

    expect_error(
        lambda: build_vendor_bills(
            [rows[0], duplicate],
            agency_map,
            vendor_map,
        ),
        "Duplicate vendor invoice",
    )

    # ---------------------------------
    # Test 8: Missing invoice number
    # ---------------------------------

    expect_error(
        lambda: build_vendor_bills(
            [{
                **rows[0],
                "Vendor Invoice Number": "",
            }],
            agency_map,
            vendor_map,
        ),
        "Missing vendor invoice number",
    )

    print()
    print("ALL AP BILLING TESTS PASSED")


if __name__ == "__main__":
    main()
