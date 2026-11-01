#!/usr/bin/env python3
"""Last turns of one Code session, read from its transcript: {"msgs": [{"role": "sen"|"claude", "text": ...}]}."""
import glob
import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # the JSON goes to a pipe, which Windows would write in its ANSI code page

sid = sys.argv[1] if len(sys.argv) > 1 else ""
# The Claude desktop app's own folder: ~/Library/Application Support/Claude on macOS, %APPDATA%\Claude on Windows.
CLAUDE = os.path.join(os.environ["APPDATA"], "Claude") if sys.platform == "win32" else os.path.expanduser("~/Library/Application Support/Claude")
ROOT = os.path.join(CLAUDE, "claude-code-sessions")
msgs = []
files = glob.glob(os.path.join(ROOT, "*", "*", f"{sid}.json")) if sid.startswith("local_") else []
# A bare transcript id (the home session, as the mod reports it) reads that transcript directly.
cli = json.load(open(files[0], encoding="utf-8")).get("cliSessionId") or "" if files else sid if sid.replace("-", "").isalnum() and len(sid) == 36 else ""
if cli:
    paths = glob.glob(os.path.expanduser(f"~/.claude*/projects/*/{cli}.jsonl")) if cli else []
    if paths:
        with open(paths[0], "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 600_000))  # the tail is enough for the last turns
            lines = f.read().decode("utf-8", "replace").splitlines()[1:]
        for line in lines:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            kind = d.get("type")
            if kind not in ("user", "assistant") or d.get("isSidechain") or d.get("isMeta"):
                continue
            content = (d.get("message") or {}).get("content")
            if isinstance(content, str):
                text = content
            else:
                text = "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")
            text = text.strip()
            if not text or text.startswith("<"):
                continue
            role = "sen" if kind == "user" else "claude"
            if msgs and msgs[-1]["role"] == role == "claude":
                msgs[-1]["text"] += "\n\n" + text
            else:
                msgs.append({"role": role, "text": text})
print(json.dumps({"msgs": [{**m, "text": m["text"][-1500:]} for m in msgs[-10:]]}, ensure_ascii=False))
