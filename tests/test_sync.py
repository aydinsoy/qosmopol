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
        for f in (sync.GROUPS,):
            if os.path.exists(f):
                os.remove(f)
        sync._peer_groups.update(at=0, rules={})
        self.shared = tempfile.mkdtemp(dir=ROOT)
        self.assertEqual(sync.configure(self.shared), "")
        sync._last.update(body=None, at=0.0)

    def tearDown(self):
        sync.configure("")

    def other(self, name="Windows", at=None, sessions=None, device="d2"):
        os.makedirs(os.path.join(self.shared, "Qosmopol", "cihazlar"), exist_ok=True)
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
        self.assertTrue(sync.publish([dict(ROW, last=time.time() * 1000), dict(ROW, id="local_far", remote=True)]))
        me = sync.device()["id"]
        d = json.load(open(os.path.join(self.shared, "Qosmopol", "cihazlar", f"{me}.json"), encoding="utf-8"))
        self.assertEqual([k["id"] for k in d["sessions"]], ["local_aaa"])
        self.assertNotIn("cwd", d["sessions"][0])
        self.assertNotIn("home", d["sessions"][0])
        self.assertEqual(d["sessions"][0]["bridge"], "session_01x")

    def test_writes_are_rare_enough_for_a_sync_service_to_upload_them(self):
        t = 1000.0
        self.assertTrue(sync.publish([ROW], now=t))
        self.assertFalse(sync.publish([dict(ROW, busy=True)], now=t + 30))  # changed, but too soon
        self.assertTrue(sync.publish([dict(ROW, busy=True)], now=t + sync.MIN_GAP + 1))
        self.assertFalse(sync.publish([dict(ROW, busy=True)], now=t + sync.MIN_GAP + 300))  # unchanged
        self.assertTrue(sync.publish([dict(ROW, busy=True)], now=t + sync.MIN_GAP + sync.HEARTBEAT + 2))

    def test_the_summary_is_rewritten_in_place(self):
        t = time.time()
        sync.publish([dict(ROW, last=t * 1000)], now=t)
        me = sync.device()["id"]
        path = os.path.join(self.shared, "Qosmopol", "cihazlar", f"{me}.json")
        inode = os.stat(path).st_ino
        sync.publish([dict(ROW, last=t * 1000, cat="completed")], now=t + sync.MIN_GAP + 1)
        self.assertEqual(os.stat(path).st_ino, inode)  # same file, no delete + create for the sync service to trash
        self.assertEqual(json.load(open(path, encoding="utf-8"))["sessions"][0]["cat"], "completed")

    def test_old_finished_sessions_stay_home(self):
        old = (time.time() - sync.RECENT - 60) * 1000
        sync.publish([dict(ROW, id="local_new", last=time.time() * 1000), dict(ROW, id="local_old", last=old, cat="completed"),
                      dict(ROW, id="local_oldwait", last=old, cat="blocked")])
        me = sync.device()["id"]
        d = json.load(open(os.path.join(self.shared, "Qosmopol", "cihazlar", f"{me}.json"), encoding="utf-8"))
        self.assertEqual(sorted(k["id"] for k in d["sessions"]), ["local_new", "local_oldwait"])

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
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "broken.json"), "w") as f:
            f.write("{not json")
        self.other(device="d3", sessions=[{"id": "../../etc"}, "x", dict(ROW, id="local_ok")])
        devices, rows = sync.peers()
        self.assertEqual([r["id"] for r in rows], ["local_ok"])

    def test_a_duplicate_folder_from_the_sync_service_is_read_too(self):
        dup = os.path.join(self.shared, "Qosmopol 2", "cihazlar")
        os.makedirs(dup)
        with open(os.path.join(dup, "d9.json"), "w", encoding="utf-8") as f:
            json.dump({"v": 1, "device": "d9", "name": "Windows", "at": int(time.time() * 1000), "sessions": [dict(ROW, id="local_dup")]}, f)
        self.other(name="Windows", device="d9", at=time.time() - 600, sessions=[dict(ROW, id="local_old")])  # older copy
        devices, rows = sync.peers()
        self.assertEqual([d["name"] for d in devices], ["Windows"])
        self.assertEqual([r["id"] for r in rows], ["local_dup"])

    def test_this_computer_joins_the_folder_the_others_use(self):
        me = sync.device()["id"]
        t = time.time()
        sync.publish([dict(ROW, last=t * 1000)], now=t)  # alone: Qosmopol
        own = os.path.join(self.shared, "Qosmopol", "cihazlar", f"{me}.json")
        self.assertTrue(os.path.exists(own))
        other = os.path.join(self.shared, "Qosmopol 1", "cihazlar")  # the other computer's folder arrives
        os.makedirs(other)
        with open(os.path.join(other, "d5.json"), "w", encoding="utf-8") as f:
            json.dump({"v": 1, "device": "d5", "name": "Mac", "at": int(t * 1000), "sessions": []}, f)
        sync.publish([dict(ROW, last=t * 1000, cat="completed")], now=t + sync.MIN_GAP + 1)
        self.assertTrue(os.path.exists(os.path.join(other, f"{me}.json")))
        self.assertFalse(os.path.exists(own))

    def test_turning_on_makes_no_folder_yet(self):
        fresh = tempfile.mkdtemp(dir=ROOT)
        self.assertEqual(sync.configure(fresh), "")
        self.assertEqual(os.listdir(fresh), [])

    def test_groups_gather_a_folder_and_a_single_session(self):
        me = sync.device()["id"]
        sync.set_groups({f"p:{me}:Projects": "Client Ads", "s:local_x": "Client Ads"})
        rows = [dict(ROW, id="local_a", proj="Projects"), dict(ROW, id="local_x", proj="Music"),
                dict(ROW, id="local_b", proj="Website")]
        names = sync.apply_groups(rows, me)
        self.assertEqual(names, ["Client Ads"])
        self.assertEqual([(k["id"], k["proj"], k.get("group", False)) for k in rows],
                         [("local_a", "Client Ads", True), ("local_x", "Client Ads", True), ("local_b", "Website", False)])
        self.assertEqual(rows[1]["proj0"], "Music")
        sync.set_groups({"s:local_x": ""})  # taken out again
        rows = [dict(ROW, id="local_x", proj="Music")]
        sync.apply_groups(rows, me)
        self.assertEqual(rows[0]["proj"], "Music")

    def test_groups_travel_and_the_newest_wins(self):
        me = sync.device()["id"]
        sync.set_groups({f"p:{me}:Projects": "Mine"})
        t = time.time()
        sync.publish([dict(ROW, proj="Mine", proj0="Projects", last=t * 1000)], now=t)
        d = json.load(open(os.path.join(self.shared, "Qosmopol", "cihazlar", f"{me}.json"), encoding="utf-8"))
        self.assertEqual(d["sessions"][0]["proj"], "Projects")  # the folder's name goes out, the group beside it
        self.assertEqual(d["groups"]["rules"], {f"p:{me}:Projects": "Mine"})
        later = int(time.time() * 1000) + 5000
        self.other(sessions=[dict(ROW, id="local_w", proj="shop-example")])
        path = os.path.join(self.shared, "Qosmopol", "cihazlar", "d2.json")
        doc = json.load(open(path, encoding="utf-8"))
        doc["groups"] = {"at": later, "rules": {"p:d2:shop-example": "Client Ads"}}
        json.dump(doc, open(path, "w", encoding="utf-8"))
        devices, rows = sync.peers()
        names = sync.apply_groups(rows, me)
        self.assertEqual(rows[0]["proj"], "Client Ads")
        self.assertEqual(sync.groups()["rules"], {"p:d2:shop-example": "Client Ads"})
        doc["groups"] = {"at": 1, "rules": {"x": "Old"}}  # an older change elsewhere does not undo ours
        json.dump(doc, open(path, "w", encoding="utf-8"))
        sync._peer_groups.update(at=0, rules={})
        sync.peers()
        self.assertEqual(sync.groups()["rules"], {"p:d2:shop-example": "Client Ads"})

    def test_rename(self):
        self.assertEqual(sync.configure(name="  Office   PC "), "")
        self.assertEqual(sync.device()["name"], "Office PC")
        self.assertEqual(sync.configure(name="   "), "empty name")


if __name__ == "__main__":
    unittest.main()
