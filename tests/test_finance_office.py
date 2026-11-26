import tempfile
import unittest
import json
from pathlib import Path
from datetime import date,timedelta
from finance.office import demo,tick,latest
from finance.schedule import claim,finish
from finance.worker import cycle,snapshot

class OfficeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.today=date(2026,11,25)
    def tearDown(self):
        self.tmp.cleanup()
    def test_reports_and_daily_refresh(self):
        demo(self.root,self.today)
        k=tick(self.root,self.today)
        r=latest(self.root)["report"]
        self.assertEqual(r["accountant"]["total_debit_cents"],500000)
        self.assertEqual(r["accountant"]["total_credit_cents"],500000)
        self.assertEqual(r["receivables"]["buckets"]["1_30"],120000)
        self.assertEqual(r["payables"]["total_cents"],45000)
        self.assertEqual(r["treasury"]["illustrative_ending_cash_cents"],575000)
        self.assertEqual(tick(self.root,self.today),k)
        self.assertNotEqual(tick(self.root,self.today+timedelta(days=1)),k)
        self.assertEqual(latest(self.root)["report"]["stale_days"],1)
    def test_unbalanced_fails_closed(self):
        path=demo(self.root,self.today)
        data=json.loads(path.read_text())
        data["journal"][0]["lines"][0]["debit_cents"]+=1
        path.write_text(json.dumps(data))
        tick(self.root,self.today)
        self.assertEqual(latest(self.root)["state"],"failed")
        self.assertIsNone(latest(self.root)["report"])
    def test_worker_picks_up_snapshot(self):
        demo(self.root)
        cycle(self.root)
        self.assertEqual(snapshot(self.root)["office"]["state"],"complete")
    def test_schedule_lease_retry_and_recovery(self):
        a=claim(self.root,"test",1000)
        self.assertTrue(a)
        self.assertIsNone(claim(self.root,"test",1001))
        b=claim(self.root,"test",1181)
        self.assertTrue(b)
        self.assertFalse(finish(self.root,"test",a,1182,True,"old"))
        self.assertTrue(finish(self.root,"test",b,1183,False,"failed"))
        self.assertIsNone(claim(self.root,"test",1302))
        c=claim(self.root,"test",1303)
        self.assertTrue(c)
        self.assertTrue(finish(self.root,"test",c,1304,True,"done"))
        self.assertIsNone(claim(self.root,"test",1603))
        self.assertTrue(claim(self.root,"test",1604))
