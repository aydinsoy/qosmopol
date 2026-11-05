"""web/index.html: checks that need no browser. Run with the other tests."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

PAGE = os.path.join(os.path.dirname(__file__), "..", "web", "index.html")


class Page(unittest.TestCase):
    def script(self):
        html = open(PAGE, encoding="utf-8").read()
        return html[html.index("<script>") + 8:html.rindex("</script>")]

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_script_parses(self):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(self.script())
        r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
        os.remove(f.name)
        self.assertEqual(r.returncode, 0, r.stderr[-500:])

    def test_the_flight_defines_what_it_calls(self):
        # 0.3.32 folded "ease = ..." into a comment: every flight stopped at its first frame (owner 2026-11-05)
        body = re.search(r"function flyTo\(.*?\n}\n", self.script(), re.S).group(0)
        code = "\n".join(line.split("//")[0] for line in body.splitlines())
        for name in re.findall(r"\b(ease|dip|far|ms)\(?", code):
            self.assertRegex(code, rf"\b(const|let)\s+[^;\n]*\b{name}\s*=", f"{name} is used in flyTo but never defined there")


if __name__ == "__main__":
    unittest.main()
