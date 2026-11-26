import tempfile
import unittest
from pathlib import Path
from datetime import date
from finance.engine import tick,plan,claim,finish,snapshot,verify_close
from finance.worker import demo,submit,cycle,connect
from finance import month_end
from contextlib import closing

TODAY=date(2026,11,25)

def fixture_browser(root):
    folder=root/"inbox"/"engine-verified"
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"bank.csv").write_text("reference,date,amount\nPAY-001,2026-11-24,120.00\nFEE-001,2026-11-24,-3.00\nBILL-001,2026-11-24,-50.00\n")
    (folder/"ledger.csv").write_text("reference,date,amount\nPAY-001,2026-11-24,120.00\nFEE-001,2026-11-24,-3.00\nBILL-001,2026-11-24,-55.00\n")
    (folder/"READY").touch()
    key=submit(root,folder);cycle(root)
    return {"batch_id":key,"before":2,"after":1}

class EngineTests(unittest.TestCase):
    def test_plan_execute_verify_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);calls=[]
            def browser(r): calls.append(r);return fixture_browser(r)
            first=tick(root,TODAY,browser,clock=lambda:1000)
            self.assertEqual(first["counts"]["completed"],8,first)
            self.assertEqual(first["counts"]["needs_review"],1)
            self.assertEqual(month_end.latest(root)[0]["state"],"sealed")
            second=tick(root,TODAY,browser,clock=lambda:1001)
            self.assertEqual(first["counts"],second["counts"])
            self.assertEqual(len(calls),1)
            self.assertEqual(len(second["jobs"]),9)
    def test_changed_source_cannot_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            plan(root,TODAY)
            path=root/"month_end"/"2026-10.json"
            path.write_bytes(path.read_bytes()+b" ")
            result=tick(root,TODAY,fixture_browser,clock=lambda:1000)
            jobs={r["tool"]:r for r in result["jobs"] if r["active"]}
            self.assertEqual(jobs["close_prepare"]["state"],"blocked")
            self.assertEqual(jobs["close_seal"]["state"],"blocked")
            self.assertFalse(any(r["state"]=="sealed" for r in month_end.latest(root)))
    def test_claim_lease_recovery_and_stale_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan(root,TODAY)
            first=claim(root,1000)
            self.assertIsNone(claim(root,1001))
            second=claim(root,1301)
            self.assertEqual(first["id"],second["id"])
            self.assertEqual(second["attempts"],2)
            self.assertFalse(finish(root,first,"completed",{},at=1302))
            self.assertTrue(finish(root,second,"completed",{},at=1302))
    def test_no_evidence_no_verified_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            result=tick(root,TODAY,lambda r:{"batch_id":"fake","before":2,"after":1},clock=lambda:1000)
            jobs={r["tool"]:r for r in result["jobs"] if r["active"]}
            self.assertEqual(jobs["browser_verify"]["state"],"blocked")
            self.assertEqual(jobs["close_seal"]["state"],"completed")
    def test_verify_rejects_wrong_amount(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);month_end.demo(root,TODAY,advanced=True);month_end.tick(root,TODAY)
            r=month_end.latest(root)[0]["report"]
            verify_close(r)
            r["income_statement"]["revenue_cents"]+=1
            with self.assertRaises(ValueError): verify_close(r)
