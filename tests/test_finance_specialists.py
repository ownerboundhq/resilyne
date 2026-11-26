import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from finance.month_end import demo,tick,latest,seal

class SpecialistTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.today=date(2026,11,25)
        self.period=demo(self.root,self.today,advanced=True)
        self.path=self.root/"month_end"/(self.period+".json")
    def tearDown(self): self.tmp.cleanup()
    def run_close(self):
        tick(self.root,self.today)
        return latest(self.root)[0]
    def change(self,fn):
        data=json.loads(self.path.read_text())
        fn(data)
        self.path.write_text(json.dumps(data))
    def test_advanced_totals_and_journals(self):
        r=self.run_close()
        self.assertEqual(r["state"],"ready",r["error"])
        s=r["report"]["specialists"]
        self.assertEqual(s["inventory"]["cogs_cents"],12400)
        self.assertEqual(s["inventory"]["closing_cents"],9600)
        self.assertEqual(s["payroll"]["net_pay_cents"],80000)
        self.assertEqual(sum(s["payroll"]["closing_by_component"].values()),21600)
        self.assertEqual(s["sales_tax"]["closing_cents"],21590)
        self.assertEqual(s["sales_tax"]["claimable_itc_cents"],7410)
        self.assertEqual(s["adjustments"]["accrued_cents"],15000)
        self.assertEqual(s["adjustments"]["prepaid_expense_cents"],10000)
        self.assertEqual(s["adjustments"]["depreciation_cents"],1000)
        self.assertEqual(len(s["adjustments"]["generated_journals"]),4)
        self.assertEqual(r["report"]["income_statement"]["net_income_cents"],125000)
        self.assertEqual(r["report"]["balance_sheet"]["assets_cents"],927600)
        self.assertEqual(r["report"]["balance_sheet"]["liabilities_cents"],122600)
        self.assertEqual(r["report"]["balance_sheet"]["total_equity_cents"],805000)
        seal(self.root,self.period,r["id"])
        self.assertEqual(self.run_close()["state"],"sealed")
    def test_inventory_count_mismatch_blocks(self):
        self.change(lambda d:d["specialists"]["inventory"]["items"][0].update(physical_units=7))
        r=self.run_close()
        self.assertEqual(r["state"],"blocked")
        self.assertIn("Physical inventory",r["error"])
    def test_payroll_mismatch_blocks(self):
        self.change(lambda d:d["specialists"]["payroll"]["runs"][0].update(employee_cpp_cents=6001))
        self.assertIn("Payroll",self.run_close()["error"])
    def test_tax_mismatch_blocks(self):
        self.change(lambda d:d["specialists"]["sales_tax"]["lines"][0].update(rate_bps=1200))
        self.assertIn("GST/HST",self.run_close()["error"])
    def test_prepaid_mismatch_blocks(self):
        self.change(lambda d:d["specialists"]["prepaids"][0].update(elapsed_months=1))
        self.assertIn("Prepaid",self.run_close()["error"])
    def test_depreciation_mismatch_blocks(self):
        self.change(lambda d:d["specialists"]["depreciation"][0].update(elapsed_months=11))
        self.assertIn("Fixed asset",self.run_close()["error"])
    def test_missing_register_blocks(self):
        self.change(lambda d:d["specialists"].pop("payroll"))
        self.assertEqual(self.run_close()["state"],"blocked")
    def test_no_double_post(self):
        self.change(lambda d:d["journal"].append({"id":"NV-CLOSE-COGS","date":self.period+"-01","evidence":"prior","lines":[{"account":"cogs","debit_cents":12400,"credit_cents":0},{"account":"inventory","debit_cents":0,"credit_cents":12400}]}))
        self.assertIn("reserved",self.run_close()["error"])
