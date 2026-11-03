#!/usr/bin/env python3
"""Reads every Claude desktop Code session on this Mac (all accounts) and prints one compact JSON.

argv[1]: this session's CLI id, to tell which account folder is the one signed in here.
Only fields the Qosmopol pane draws are kept; archived sessions are left out.
"""
import glob
import html
import json
import os
import re
import sys
import time
import winenv  # noqa: F401  (first: a bare Windows environment gets its home and APPDATA back)
import sync

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # the JSON goes to a pipe, which Windows would write in its ANSI code page

TRANSCRIPTS = {os.path.basename(f)[:-6]: f for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))}
WRITTEN = {k: os.path.getmtime(f) for k, f in TRANSCRIPTS.items()}

# The Claude desktop app's own folder: ~/Library/Application Support/Claude on macOS, %APPDATA%\Claude on Windows.
CLAUDE = os.path.join(os.environ["APPDATA"], "Claude") if sys.platform == "win32" else os.path.expanduser("~/Library/Application Support/Claude")
ROOT = os.path.join(CLAUDE, "claude-code-sessions")
HOME = os.path.expanduser("~").replace("\\", "/")
# Sessions the owner closed in the pane; works for every account, unlike archiving.
HIDDEN_FILE = os.path.expanduser("~/.qosmopol/gizli.txt")
# One line per closed session: id, project, title (tab separated).
LINES = [l.split("\t") for l in open(HIDDEN_FILE, encoding="utf-8").read().splitlines() if l.strip()] if os.path.exists(HIDDEN_FILE) else []
if len(sys.argv) > 2 and sys.argv[1] in ("--gizle", "--ac"):
    LINES = [l for l in LINES if l[0] != sys.argv[2]]
    if sys.argv[1] == "--gizle":
        LINES.append([sys.argv[2], *(a.replace("\t", " ").replace("\n", " ") for a in sys.argv[3:5])])
    os.makedirs(os.path.dirname(HIDDEN_FILE), exist_ok=True)
    with open(HIDDEN_FILE, "w", encoding="utf-8") as out:
        out.write("".join("\t".join(l) + "\n" for l in LINES))
    sys.exit(0)
HIDDEN = {l[0] for l in LINES}

me = sys.argv[1] if len(sys.argv) > 1 else ""


def project(path):
    if not path:
        return "?"
    if sys.platform == "win32":
        path = path.replace("\\", "/")  # C:\Users\... reads like a POSIX path below
    if "/scratch-workspaces/" in path:
        return "No folder"
    parts = path.rstrip("/").split("/")
    if "Projects" in parts:
        i = parts.index("Projects")
        if i + 1 < len(parts):
            return parts[i + 1]
        return "Projects"
    if path.rstrip("/") == HOME:
        return "~"
    return parts[-1]


def subfolder(path):
    """The folder below the project's own, as in Media/#Game → "#Game": one project folder often holds several pieces
    of work, and a folder rule can gather one of them on its own. '' when the session runs in the project folder."""
    parts = (path or "").replace("\\", "/").rstrip("/").split("/")
    if "/scratch-workspaces/" in path or "Projects" not in parts:
        return ""
    return "/".join(parts[parts.index("Projects") + 2:])


def project_thread(d):
    """A session that a Claude project (claude.ai Projects) started on this computer: (project id, first message).
    The app names every such session "Local session (from a project)" and runs it in the Projects folder, so without
    this they all fall on one planet. The project's own conversation lives on claude.ai; only its id is written here,
    in the message that woke the session."""
    if not (d.get("remoteControlSpawn") or {}).get("projectThreadChild"):
        return None
    try:
        with open(TRANSCRIPTS.get(d.get("cliSessionId") or "", ""), encoding="utf-8") as fh:
            for _, line in zip(range(200), fh):
                if "<project id=" not in line:
                    continue
                c = json.loads(line).get("message", {}).get("content")
                text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
                m = re.search(r'<project id="(chan_[A-Za-z0-9]{4,60})"', text)
                if m:
                    said = re.search(r"<message\b[^>]*>(.*?)</message>", text, re.S)
                    return m.group(1), " ".join(html.unescape(said.group(1) if said else "").split())
    except (OSError, ValueError, AttributeError):
        pass
    return None


accounts, rows, current = [], [], ""
for f in glob.glob(os.path.join(ROOT, "*", "*", "local_*.json")):
    acc = os.path.relpath(f, ROOT).split(os.sep)[0]
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        continue
    if me and (d.get("cliSessionId") == me or me in (d.get("priorCliSessionIds") or [])):
        current = acc
    if d.get("isArchived") or d.get("sessionId") in HIDDEN:
        continue
    if acc not in accounts:
        accounts.append(acc)
    s = d.get("postTurnSummary") or {}
    cwd = d.get("originCwd") or d.get("cwd") or ""
    title, proj, sub = d.get("title") or "Untitled session", project(cwd), subfolder(cwd)
    thread = project_thread(d)
    if thread:  # one planet per Claude project (they live on claude.ai), until the owner names it on the map
        proj, sub = "claude.ai · " + thread[0][-4:], ""  # same in every language: the rename rule is keyed on it
        if thread[1] and re.search(r"\(from a project\)$", title):
            title = thread[1]
    rows.append({
        "id": d.get("sessionId"),
        "acc": acc,
        "title": title[:120],
        "proj": proj,
        "sub": sub,
        "cwd": cwd,
        "last": d.get("lastActivityAt") or 0,
        "seen": d.get("lastFocusedAt") or 0,
        "created": d.get("createdAt") or 0,
        "turns": d.get("completedTurns") or 0,
        "star": bool(d.get("isStarred")),
        "cat": s.get("status_category") or "",
        "need": (s.get("needs_action") or "")[:600],
        "detail": (s.get("status_detail") or "")[:600],
        "sumId": s.get("summarizes_uuid") or "",
        "error": bool(d.get("error")),
        # A running turn keeps appending to its transcript; the session file itself is only written at turn edges.
        "busy": time.time() - WRITTEN.get(d.get("cliSessionId") or "", 0) < 90,
        # Set while a turn is paused on a permission or a question for the owner.
        "ask": bool(d.get("interruptedAwaitingPerson")),
        # what the composer's bottom row shows (and lets the owner change)
        "model": d.get("model") or "",
        "effort": d.get("effort") or "",
        "mode": d.get("permissionMode") or "",
        "home": bool(me) and (d.get("cliSessionId") == me or me in (d.get("priorCliSessionIds") or [])),
        # Remote Control's id: claude.ai/code/<id> opens the session from any device while it is still valid
        "bridge": (d.get("bridgeSessionIds") or [""])[-1],
    })

# Remote Control on or off, as the home session last read it from the app; too old a reading says nothing.
try:
    _rc = json.load(open(os.path.expanduser("~/.qosmopol/rc.json"), encoding="utf-8"))
    RC = _rc.get("rc") or {} if time.time() - (_rc.get("at") or 0) / 1000 < 600 else {}
    SIDE = _rc.get("side") or {}  # names do not go stale like the switch does: they stand until the app says otherwise
except (OSError, ValueError, AttributeError):
    RC, SIDE = {}, {}
for k in rows:
    if k["id"] in RC:
        k["rc"] = RC[k["id"]]
    if isinstance(SIDE.get(k["id"]), str):
        k["side"] = SIDE[k["id"]]
# The owner's other computers, from the shared sync folder (off until the owner picks one).
try:
    devices, remote = sync.peers()
except OSError:  # an unreadable sync folder must not take this computer's own sessions with it
    devices, remote = [], []
rows += [k for k in remote if k["id"] not in HIDDEN]
try:  # the owner's own project names, on this computer's sessions and the others' alike
    group_names = sync.apply_groups(rows, sync.device()["id"])
except OSError:
    group_names = []
try:  # the language the owner chose in the Claude app, for the band and the pane
    lang = json.load(open(os.path.join(CLAUDE, "config.json"), encoding="utf-8")).get("locale", "")
except (OSError, ValueError):
    lang = ""
# A Claude project nobody has named yet: its name stays on claude.ai, so the map says what it is, in the owner's
# language, and asks for the name once. The rules stay keyed on "claude.ai · XXXX", the same in every language.
for k in rows:
    m = not k.get("group") and re.fullmatch(r"claude\.ai · ([A-Za-z0-9]{4})", k.get("proj0") or "")
    if m:
        k["proj"], k["unnamed"] = ("Claude projesi · " if lang.lower().startswith("tr") else "Claude project · ") + m.group(1), True
accounts.sort()
hidden = [{"id": l[0], "proj": l[1] if len(l) > 1 else "", "title": l[2] if len(l) > 2 else l[0]} for l in LINES]
print(json.dumps({"current": current, "accounts": accounts, "sessions": rows, "hidden": hidden, "lang": lang, "devices": devices, "groups": group_names}, ensure_ascii=False))
