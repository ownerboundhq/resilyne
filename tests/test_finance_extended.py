import copy
import tempfile
import unittest
from datetime import date
from pathlib import Path
from finance.extended_finance import calculate,sample,receipt
from finance.intelligence import tick,period_rollup,verify

class ExtendedTests(unittest.TestCase):
    def test_accounting(self):
        r=calculate(sample("2026-10"))
        self.assertEqual(r["expense_categories_cents"],{"Office supplies":10000})
        self.assertTrue(r["card"]["reconciled"])
        self.assertEqual(r["loans"][0]["principal_paid_cents"],9000)
        self.assertEqual(r["loans"][0]["closing_cents"],91000)
        self.assertTrue(all(a["reconciled"] for a in r["related_parties"]))
        self.assertEqual(r["foreign_currency"][0]["signed_remeasurement_cents"],500)
        self.assertEqual(r["budget"][1]["favourable_variance_cents"],5000)
        self.assertEqual(len(r["tax_source_worksheets"]),2)
        self.assertTrue(verify(r)["passed"])
    def test_duplicate_and_mismatch(self):
        d=sample("2026-10")
        d["documents"].append(copy.deepcopy(d["documents"][0]))
        d["loans"][0]["gl_closing_cents"]+=1
        r=calculate(d)
        self.assertTrue(r["review_required"])
        self.assertFalse(verify(r)["passed"])
        self.assertEqual(len(r["documents"]),1)
    def test_missing_document_field(self):
        with self.assertRaises(ValueError): receipt("Invoice: X\nVendor: Y")
    def test_durable_and_compliance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);today=date(2026,11,25)
            a=tick(root,today);b=tick(root,today)
            self.assertEqual(a["state"],"prepared",a["error"])
            self.assertEqual(a["id"],b["id"])
            self.assertEqual(len(list((root/"backups").glob("*.sqlite3"))),1)
            self.assertEqual(a["report"]["compliance"]["status"],"not_ready_to_file")
            self.assertEqual(a["report"]["period_reports"]["year"]["state"],"blocked")
    def test_rollup_continuity(self):
        def row(period,opening,profit):
            report={"company":"Fictional","trial_balance":[{"id":"cash","type":"asset","opening_cents":opening,"net_cents":opening+profit},{"id":"equity","type":"equity","opening_cents":-opening,"net_cents":-opening}],
                    "income_statement":{"revenue_cents":profit,"expenses_cents":0,"net_income_cents":profit},"balance_sheet":{"assets_cents":opening+profit}}
            return {"period":period,"state":"sealed","id":period,"sealed_id":period,"report":report}
        rows=[row("2026-01",100,10),row("2026-02",110,20),row("2026-03",130,30)]
        p=["2026-01","2026-02","2026-03"]
        self.assertEqual(period_rollup(rows,p)["net_income_cents"],60)
        rows[1]["report"]["trial_balance"][0]["opening_cents"]+=1
        self.assertEqual(period_rollup(rows,p)["state"],"blocked")
