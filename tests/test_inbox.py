"""bin/server.py inbox: the owner's words reach a running session through its own mod. Run with the other tests."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = tempfile.mkdtemp(prefix="qosmopol-inbox-")
os.environ["HOME"] = os.environ["USERPROFILE"] = ROOT  # never the owner's own ~/.qosmopol or sessions
BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin")
sys.path.insert(0, BIN)
import server  # noqa: E402

SESS = os.path.join(server.CLAUDE, "claude-code-sessions", "acc", "org")
CLI = "11111111-2222-3333-4444-555555555555"


class Inbox(unittest.TestCase):
    def setUp(self):
        os.makedirs(SESS, exist_ok=True)
        with open(os.path.join(SESS, "local_x.json"), "w") as f:
            json.dump({"sessionId": "local_x", "cliSessionId": CLI}, f)
        self.box = os.path.join(server.INBOX, CLI)
        os.makedirs(self.box, exist_ok=True)
        for n in os.listdir(self.box):
            os.remove(os.path.join(self.box, n))

    def beat(self, ago=0):
        p = os.path.join(self.box, ".canli")
        open(p, "w").close()
        os.utime(p, (time.time() - ago, time.time() - ago))

    def test_a_running_session_gets_it_in_its_own_inbox(self):
        self.beat()
        job = server.to_inbox("local_x", "devam et")
        m = json.load(open(os.path.join(self.box, job + ".json"), encoding="utf-8"))
        self.assertEqual((m["id"], m["text"]), ("local_x", "devam et"))

    def test_a_closed_session_goes_through_the_app(self):
        self.assertIsNone(server.to_inbox("local_x", "hi"))  # no heartbeat at all
        self.beat(ago=server.ALIVE + 5)
        self.assertIsNone(server.to_inbox("local_x", "hi"))  # stopped beating
        self.assertIsNone(server.to_inbox("local_nobody", "hi"))

    def test_a_message_left_lying_goes_to_the_home_session_once_and_receipts_are_swept(self):
        self.beat()
        job = server.to_inbox("local_x", "still there?")
        path = os.path.join(self.box, job + ".json")
        self.assertEqual(server.unclaimed(), [])  # the mod still has time
        old = time.time() - server.LATE - 1
        os.utime(path, (old, old))
        jobs = server.unclaimed()
        self.assertEqual([(j["kind"], j["id"], j["text"], j["job"]) for j in jobs], [("send", "local_x", "still there?", job)])
        self.assertFalse(os.path.exists(path))
        self.assertEqual(server.unclaimed(), [])
        receipt = os.path.join(self.box, "r.json")
        open(receipt, "w").close()
        os.utime(receipt, (time.time() - 61, time.time() - 61))
        server.unclaimed()
        self.assertFalse(os.path.exists(receipt))

    def test_the_token_and_the_folder_are_the_owners_alone(self):
        if os.path.exists(server.TOKEN_FILE):
            os.remove(server.TOKEN_FILE)
        os.chmod(server.HOME, 0o755)
        self.assertEqual(len(server.token()), 32)
        if sys.platform != "win32":  # Windows keeps them private through the user profile's access list, not mode bits
            self.assertEqual(os.stat(server.TOKEN_FILE).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(server.HOME).st_mode & 0o777, 0o700)

    def test_the_conversation_shows_what_came_through_another_session(self):
        proj = os.path.join(ROOT, ".claude", "projects", "p")
        os.makedirs(proj, exist_ok=True)
        rows = [{"type": "user", "isMeta": True, "origin": {"kind": "peer", "name": "Home", "body": "ok"},
                 "message": {"content": "Another Claude session sent a message: ok"}},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": "done"}]}}]
        with open(os.path.join(proj, CLI + ".jsonl"), "w", encoding="utf-8") as f:
            f.write("\n" + "\n".join(json.dumps(r) for r in rows) + "\n")
        out = subprocess.run([sys.executable, os.path.join(BIN, "konu.py"), "local_x"], capture_output=True, text=True,
                             env={**os.environ, "HOME": ROOT, "USERPROFILE": ROOT}).stdout
        self.assertEqual(json.loads(out)["msgs"], [{"role": "sen", "text": "ok", "via": "Home"}, {"role": "claude", "text": "done"}])

    def test_a_dropped_file_is_kept_here_privately_and_only_plain_kinds_get_in(self):
        import base64
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 100).decode()
        status, r = server.attach("Ekran Resmi 2026-11-05 13.21.23.png", png)
        self.assertEqual((status, r["name"], r["size"]), (200, "Ekran Resmi 2026-11-05 13.21.23.png", 108))
        self.assertEqual(os.path.dirname(r["path"]), server.ATTACH)
        with open(r["path"], "rb") as f:
            self.assertTrue(f.read().startswith(b"\x89PNG"))
        if sys.platform != "win32":
            self.assertEqual(os.stat(r["path"]).st_mode & 0o777, 0o600)
        self.assertEqual(server.attach("../../evil.png", png)[1]["path"].startswith(server.ATTACH + os.sep), True)  # never outside
        self.assertEqual(server.attach("run.sh", png)[0], 400)
        self.assertEqual(server.attach("a.png", "not base64!")[0], 400)
        self.assertEqual(server.attach("a.png", "")[0], 413)


if __name__ == "__main__":
    unittest.main()
