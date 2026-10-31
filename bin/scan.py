#!/usr/bin/env python3
"""Reads every Claude desktop Code session on this Mac (all accounts) and prints one compact JSON.

argv[1]: this session's CLI id, to tell which account folder is the one signed in here.
Only fields the Qosmopol pane draws are kept; archived sessions are left out.
"""
import glob
import json
import os
import sys
import time

WRITTEN = {os.path.basename(f)[:-6]: os.path.getmtime(f) for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))}

ROOT = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
HOME = os.path.expanduser("~")
# Sessions the owner closed in the pane; works for every account, unlike archiving.
HIDDEN_FILE = os.path.expanduser("~/.qosmopol/gizli.txt")
# One line per closed session: id, project, title (tab separated).
LINES = [l.split("\t") for l in open(HIDDEN_FILE).read().splitlines() if l.strip()] if os.path.exists(HIDDEN_FILE) else []
if len(sys.argv) > 2 and sys.argv[1] in ("--gizle", "--ac"):
    LINES = [l for l in LINES if l[0] != sys.argv[2]]
    if sys.argv[1] == "--gizle":
        LINES.append([sys.argv[2], *(a.replace("\t", " ").replace("\n", " ") for a in sys.argv[3:5])])
    os.makedirs(os.path.dirname(HIDDEN_FILE), exist_ok=True)
    with open(HIDDEN_FILE, "w") as out:
        out.write("".join("\t".join(l) + "\n" for l in LINES))
    sys.exit(0)
HIDDEN = {l[0] for l in LINES}

me = sys.argv[1] if len(sys.argv) > 1 else ""


def project(path):
    if not path:
        return "?"
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
    rows.append({
        "id": d.get("sessionId"),
        "acc": acc,
        "title": (d.get("title") or "Untitled session")[:120],
        "proj": project(cwd),
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
    })

accounts.sort()
hidden = [{"id": l[0], "proj": l[1] if len(l) > 1 else "", "title": l[2] if len(l) > 2 else l[0]} for l in LINES]
print(json.dumps({"current": current, "accounts": accounts, "sessions": rows, "hidden": hidden}, ensure_ascii=False))
