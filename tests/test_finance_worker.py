import tempfile
import unittest
from pathlib import Path
from finance.worker import acknowledge, connect, cycle, demo, parse, process_one, reconcile, snapshot, submit

class FinanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def test_demo_reconciles_and_preserves_exceptions(self):
        demo(self.root)
        cycle(self.root)
        s=snapshot(self.root)
        self.assertEqual(s["counts"],{"batches":1,"queued":0,"open_exceptions":4})
        r=s["batches"][0]["report"]
        self.assertEqual(r["matched"],2)
        self.assertEqual(r["difference_cents"],175)
        self.assertEqual({f["kind"] for f in s["findings"]},{"duplicate_or_ambiguous_reference","date_or_amount_mismatch","missing_from_ledger","missing_from_bank"})
        self.assertTrue(s["last_cycle"])
    def test_restart_and_idempotency(self):
        folder=demo(self.root)
        key=submit(self.root,folder)
        self.assertEqual(snapshot(self.root)["counts"]["queued"],1)
        self.assertTrue(process_one(self.root))
        self.assertFalse(process_one(self.root))
        cycle(self.root)
        self.assertEqual(snapshot(self.root)["counts"]["batches"],1)
        self.assertEqual(submit(self.root,folder),key)
    def test_review_no_ledger_mutation(self):
        demo(self.root);cycle(self.root)
        s=snapshot(self.root)
        fid=s["findings"][0]["id"]
        acknowledge(self.root,fid,"Reviewed source evidence")
        after=snapshot(self.root)
        self.assertEqual(after["counts"]["open_exceptions"],3)
        self.assertEqual(s["batches"],after["batches"])
        self.assertEqual(after["activity"][0]["event"],"acknowledged")
        with self.assertRaises(ValueError):
            acknowledge(self.root,fid,"again")
    def test_bad_data_fails_closed(self):
        folder=demo(self.root)
        (folder/"bank.csv").write_bytes(b"reference,date,amount\nx,2026-11-20,NaN\n")
        cycle(self.root)
        s=snapshot(self.root)
        self.assertEqual(s["batches"][0]["state"],"failed")
        self.assertEqual(s["counts"]["open_exceptions"],0)
    def test_exact_amount_and_dates(self):
        for v in ["0.001","1e2","NaN","Infinity","1,000"]:
            with self.assertRaises(ValueError):
                parse(("reference,date,amount\nx,2026-11-20,"+v+"\n").encode())
        b=parse(b"reference,date,amount\nx,2026-11-20,0.10\n")
        l=parse(b"reference,date,amount\nx,2026-11-21,0.10\n")
        report,findings=reconcile(b,l)
        self.assertEqual(report["difference_cents"],0)
        self.assertEqual(report["matched"],0)
        self.assertEqual(len(findings),1)
    def test_unready_folder_is_ignored(self):
        f=self.root/"inbox"/"unfinished";f.mkdir(parents=True)
        cycle(self.root)
        self.assertEqual(snapshot(self.root)["counts"]["batches"],0)

if __name__=="__main__":
    unittest.main()
