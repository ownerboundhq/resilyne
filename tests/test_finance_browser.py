import tempfile
import unittest
from pathlib import Path
from finance.worker import snapshot

class BrowserPilotTests(unittest.TestCase):
    def test_browser_fixture_exports_and_reconciles(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Optional desktop dependencies not installed")
        with sync_playwright() as p:
            if not Path(p.chromium.executable_path).exists():
                self.skipTest("Chromium not installed")
        from finance.browser_pilot import browser_pilot
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            key=browser_pilot(root,headless=True)
            s=snapshot(root)
            self.assertEqual(s["counts"]["batches"],1)
            self.assertEqual(s["counts"]["open_exceptions"],2)
            report=s["batches"][0]["report"]
            self.assertEqual(report["matched"],1)
            self.assertEqual(report["difference_cents"],200)
            self.assertEqual(s["batches"][0]["id"],key)
            self.assertIn("browser_export",{x["event"] for x in s["activity"]})
            self.assertEqual(browser_pilot(root,headless=True),key)
            self.assertEqual(snapshot(root)["counts"]["batches"],1)
