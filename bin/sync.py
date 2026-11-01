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
VERSION = 1
HEARTBEAT = 60  # seconds: an unchanged summary is still rewritten this often, so the others see we are alive
STALE = 180  # seconds: a computer that wrote nothing for this long is shown as offline
# What another computer may see of a session: no folder paths, nothing the map does not show.
FIELDS = ("id", "acc", "title", "proj", "last", "seen", "created", "turns", "star", "cat", "need", "detail",
          "sumId", "error", "busy", "ask", "model", "effort", "mode", "bridge")
_last = {"body": None, "at": 0.0}


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


def configure(path=None, name=None):
    """Turn sync on with a folder ('' turns it off) and/or rename this computer. Returns an error or ''."""
    s = settings()
    if path is not None:
        path = os.path.expanduser(str(path).strip())
        if path:
            if not os.path.isdir(path):
                return "folder not found"
            try:
                os.makedirs(_dir(path), exist_ok=True)
                probe = os.path.join(_dir(path), f".yazma-{secrets.token_hex(4)}")
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


def publish(rows, now=None):
    """Write this computer's summary when it changed or the heartbeat is due. Returns True when written."""
    base = folder()
    if not base:
        return False
    now = time.time() if now is None else now
    me = device()
    sessions = [{f: k.get(f) for f in FIELDS} for k in rows if not k.get("remote")]
    body = json.dumps({"device": me["id"], "name": me["name"], "sessions": sessions}, ensure_ascii=False, sort_keys=True)
    if body == _last["body"] and now - _last["at"] < HEARTBEAT:
        return False
    _save(os.path.join(_dir(base), f"{me['id']}.json"),
          {"v": VERSION, "device": me["id"], "name": me["name"], "at": int(now * 1000), "os": sys.platform, "sessions": sessions})
    _last.update(body=body, at=now)
    return True


def _icloud_fetch(base):
    """macOS may keep a file iCloud has not downloaded yet as '.<name>.icloud': ask for it, read it next time."""
    if sys.platform != "darwin":
        return
    for stub in glob.glob(os.path.join(_dir(base), ".*.json.icloud")):
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
    for path in sorted(glob.glob(os.path.join(_dir(base), "*.json"))):
        d = _load(path, None)
        if not isinstance(d, dict) or d.get("device") in (None, me) or not isinstance(d.get("sessions"), list):
            continue
        name = " ".join(str(d.get("name") or "Computer").split())[:40]
        age = now - (d.get("at") or 0) / 1000
        stale = age > STALE
        devices.append({"id": str(d["device"])[:32], "name": name, "at": d.get("at") or 0, "stale": stale,
                        "os": str(d.get("os") or "")[:12], "sessions": len(d["sessions"])})
        for k in d["sessions"]:
            if not isinstance(k, dict) or not str(k.get("id") or "").startswith("local_"):
                continue
            row = {f: k.get(f) for f in FIELDS}
            row.update(proj=f"{row.get('proj') or 'No folder'} · {name}", cwd="", home=False, remote=True,
                       dev=devices[-1]["id"], devName=name, stale=stale)
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
