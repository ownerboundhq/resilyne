import tempfile
import unittest
from pathlib import Path
from finance.worker import snapshot

class OperationTests(unittest.TestCase):
    def test_practice_post_and_verify(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Optional desktop dependencies not installed")
        with sync_playwright() as p:
            if not Path(p.chromium.executable_path).exists():
                self.skipTest("Chromium not installed")
        from finance.operation import operation
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            result=operation(root,headless=True)
            self.assertEqual(result["before"]["exceptions"],2)
            self.assertEqual(result["after"]["exceptions"],1)
            self.assertEqual(result["after"]["difference_cents"],500)
            self.assertEqual(result["remaining"][0]["reference"],"BILL-001")
            self.assertEqual(result["journal"]["cents"],300)
            self.assertEqual(snapshot(root)["counts"]["open_exceptions"],1)
            run=next((root/"operations").iterdir())
            for f in ("01-before.png","02-adjustment.png","03-verified.png","report.json","ledger-before.csv","ledger-after.csv"):
                self.assertTrue((run/f).is_file(),f)
            repeat=operation(root,headless=True)
            self.assertEqual(repeat["batch_id"],result["batch_id"])
            self.assertEqual(snapshot(root)["counts"]["batches"],1)
