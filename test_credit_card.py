
import csv
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import CreditCard as cc


class TestCreditCard(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.root = Path(self.temp.name)
        self.data = self.root / "credit-card"
        self.output = self.root / "cc-output"

        shutil.copytree(cc.DATA, self.data)

        self.data_patch = patch.object(
            cc, "DATA", self.data
        )
        self.output_patch = patch.object(
            cc, "OUTPUT", self.output
        )

        self.data_patch.start()
        self.output_patch.start()

        self.addCleanup(self.data_patch.stop)
        self.addCleanup(self.output_patch.stop)

    def append_transaction(self, filename, row):
        path = self.data / filename

        with path.open(
            "a", encoding="utf-8", newline=""
        ) as file:
            writer = csv.writer(file)
            writer.writerow(row)

    def process_a(self):
        return cc.process_account(
            self.data / "AMEX_Account_A.csv",
            "DEMO-1001",
            cc.load_vendor_map(),
            cc.load_card_map(),
        )

    def process_b(self):
        return cc.process_account(
            self.data / "AMEX_Account_B.csv",
            "DEMO-2002",
            cc.load_vendor_map(),
            cc.load_card_map(),
        )

    def test_account_a_reconciliation(self):
        result = self.process_a()
        summary = result["summary"]

        self.assertTrue(result["passed"])
        self.assertEqual(summary["Raw Count"], 6)
        self.assertEqual(summary["Import Count"], 4)
        self.assertEqual(summary["Manual Count"], 2)

        self.assertEqual(
            Decimal(summary["Raw Total"]),
            Decimal("-304.52"),
        )

        self.assertEqual(
            Decimal(summary["Import Total"]),
            Decimal("220.48"),
        )

        self.assertEqual(
            Decimal(summary["Manual Total"]),
            Decimal("-525.00"),
        )

        self.assertEqual(
            Decimal(summary["Difference"]),
            Decimal("0.00"),
        )

    def test_account_b_reconciliation(self):
        result = self.process_b()
        summary = result["summary"]

        self.assertTrue(result["passed"])
        self.assertEqual(summary["Raw Count"], 6)
        self.assertEqual(summary["Import Count"], 4)
        self.assertEqual(summary["Manual Count"], 2)

        self.assertEqual(
            Decimal(summary["Import Total"]),
            Decimal("377.24"),
        )

        self.assertEqual(
            Decimal(summary["Manual Total"]),
            Decimal("-380.00"),
        )

        self.assertEqual(
            Decimal(summary["Raw Total"]),
            Decimal("-2.76"),
        )

        self.assertEqual(
            Decimal(summary["Difference"]),
            Decimal("0.00"),
        )

    def test_payment_and_refund_excluded(self):
        result = self.process_a()

        reasons = [
            row["Reason"]
            for row in result["manual"]
        ]

        self.assertIn("Payment", reasons)
        self.assertIn("Refund / Credit", reasons)

        for row in result["export"]:
            self.assertNotIn(
                "PAYMENT",
                row["Line Description"].upper(),
            )

            self.assertGreaterEqual(
                Decimal(row["Amount"]),
                Decimal("0.00"),
            )

    def test_multiple_cardholders(self):
        result = self.process_a()

        cardholders = {
            row["Memo"]
            for row in result["export"]
        }

        account_ids = {
            row["Credit Card Acct Internal ID"]
            for row in result["export"]
        }

        self.assertEqual(
            cardholders,
            {
                "DEMO CARDHOLDER A1",
                "DEMO CARDHOLDER A2",
            },
        )

        self.assertEqual(account_ids, {"2201"})

    def test_separate_card_accounts(self):
        result_a = self.process_a()
        result_b = self.process_b()

        self.assertTrue(all(
            row["Credit Card Acct Internal ID"]
            == "2201"
            for row in result_a["export"]
        ))

        self.assertTrue(all(
            row["Credit Card Acct Internal ID"]
            == "2202"
            for row in result_b["export"]
        ))

    def test_vendor_mapping(self):
        result = self.process_a()

        office_rows = [
            row for row in result["export"]
            if "OFFICE MART" in row["Line Description"]
        ]

        self.assertEqual(len(office_rows), 1)

        self.assertEqual(
            office_rows[0]["Vendor Internal ID"],
            "9102",
        )

        self.assertEqual(
            office_rows[0]["Expense Acct Internal ID"],
            "6102",
        )

    def test_missing_vendor_blocks_import(self):
        # Create successful exports first.
        cc.main()

        self.assertTrue(
            (self.output / "AMEX_A_Import.csv")
            .exists()
        )

        # Add an unmapped vendor.
        self.append_transaction(
            "AMEX_Account_A.csv",
            [
                "09/20/2026",
                "",
                "NEW DEMO VENDOR CA",
                "DEMO CARDHOLDER A1",
                "DEMO-1001",
                "42.00",
            ],
        )

        result = self.process_a()

        self.assertFalse(result["passed"])

        self.assertEqual(
            len(result["missing"]), 1
        )

        self.assertEqual(
            result["missing"][0]["Reason"],
            "Missing Vendor Key",
        )

        self.assertEqual(
            Decimal(result["summary"]["Difference"]),
            Decimal("0.00"),
        )

        # Neither account may release an import file.
        with self.assertRaises(SystemExit):
            cc.main()

        self.assertFalse(
            (self.output / "AMEX_A_Import.csv")
            .exists()
        )

        self.assertFalse(
            (self.output / "AMEX_B_Import.csv")
            .exists()
        )

        self.assertTrue(
            (self.output / "MissingVendor_QC.csv")
            .exists()
        )

        # Accounting adds the missing mapping.
        with (
            self.data / "VendorMap.csv"
        ).open(
            "a", encoding="utf-8", newline=""
        ) as file:
            writer = csv.writer(file)

            writer.writerow([
                "NEW DEMO VENDOR",
                "New Demo Vendor",
                "9199",
                "6199",
                "Demo Business Expense",
            ])

        # The corrected batch can now pass.
        cc.main()

        self.assertTrue(
            (self.output / "AMEX_A_Import.csv")
            .exists()
        )

        self.assertTrue(
            (self.output / "AMEX_B_Import.csv")
            .exists()
        )

        corrected = self.process_a()

        self.assertTrue(corrected["passed"])

        self.assertEqual(
            corrected["summary"]["Import Count"],
            5,
        )

        self.assertEqual(
            Decimal(
                corrected["summary"]["Import Total"]
            ),
            Decimal("262.48"),
        )

    def test_unique_references(self):
        self.append_transaction(
            "AMEX_Account_A.csv",
            [
                "09/01/2026",
                "",
                "CITY PARKING DEMO CA",
                "DEMO CARDHOLDER A2",
                "DEMO-1001",
                "10.00",
            ],
        )

        result_a = self.process_a()
        result_b = self.process_b()

        references = [
            row["Reference #"]
            for row in (
                result_a["export"]
                + result_b["export"]
            )
        ]

        self.assertEqual(
            len(references),
            len(set(references)),
        )

        self.assertIn(
            "AMEX-A-20260901-001",
            references,
        )

        self.assertIn(
            "AMEX-A-20260901-002",
            references,
        )

    def test_wrong_card_account_rejected(self):
        self.append_transaction(
            "AMEX_Account_A.csv",
            [
                "09/20/2026",
                "",
                "OFFICE MART DEMO CA",
                "DEMO CARDHOLDER B",
                "DEMO-2002",
                "50.00",
            ],
        )

        with self.assertRaises(ValueError):
            self.process_a()

    def test_successful_export_files(self):
        cc.main()

        expected_files = [
            "AMEX_A_Import.csv",
            "AMEX_B_Import.csv",
            "MissingVendor_QC.csv",
            "ManualEntry_Review.csv",
            "CC_Reconciliation.csv",
        ]

        for filename in expected_files:
            self.assertTrue(
                (self.output / filename).exists()
            )

        manual = cc.read_csv(
            self.output / "ManualEntry_Review.csv"
        )

        missing = cc.read_csv(
            self.output / "MissingVendor_QC.csv"
        )

        self.assertEqual(len(manual), 4)
        self.assertEqual(len(missing), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
