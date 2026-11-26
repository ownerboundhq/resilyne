import tempfile
import unittest
from pathlib import Path
from datetime import date
from finance.autonomy import tick
from finance import month_end

class AutonomyTests(unittest.TestCase):
    def test_restart_idempotency_and_block_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            calls=[]
            def browser(path):
                calls.append(path);return {"before":2,"after":1}
            today=date(2026,11,25)
            first=tick(root,today,browser,1000)
            self.assertEqual(first["month_end"]["state"],"completed")
            self.assertEqual(first["browser"]["state"],"needs_review")
            self.assertEqual(month_end.latest(root)[0]["state"],"sealed")
            files=list((root/"reports").glob("*.json"))
            self.assertEqual(len(files),1)
            old=files[0].read_bytes()
            tick(root,today,browser,1001)
            self.assertEqual(len(calls),1)
            self.assertEqual(files[0].read_bytes(),old)
            source=root/"month_end"/"2026-10.json"
            source.write_bytes(source.read_bytes()+b" ")
            result=tick(root,today,browser,1002)
            self.assertEqual(result["month_end"]["state"],"blocked")
            self.assertEqual(files[0].read_bytes(),old)
    def test_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def fail(path): raise RuntimeError("fixture")
            def ok(path): return {"before":2,"after":1}
            a=tick(root,date(2026,11,25),fail,1000)
            self.assertEqual(a["browser"]["state"],"retry")
            b=tick(root,date(2026,11,25),ok,1121)
            self.assertEqual(b["browser"]["state"],"needs_review")
