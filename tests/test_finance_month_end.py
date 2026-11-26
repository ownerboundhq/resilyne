import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from finance.month_end import demo,tick,latest,seal
from finance.worker import cycle,snapshot

class MonthEndTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.today=date(2026,11,25)
    def tearDown(self): self.temp.cleanup()
    def test_complete_and_seal(self):
        period=demo(self.root,self.today)
        tick(self.root,self.today)
        r=latest(self.root)[0]
        self.assertEqual(r["state"],"ready")
        self.assertTrue(all(g["passed"] for g in r["report"]["gates"]))
        self.assertEqual(r["report"]["income_statement"]["net_income_cents"],275000)
        self.assertEqual(r["report"]["balance_sheet"]["assets_cents"],820000)
        self.assertEqual(r["report"]["balance_sheet"]["liabilities_cents"],45000)
        self.assertEqual(r["report"]["balance_sheet"]["total_equity_cents"],775000)
        seal(self.root,period,r["id"])
        tick(self.root,self.today)
        self.assertEqual(latest(self.root)[0]["state"],"sealed")
        path=self.root/"month_end"/(period+".json")
        path.write_text(path.read_text()+" ")
        tick(self.root,self.today)
        self.assertEqual(latest(self.root)[0]["state"],"sealed_conflict")
        self.assertEqual(latest(self.root)[0]["sealed_id"],r["id"])
    def test_bank_mismatch_blocks(self):
        period=demo(self.root,self.today,blocked=True)
        tick(self.root,self.today)
        r=latest(self.root)[0]
        self.assertEqual(r["state"],"blocked")
        self.assertFalse(next(g for g in r["report"]["gates"] if g["name"]=="Bank reconciliation")["passed"])
        with self.assertRaises(ValueError): seal(self.root,period,r["id"])
    def test_missing_checks_and_ar_block(self):
        period=demo(self.root,self.today)
        path=self.root/"month_end"/(period+".json")
        data=json.loads(path.read_text())
        del data["checks"]["payroll"]
        data["receivables"][0]["open_cents"]-=1
        path.write_text(json.dumps(data))
        tick(self.root,self.today)
        r=latest(self.root)[0]
        self.assertEqual(r["state"],"blocked")
        self.assertFalse(next(g for g in r["report"]["gates"] if g["name"]=="payroll")["passed"])
        self.assertFalse(next(g for g in r["report"]["gates"] if g["name"]=="AR control account")["passed"])
    def test_stale_approval_rejected(self):
        period=demo(self.root,self.today)
        tick(self.root,self.today)
        r=latest(self.root)[0]
        path=self.root/"month_end"/(period+".json")
        path.write_text(path.read_text()+" ")
        with self.assertRaises(ValueError): seal(self.root,period,r["id"])
    def test_worker_prepares_automatically(self):
        demo(self.root)
        cycle(self.root)
        self.assertEqual(snapshot(self.root)["month_end"][0]["state"],"ready")
    def test_unbalanced_entry_rejected(self):
        period=demo(self.root,self.today)
        path=self.root/"month_end"/(period+".json")
        data=json.loads(path.read_text())
        data["journal"][0]["lines"][0]["debit_cents"]+=1
        path.write_text(json.dumps(data))
        tick(self.root,self.today)
        r=latest(self.root)[0]
        self.assertEqual(r["state"],"blocked")
        self.assertIn("Unbalanced",r["error"])
