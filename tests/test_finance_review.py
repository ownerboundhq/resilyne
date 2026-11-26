import json
import tempfile
import unittest
from pathlib import Path
from datetime import date
from finance import month_end,office
from finance.computer_use import journal_rows
from finance.worker import cycle

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_close_reversion_and_stale_report(self):
        p=month_end.demo(self.root,advanced=True)
        path=self.root/"month_end"/(p+".json")
        original=path.read_bytes()
        month_end.tick(self.root)
        ready=month_end.latest(self.root)[0]
        data=json.loads(original)
        data["bank"]["closing_cents"]-=1
        path.write_text(json.dumps(data))
        self.assertEqual(month_end.latest(self.root)[0]["state"],"pending_recheck")
        month_end.tick(self.root)
        self.assertEqual(month_end.latest(self.root)[0]["state"],"blocked")
        path.write_bytes(original)
        month_end.tick(self.root)
        self.assertEqual(month_end.latest(self.root)[0]["id"],ready["id"])
        self.assertEqual(month_end.latest(self.root)[0]["state"],"ready")
        month_end.seal(self.root,p,ready["id"])
        path.unlink()
        self.assertEqual(month_end.latest(self.root)[0]["state"],"source_unavailable")
    def test_plan_linked_and_seal_blocks_execution(self):
        p=month_end.demo(self.root,advanced=True)
        cycle(self.root)
        key,period,entries=month_end.current_plan(self.root)
        self.assertEqual(period,p)
        self.assertEqual(journal_rows(entries)[0],("cogs","inventory","124.00"))
        month_end.seal(self.root,p,key)
        with self.assertRaises(ValueError): month_end.current_plan(self.root)
    def test_missing_specialist_field_blocks_but_other_module_runs(self):
        p=month_end.demo(self.root,advanced=True)
        path=self.root/"month_end"/(p+".json")
        data=json.loads(path.read_text())
        del data["specialists"]["inventory"]["items"][0]["sku"]
        path.write_text(json.dumps(data))
        office.demo(self.root)
        cycle(self.root)
        self.assertEqual(month_end.latest(self.root)[0]["state"],"blocked")
        self.assertEqual(office.latest(self.root)["state"],"complete")
    def test_office_current_source(self):
        path=office.demo(self.root)
        original=path.read_bytes()
        office.tick(self.root)
        data=json.loads(original);data["cash_cents"]+=1
        path.write_text(json.dumps(data))
        self.assertEqual(office.latest(self.root)["state"],"pending_recheck")
        office.tick(self.root)
        self.assertEqual(office.latest(self.root)["report"]["treasury"]["snapshot_cash_cents"],500001)
        path.write_bytes(original)
        office.tick(self.root)
        self.assertEqual(office.latest(self.root)["report"]["treasury"]["snapshot_cash_cents"],500000)
        path.unlink()
        self.assertEqual(office.latest(self.root)["state"],"source_unavailable")
