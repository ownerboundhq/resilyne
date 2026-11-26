import csv
import tempfile
import unittest
from pathlib import Path
from finance.computer_use import COLORS,locate,expected_journals,verify_saved

class ComputerUseTests(unittest.TestCase):
    def test_calculated_journal_plan(self):
        self.assertEqual(expected_journals(),[("cogs","inventory","124.00"),("accrual_exp","accrual","150.00"),("prepaid_exp","prepaid","100.00"),("dep_exp","accum_dep","10.00")])
    def test_screen_marker_and_ambiguity(self):
        try:
            from PIL import Image,ImageDraw
        except ImportError:
            self.skipTest("Optional Pillow dependency")
        image=Image.new("RGB",(400,200),"white")
        draw=ImageDraw.Draw(image)
        draw.rectangle((20,30,160,70),outline=COLORS[0],width=4)
        self.assertEqual(locate(image,COLORS[0]),(90,50))
        with self.assertRaises(RuntimeError): locate(image,COLORS[1])
        draw.rectangle((180,100,320,140),outline=COLORS[0],width=4)
        with self.assertRaises(RuntimeError): locate(image,COLORS[0])
    def test_readback_rejects_changed_amount(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"posted.csv"
            expected=expected_journals()
            with path.open("w",encoding="utf-8",newline="") as f:
                w=csv.writer(f);w.writerow(["debit_account","credit_account","amount_cad"]);w.writerows(expected)
            self.assertTrue(verify_saved(path,expected))
            path.write_text(path.read_text().replace("124.00","125.00"))
            with self.assertRaises(RuntimeError): verify_saved(path,expected)
