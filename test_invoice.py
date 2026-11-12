
"""Tests for Phase 2 invoice selection."""
import unittest

from InvoiceTool import extract


def row(shift, agency, tab, facility="Pineview Medical",
        weo="2026-10-17", status="OK"):
    return {
        "SourceFile": f"WEO_{weo}.xlsx",
        "SourceTab": tab,
        "Shift ID": shift,
        "Facility Standard": facility,
        "Agency Standard": agency,
        "Mapping Status": status,
        "Calculated Total": "100.00",
    }


class InvoiceTests(unittest.TestCase):

    def setUp(self):
        self.rows = [
            row("S1", "Cedar Staffing", "Original"),
            row("S2", "Cedar Staffing", "Original"),
            row("S3", "Harbor Clinical", "Original"),
            row("S4", "Cedar Staffing", "COR"),
            row("S5", "Cedar Staffing", "Original",
                facility="Lakebend Care"),
            row("S6", "Cedar Staffing", "Original",
                weo="2026-10-24"),
        ]

    def test_agency_selection(self):
        result = extract(
            self.rows, "2026-10-17",
            "Pineview Medical", ["Cedar Staffing"],
        )
        self.assertEqual(
            [r["Shift ID"] for r in result],
            ["S1", "S2", "S4"],
        )

    def test_multiple_agencies(self):
        result = extract(
            self.rows, "2026-10-17",
            "Pineview Medical",
            ["Cedar Staffing", "Harbor Clinical"],
        )
        self.assertEqual(len(result), 4)

    def test_correction_only(self):
        result = extract(
            self.rows, "2026-10-17",
            "Pineview Medical", ["Cedar Staffing"],
            ["COR"],
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Shift ID"], "S4")

    def test_missing_agency(self):
        with self.assertRaises(ValueError):
            extract(
                self.rows, "2026-10-17",
                "Pineview Medical", ["Unknown Agency"],
            )

    def test_mapping_qc(self):
        bad_rows = [
            row("S7", "", "Original", status="REVIEW")
        ]
        with self.assertRaises(ValueError):
            extract(
                bad_rows, "2026-10-17",
                "Pineview Medical", ["Cedar Staffing"],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
