import json
import tempfile
import unittest
from pathlib import Path
from finance.vision_operator import LocalVision,validate_choice,operation
from finance.engine import plan,snapshot
from datetime import date

class VisionTests(unittest.TestCase):
    def test_structured_model_call(self):
        seen=[]
        def request(path,body=None,timeout=45):
            if path=="/api/tags": return {"models":[{"name":"gemma3:4b"}]}
            seen.append(body)
            return {"done":True,"message":{"content":'{"action":"open_bank","reason":"Inspect statement"}'}}
        model=LocalVision(request=request)
        r=model.choose(b"fake screenshot",{"screen":"home"},{"open_bank":"Bank","stop":"Stop"})
        self.assertEqual(r["action"],"open_bank")
        self.assertEqual(seen[0]["model"],"gemma3:4b")
        self.assertTrue(seen[0]["messages"][1]["images"])
        self.assertEqual(seen[0]["format"]["properties"]["action"]["enum"],["open_bank","stop"])
    def test_invalid_model_action(self):
        for value in ['{"action":"post_fee","reason":"skip checks"}','{"action":"stop","action":"open_bank","reason":"duplicate"}','{"action":"stop","reason":"x","command":"bad"}']:
            with self.assertRaises(ValueError): validate_choice(value,{"stop":"Stop","open_bank":"Bank"})
    def test_missing_model_no_download(self):
        calls=[]
        def request(path,body=None,timeout=45):
            calls.append(path);return {"models":[]}
        with self.assertRaises(ValueError): LocalVision(request=request)
        self.assertEqual(calls,["/api/tags"])
    def test_vision_task_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);today=date(2026,11,25)
            plan(root,today)
            before={j["tool"]:j["id"] for j in snapshot(root)["jobs"] if j["active"]}
            plan(root,today,"gemma3:4b")
            after={j["tool"]:j["id"] for j in snapshot(root)["jobs"] if j["active"]}
            self.assertEqual(before["close_prepare"],after["close_prepare"])
            self.assertNotEqual(before["browser_execute"],after["browser_execute"])
            self.assertNotEqual(before["browser_verify"],after["browser_verify"])
    def test_browser_with_test_double(self):
        try: import playwright.sync_api
        except ImportError: self.skipTest("Optional browser runtime")
        class Chooser:
            model="test-double"
            def __init__(self): self.i=0
            def choose(self,shot,observation,options,timeout=45):
                # Deliberately inspect original ledger first, then bank.
                order=["open_ledger","export_before","open_bank","export_bank","open_adjust","enter_amount","enter_account","enter_day","enter_ref","post_fee","open_ledger","export_after","finish"]
                action=order[self.i];self.i+=1
                if not shot.startswith(b"\x89PNG"): raise AssertionError("Missing screenshot")
                if action not in options: raise AssertionError((action,options))
                return {"action":action,"reason":"Deterministic integration test only"}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result=operation(root,Chooser())
            self.assertEqual(result["steps"],13)
            self.assertEqual(result["model"],"test-double")
            self.assertTrue(result["verified"])
            self.assertEqual(result["state"],"needs_review")
            self.assertEqual(len(list((root/"vision_runs").glob("*/report.json"))),1)
