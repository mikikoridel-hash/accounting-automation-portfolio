
"""Test weekly batch accumulation and safety controls."""

import csv
import unittest
import tempfile

from pathlib import Path
from decimal import Decimal
from unittest.mock import patch

import WeeklyBatch as batch


def make_header(number, expected):
    return {
        "Invoice Number": number,
        "Invoice Date": "2026-11-09",
        "Customer ID": "1001",
        "Facility": "Pineview Medical",
        "Terms": "Net 14",
        "WEO": "2026-10-17",
        "Service Date Range": "10/11/2026 - 10/17/2026",
        "Line Date": "2026-10-17",
        "Expected Total": str(expected),
    }


def make_rows(reg_amount, ot_amount="0.00"):
    return [{
        "Unit": "Med-Surg",
        "REG Hours": "8",
        "REG Amount": str(reg_amount),
        "OT Hours": "4" if Decimal(ot_amount) else "0",
        "OT Amount": str(ot_amount),
        "DT Hours": "0",
        "DT Amount": "0.00",
        "Additional Amount": "0.00",
        "REG Item": "350",
        "OT Item": "351",
        "DT Item": "352",
        "Additional Item": "900",
    }]


class WeeklyBatchTests(unittest.TestCase):

    def test_weekly_batch(self):

        with tempfile.TemporaryDirectory() as folder:

            output = Path(folder)

            with patch.object(batch, "OUT", output):

                path = output / "WeeklyBatch_2026-11-09.csv"

                def read_batch():
                    with path.open(
                        newline="", encoding="utf-8"
                    ) as f:
                        return list(csv.DictReader(f))

                def invoice_count():
                    return len({
                        r["Invoice Number"]
                        for r in read_batch()
                    })

                def total():
                    return sum(
                        (Decimal(r["Amount"])
                         for r in read_batch()),
                        Decimal("0.00"),
                    )

                h1 = make_header("DEMO-PV10001", "2074.00")
                h2 = make_header("DEMO-PV10002", "1500.00")
                h3 = make_header("DEMO-PV10003", "1200.00")

                print("\n=== STEP 1: FIRST INVOICE ===")

                self.assertTrue(batch.add_invoice(
                    h1, make_rows("1400.00", "674.00")
                ))

                self.assertEqual(invoice_count(), 1)
                self.assertEqual(total(), Decimal("2074.00"))

                print("\n=== STEP 2: SECOND INVOICE ===")

                self.assertTrue(batch.add_invoice(
                    h2, make_rows("1000.00", "500.00")
                ))

                self.assertEqual(invoice_count(), 2)
                self.assertEqual(total(), Decimal("3574.00"))

                print("\n=== STEP 3: WRONG AMOUNT ===")

                before = path.read_bytes()

                self.assertFalse(batch.add_invoice(
                    h3, make_rows("800.00", "500.00")
                ))

                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(invoice_count(), 2)
                self.assertEqual(total(), Decimal("3574.00"))

                print("\n=== STEP 4: CORRECTED INVOICE ===")

                self.assertTrue(batch.add_invoice(
                    h3, make_rows("800.00", "400.00")
                ))

                self.assertEqual(invoice_count(), 3)
                self.assertEqual(total(), Decimal("4774.00"))

                print("\n=== STEP 5: DUPLICATE EXPORT ===")

                before = path.read_bytes()

                self.assertFalse(batch.add_invoice(
                    h3, make_rows("800.00", "400.00")
                ))

                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(invoice_count(), 3)

                print("\n=== STEP 6: EXPLICIT REPLACEMENT ===")

                corrected = make_header(
                    "DEMO-PV10003", "1250.00"
                )

                self.assertTrue(batch.add_invoice(
                    corrected,
                    make_rows("800.00", "450.00"),
                    replace=True,
                ))

                self.assertEqual(invoice_count(), 3)
                self.assertEqual(total(), Decimal("4824.00"))

                print("\n=== ALL BATCH CHECKS PASSED ===")


if __name__ == "__main__":
    unittest.main(verbosity=2)
