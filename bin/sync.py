"""Several computers on one map (docs/coklu-bilgisayar-tasarim.md, stage 1: seeing only).

Each Qosmopol writes a summary of its own sessions into a folder the owner's sync service already shares
(iCloud Drive, Google Drive, Dropbox, OneDrive) and reads the summaries the other computers wrote there.
Off until the owner picks the folder; no port is opened and the server stays on 127.0.0.1.

  <folder>/Qosmopol/cihazlar/<device id>.json   every computer writes only its own file, so nothing conflicts
"""
import glob
import json
import os
import secrets
import socket
import subprocess
import sys
import time

import winenv  # noqa: F401  (first: a bare Windows environment gets its home and APPDATA back)

HOME = os.path.expanduser("~/.qosmopol")
SETTINGS = os.path.join(HOME, "ayar.json")
DEVICE = os.path.join(HOME, "cihaz.json")
# The owner's own projects: {"at": ms, "rules": {"s:<session id>" or "p:<device id>:<folder project>": name}}.
# Claude's own project names are not open to plugins, so the owner gathers sessions under names here.
GROUPS = os.path.join(HOME, "gruplar.json")
VERSION = 1
# A sync service uploads a file only once it stops changing: iCloud left a summary rewritten every 30 s at
# "needs-upload" for 25 minutes (2026-11-01). So: at most one write per MIN_GAP, an unchanged one per HEARTBEAT.
MIN_GAP = 120  # seconds between two writes, however much changed
HEARTBEAT = 600  # seconds: an unchanged summary is still rewritten this often, so the others see we are alive
STALE = 1800  # seconds: a computer that wrote nothing for this long is shown as offline
RECENT = 30 * 86400  # seconds: older sessions stay home unless they wait for the owner (keeps the file small)
# What another computer may see of a session: no folder paths, nothing the map does not show.
FIELDS = ("id", "acc", "title", "proj", "last", "seen", "created", "turns", "star", "cat", "need", "detail",
          "sumId", "error", "busy", "ask", "model", "effort", "mode", "bridge", "rc", "side", "sub")
_last = {"body": None, "at": 0.0}
_peer_groups = {"at": 0, "rules": {}}  # the newest groups another computer published, seen by peers()


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{secrets.token_hex(3)}.tmp"  # the publisher thread and a page request may write at once
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
    os.replace(tmp, path)


def _host():
    if sys.platform == "darwin":
        try:  # the name the owner gave the Mac in System Settings, not its network name
            name = subprocess.run(["/usr/sbin/scutil", "--get", "ComputerName"], capture_output=True, text=True, timeout=5).stdout.strip()
            if name:
                return name
        except (OSError, subprocess.SubprocessError):
            pass
    return socket.gethostname().split(".")[0] or "Computer"


def device():
    """This computer: a random id made once, and a name the owner can change."""
    d = _load(DEVICE, {})
    if not d.get("id"):
        d = {"id": secrets.token_hex(8), "name": _host()}
        _save(DEVICE, d)
    return d


def settings():
    return _load(SETTINGS, {})


def folder():
    """The shared folder, or None while sync is off (QOSMOPOL_SYNC_DIR wins over the setting)."""
    path = os.environ.get("QOSMOPOL_SYNC_DIR") or settings().get("sync") or ""
    return path if path and os.path.isdir(path) else None


def _dir(base):
    return os.path.join(base, "Qosmopol", "cihazlar")


def _target(base, me):
    """The folder this computer writes into: the one the other computers already use. Two computers that each
    made "Qosmopol" before seeing the other's end up in two cloud folders, and one of them never reaches the
    other computer at all (Google Drive, 2026-11-01); joining the folder that holds the others' files ends that."""
    best, best_score = None, (0, 0)
    for d in _all_dirs(base):
        files = [os.path.basename(x) for x in glob.glob(os.path.join(d, "*.json"))]
        score = (sum(f != f"{me}.json" for f in files), int(f"{me}.json" in files))  # others first, then where we are
        if score > best_score or (score == best_score and best and d < best):
            best, best_score = d, score
    return best or _dir(base)


def _all_dirs(base):
    """Every computer's folder to read: a sync service may keep two folders made under the same name as
    "Qosmopol" and "Qosmopol 2" (Google Drive did, 2026-11-01), and each computer then writes into its own."""
    return sorted(d for d in glob.glob(os.path.join(base, "Qosmopol*", "cihazlar")) if os.path.isdir(d))


def configure(path=None, name=None):
    """Turn sync on with a folder ('' turns it off) and/or rename this computer. Returns an error or ''."""
    s = settings()
    if path is not None:
        path = os.path.expanduser(str(path).strip())
        if path:
            if not os.path.isdir(path):
                return "folder not found"
            try:  # probe the folder itself: making "Qosmopol" here early is how duplicate folders start
                probe = os.path.join(path, f".qosmopol-yazma-{secrets.token_hex(4)}")
                open(probe, "w").close()
                os.remove(probe)
            except OSError as err:
                return f"cannot write there: {err.strerror or err}"
        s["sync"] = path
        _last.update(body=None, at=0.0)
    if name is not None:
        name = " ".join(str(name).split())[:40]
        if not name:
            return "empty name"
        d = device()
        d["name"] = name
        _save(DEVICE, d)
        _last.update(body=None, at=0.0)
    _save(SETTINGS, s)
    return ""


def groups():
    """The owner's groups: this computer's, or another computer's when that one changed them later."""
    mine = _load(GROUPS, {"at": 0, "rules": {}})
    if (_peer_groups.get("at") or 0) > (mine.get("at") or 0):
        mine = {"at": _peer_groups["at"], "rules": dict(_peer_groups["rules"])}
        _save(GROUPS, mine)
    return mine


def set_groups(changes):
    """Put keys under a name ('' takes them out); the change reaches the other computers with the next summary."""
    rules = dict(groups().get("rules") or {})
    for key, name in changes.items():
        name = " ".join(str(name or "").split())[:60]
        if name:
            rules[key] = name
        else:
            rules.pop(key, None)
    g = {"at": int(time.time() * 1000), "rules": rules}
    _save(GROUPS, g)
    _last.update(body=None, at=0.0)  # publish at once, not after the usual gap
    return g


def apply_groups(rows, me):
    """Give each session the owner's project name: a session's own rule, then its subfolder's (the deepest one),
    then its project folder's, then the Claude sidebar group it is filed under. Returns every name in use, for the
    "Move to project" list. The rule that named a session stays on it, so renaming its planet changes that rule."""
    rules = groups().get("rules") or {}
    for k in rows:
        k.setdefault("dev", me)
        k.setdefault("proj0", k.get("proj") or "")
        side = k.get("side") if isinstance(k.get("side"), str) else ""
        parts = [p for p in (k.get("sub") if isinstance(k.get("sub"), str) else "").split("/") if p]
        keys = ["s:" + str(k.get("id"))] + [f"f:{k['dev']}:{k['proj0']}/" + "/".join(parts[:n]) for n in range(len(parts), 0, -1)]
        rule = next((key for key in keys + [f"p:{k['dev']}:{k['proj0']}"] if rules.get(key)), None)
        if rule:
            k["proj"], k["group"], k["rule"] = rules[rule], True, rule
        elif side:
            k["proj"], k["group"] = side, True
    return sorted(set(rules.values()) | {k["side"] for k in rows if isinstance(k.get("side"), str) and k["side"]})


def publish(rows, now=None):
    """Write this computer's summary when it changed or the heartbeat is due. Returns True when written."""
    base = folder()
    if not base:
        return False
    now = time.time() if now is None else now
    me = device()
    keep = lambda k: now - (k.get("last") or 0) / 1000 < RECENT or k.get("ask") or k.get("cat") == "blocked"
    # a session goes out under its folder's name; the groups travel beside it, for every computer to apply
    sessions = [{f: (k.get("proj0") or k.get("proj")) if f == "proj" else k.get(f) for f in FIELDS}
                for k in rows if not k.get("remote") and keep(k)]
    g = groups()
    body = json.dumps({"device": me["id"], "name": me["name"], "sessions": sessions, "groups": g}, ensure_ascii=False, sort_keys=True)
    if now - _last["at"] < (HEARTBEAT if body == _last["body"] else MIN_GAP):
        return False
    # Written in place, not as a new file swapped in: iCloud for Windows takes the swap for a deletion and fills its
    # trash with old copies (2026-11-01). A reader that catches it half written skips it until the next round.
    target = _target(base, me["id"])
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, f"{me['id']}.json"), "w", encoding="utf-8") as f:
        json.dump({"v": VERSION, "device": me["id"], "name": me["name"], "at": int(now * 1000), "os": sys.platform,
                   "sessions": sessions, "groups": g}, f, ensure_ascii=False)
    for d in _all_dirs(base):  # our own copy left in a folder we moved out of
        old = os.path.join(d, f"{me['id']}.json")
        if d != target and os.path.exists(old):
            try:
                os.remove(old)
            except OSError:
                pass
    _last.update(body=body, at=now)
    return True


def _icloud_fetch(base):
    """macOS may keep a file iCloud has not downloaded yet as '.<name>.icloud': ask for it, read it next time."""
    if sys.platform != "darwin":
        return
    for stub in (x for d in _all_dirs(base) for x in glob.glob(os.path.join(d, ".*.json.icloud"))):
        try:
            subprocess.Popen(["/usr/bin/brctl", "download", stub], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def peers(now=None):
    """The other computers and their sessions: (devices, rows). Rows carry dev/devName/remote and a project
    name that says which computer it is on, so the same folder name on two computers stays two planets."""
    base = folder()
    if not base:
        return [], []
    now = time.time() if now is None else now
    me = device()["id"]
    _icloud_fetch(base)
    devices, rows = [], []
    newest = {}
    for path in (x for d in _all_dirs(base) for x in glob.glob(os.path.join(d, "*.json"))):
        d = _load(path, None)
        if not isinstance(d, dict) or d.get("device") in (None, me) or not isinstance(d.get("sessions"), list):
            continue
        if (d.get("at") or 0) > (newest.get(d["device"], {}).get("at") or -1):
            newest[d["device"]] = d  # the same computer in two folders: its latest summary wins
        g = d.get("groups")
        if isinstance(g, dict) and isinstance(g.get("rules"), dict) and (g.get("at") or 0) > (_peer_groups.get("at") or 0):
            rules = {str(a)[:300]: " ".join(str(b).split())[:60] for a, b in list(g["rules"].items())[:2000] if str(b).strip()}
            _peer_groups.update(at=int(g.get("at") or 0), rules=rules)
    for d in sorted(newest.values(), key=lambda d: str(d.get("name") or "")):
        name = " ".join(str(d.get("name") or "Computer").split())[:40]
        age = now - (d.get("at") or 0) / 1000
        stale = age > STALE
        devices.append({"id": str(d["device"])[:32], "name": name, "at": d.get("at") or 0, "stale": stale,
                        "os": str(d.get("os") or "")[:12], "sessions": len(d["sessions"])})
        for k in d["sessions"]:
            if not isinstance(k, dict) or not str(k.get("id") or "").startswith("local_"):
                continue
            row = {f: k.get(f) for f in FIELDS}
            row.update(proj=f"{row.get('proj') or 'No folder'} · {name}", proj0=row.get("proj") or "No folder", cwd="",
                       home=False, remote=True, dev=devices[-1]["id"], devName=name, stale=stale)
            if stale:
                row["busy"] = False  # nobody is reporting it: do not show it as working
            rows.append(row)
    return devices, rows


def candidates():
    """Folders a sync service keeps on this computer, the likeliest first."""
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        pats = [os.path.join(home, "iCloudDrive"), os.path.join("G:\\", "My Drive"), os.path.join(home, "Google Drive"),
                os.path.join(home, "Dropbox"), os.environ.get("OneDrive") or "", os.path.join(home, "OneDrive")]
    else:
        pats = [os.path.join(home, "Library", "Mobile Documents", "com~apple~CloudDocs"),
                os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*", "My Drive"),
                os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*", "Drive'ım"),
                os.path.join(home, "Library", "CloudStorage", "Dropbox"), os.path.join(home, "Dropbox"),
                os.path.join(home, "Library", "CloudStorage", "OneDrive*")]
    out = []
    for p in pats:
        for hit in sorted(glob.glob(p)) if p else []:
            if os.path.isdir(hit) and hit not in out:
                out.append(hit)
    return out


def state():
    """What the web view's settings column shows."""
    devices, _ = peers()
    return {"enabled": bool(folder()), "folder": folder() or settings().get("sync") or "", "device": device(),
            "devices": devices, "candidates": candidates(), "env": bool(os.environ.get("QOSMOPOL_SYNC_DIR"))}
