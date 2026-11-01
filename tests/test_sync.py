"""bin/sync.py: several computers on one map. Run: python3 -m unittest discover -s tests -p 'test_*.py'"""
import json
import os
import sys
import tempfile
import time
import unittest

ROOT = tempfile.mkdtemp(prefix="qosmopol-test-")
os.environ["HOME"] = os.path.join(ROOT, "home")  # never the owner's own ~/.qosmopol
os.environ["USERPROFILE"] = os.environ["HOME"]
os.environ.pop("QOSMOPOL_SYNC_DIR", None)
os.makedirs(os.environ["HOME"])
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import sync  # noqa: E402

ROW = {"id": "local_aaa", "acc": "A", "title": "Ship the level", "proj": "Space Game", "cwd": "/Users/me/Space Game",
       "last": 1, "seen": 0, "created": 0, "turns": 3, "star": False, "cat": "blocked", "need": "which ending?",
       "detail": "", "sumId": "s1", "error": False, "busy": False, "ask": False, "model": "", "effort": "", "mode": "",
       "bridge": "session_01x", "home": True}


class Sync(unittest.TestCase):
    def setUp(self):
        self.shared = tempfile.mkdtemp(dir=ROOT)
        self.assertEqual(sync.configure(self.shared), "")
        sync._last.update(body=None, at=0.0)

    def tearDown(self):
        sync.configure("")

    def other(self, name="Windows", at=None, sessions=None, device="d2"):
        path = os.path.join(self.shared, "Qosmopol", "cihazlar", f"{device}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"v": 1, "device": device, "name": name, "at": int((at or time.time()) * 1000), "os": "win32",
                       "sessions": sessions if sessions is not None else [dict(ROW, id="local_bbb", proj="Projects")]}, f)

    def test_off_until_a_folder_is_picked(self):
        sync.configure("")
        self.assertIsNone(sync.folder())
        self.assertFalse(sync.publish([ROW]))
        self.assertEqual(sync.peers(), ([], []))

    def test_a_missing_folder_is_refused(self):
        self.assertEqual(sync.configure(os.path.join(ROOT, "nope")), "folder not found")

    def test_publish_writes_only_this_computers_sessions_without_paths(self):
        self.assertTrue(sync.publish([ROW, dict(ROW, id="local_far", remote=True)]))
        me = sync.device()["id"]
        d = json.load(open(os.path.join(self.shared, "Qosmopol", "cihazlar", f"{me}.json"), encoding="utf-8"))
        self.assertEqual([k["id"] for k in d["sessions"]], ["local_aaa"])
        self.assertNotIn("cwd", d["sessions"][0])
        self.assertNotIn("home", d["sessions"][0])
        self.assertEqual(d["sessions"][0]["bridge"], "session_01x")

    def test_unchanged_summary_waits_for_the_heartbeat(self):
        t = 1000.0
        self.assertTrue(sync.publish([ROW], now=t))
        self.assertFalse(sync.publish([ROW], now=t + 10))
        self.assertTrue(sync.publish([ROW], now=t + sync.HEARTBEAT + 1))
        self.assertTrue(sync.publish([dict(ROW, cat="completed")], now=t + sync.HEARTBEAT + 2))

    def test_peers_skip_this_computer_and_name_the_other(self):
        sync.publish([ROW])
        self.other()
        devices, rows = sync.peers()
        self.assertEqual([d["name"] for d in devices], ["Windows"])
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["id"], r["proj"], r["remote"], r["devName"], r["cwd"], r["home"]),
                         ("local_bbb", "Projects · Windows", True, "Windows", "", False))
        self.assertFalse(r["stale"])

    def test_a_silent_computer_is_offline_and_not_working(self):
        self.other(at=time.time() - sync.STALE - 5, sessions=[dict(ROW, id="local_ccc", busy=True)])
        devices, rows = sync.peers()
        self.assertTrue(devices[0]["stale"])
        self.assertFalse(rows[0]["busy"])

    def test_broken_or_foreign_files_are_ignored(self):
        d = os.path.join(self.shared, "Qosmopol", "cihazlar")
        with open(os.path.join(d, "broken.json"), "w") as f:
            f.write("{not json")
        self.other(device="d3", sessions=[{"id": "../../etc"}, "x", dict(ROW, id="local_ok")])
        devices, rows = sync.peers()
        self.assertEqual([r["id"] for r in rows], ["local_ok"])

    def test_rename(self):
        self.assertEqual(sync.configure(name="  Office   PC "), "")
        self.assertEqual(sync.device()["name"], "Office PC")
        self.assertEqual(sync.configure(name="   "), "empty name")


if __name__ == "__main__":
    unittest.main()
