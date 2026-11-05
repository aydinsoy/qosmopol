"""bin/scan.py: what the map reads from the Claude app's session records. Run: python3 -m unittest discover -s tests -p 'test_*.py'"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCAN = os.path.join(os.path.dirname(__file__), "..", "bin", "scan.py")


class Scan(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="qosmopol-scan-")
        self.env = dict(os.environ, HOME=self.home, USERPROFILE=self.home, APPDATA=os.path.join(self.home, "AppData"))
        self.env.pop("QOSMOPOL_SYNC_DIR", None)
        claude = os.path.join(self.env["APPDATA"], "Claude") if sys.platform == "win32" else os.path.join(self.home, "Library", "Application Support", "Claude")
        self.sessions = os.path.join(claude, "claude-code-sessions", "acc", "space")
        self.transcripts = os.path.join(self.home, ".claude", "projects", "-Users-me-Projects")
        os.makedirs(self.sessions)
        os.makedirs(self.transcripts)

    def session(self, sid, cli, title, project=None, said=""):
        d = {"sessionId": sid, "cliSessionId": cli, "cwd": "/Users/me/Projects", "title": title, "lastActivityAt": 1}
        if project:
            d["remoteControlSpawn"] = {"ccrSessionId": "cse_x", "folder": "/Users/me/Projects", "projectThreadChild": True}
            wake = f'<wake reason="mention">\n  <project id="{project}" type="project">\n    <message from="human" id="m1">{said}</message>\n  </project>\n</wake>'
            with open(os.path.join(self.transcripts, cli + ".jsonl"), "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "queue-operation"}) + "\n")
                f.write(json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": wake}]}}) + "\n")
        with open(os.path.join(self.sessions, sid + ".json"), "w", encoding="utf-8") as f:
            json.dump(d, f)

    def scan(self):
        out = subprocess.run([sys.executable, SCAN], env=self.env, capture_output=True, text=True, encoding="utf-8", check=True).stdout
        return {k["id"]: k for k in json.loads(out)["sessions"]}

    def test_each_claude_project_is_its_own_planet_named_by_what_was_asked(self):
        self.session("local_a", "c-a", "Local session (from a project)", "chan_01AAAAAB12", "localhost &amp; port\n 5173")
        self.session("local_b", "c-b", "Remote Control session (from a project)", "chan_01AAAAAB12", "devam")
        self.session("local_c", "c-c", "Fix the font", "chan_01BBBBCD34", "ignored: the app gave it a title")
        self.session("local_d", "c-d", "Plain session in Projects")
        rows = self.scan()
        self.assertEqual([(rows[i]["proj"], rows[i]["title"]) for i in ("local_a", "local_b", "local_c", "local_d")],
                         [("Claude project · AB12", "localhost & port 5173"), ("Claude project · AB12", "devam"),
                          ("Claude project · CD34", "Fix the font"), ("Projects", "Plain session in Projects")])
        self.assertEqual([rows[i].get("unnamed") for i in ("local_a", "local_d")], [True, None])
        self.assertEqual((rows["local_a"]["proj0"], rows["local_a"]["sub"]), ("claude.ai · AB12", ""))
        self.assertEqual((rows["local_a"]["thread"], "thread" in rows["local_d"]), ("chan_01AAAAAB12", False))  # as claude.ai/projects links it

    def test_an_unnamed_project_speaks_claudes_language_and_a_given_name_holds_in_every_language(self):
        self.session("local_a", "c-a", "Local session (from a project)", "chan_01AAAAAB12", "hi")
        self.session("local_b", "c-b", "Local session (from a project)", "chan_01BBBBCD34", "hi")
        with open(os.path.join(os.path.dirname(self.sessions), "..", "..", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"locale": "tr-TR"}, f)
        rows = self.scan()
        self.assertEqual(rows["local_a"]["proj"], "Claude projesi · AB12")
        os.makedirs(os.path.join(self.home, ".qosmopol"), exist_ok=True)  # the owner names it once, from the map
        with open(os.path.join(self.home, ".qosmopol", "gruplar.json"), "w", encoding="utf-8") as f:
            json.dump({"at": 1, "rules": {f"p:{rows['local_a']['dev']}:claude.ai · AB12": "Space Game"}}, f)
        rows = self.scan()
        self.assertEqual([(rows[i]["proj"], rows[i].get("unnamed")) for i in ("local_a", "local_b")],
                         [("Space Game", None), ("Claude projesi · CD34", True)])

    def test_a_missing_or_odd_transcript_leaves_the_folder_planet(self):
        self.session("local_a", "c-a", "Local session (from a project)", "chan_01AAAAAB12", "hi")
        os.remove(os.path.join(self.transcripts, "c-a.jsonl"))
        self.session("local_b", "c-b", "Local session (from a project)", 'x" onload="evil', "hi")  # not a project id
        rows = self.scan()
        self.assertEqual([rows[i]["proj"] for i in ("local_a", "local_b")], ["Projects", "Projects"])


if __name__ == "__main__":
    unittest.main()
