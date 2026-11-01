#!/usr/bin/env python3
"""Qosmopol web server: the sky as a local web app.

Serves web/index.html and a small JSON API on 127.0.0.1 only. Every API call must carry the
token from ~/.qosmopol/token, which the page receives embedded in its HTML, so another site
open in the same browser cannot drive it. Reading sessions and opening one in the app happen
here; sending a message, archiving and unarchiving need the app itself, so they are written
to a queue that the Qosmopol mod (running inside a Claude Code session) carries out.

  server.py [--port N]      serve in the foreground
  server.py --daemon        serve in the background, unless one already answers
  server.py claim ID        (for the mod) make this session the home one
  server.py take [ID]       (for the mod) print and clear the queued jobs, if ID is the home
  server.py done JSON       (for the mod) store results: [{"job": ..., "ok": ..., "text": ...}]
"""
import glob
import http.server
import re
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import winenv  # noqa: F401  (first: a bare Windows environment gets its home and APPDATA back)
import sync
import urllib.parse

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # the JSON goes to a pipe, which Windows would write in its ANSI code page

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(os.path.dirname(HERE), "web")
HOME = os.path.expanduser("~/.qosmopol")
QUEUE = os.path.join(HOME, "kuyruk.jsonl")
RESULTS = os.path.join(HOME, "sonuc.json")
ARCHIVE = os.path.join(HOME, "mesajlar.json")
READ = os.path.join(HOME, "okundu.json")
TOKEN_FILE = os.path.join(HOME, "token")
SESSION = os.path.join(HOME, "oturum")
ORDER = os.path.join(HOME, "sira.json")
RC = os.path.join(HOME, "rc.json")  # which sessions' Remote Control is on, as the home session last saw it
PORT = 47321
KEEP = 1000
LOCK = threading.Lock()
# The Claude desktop app's own folder: ~/Library/Application Support/Claude on macOS, %APPDATA%\Claude on Windows.
CLAUDE = os.path.join(os.environ["APPDATA"], "Claude") if sys.platform == "win32" else os.path.expanduser("~/Library/Application Support/Claude")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)
    os.replace(tmp, path)


def token():
    os.makedirs(HOME, exist_ok=True)
    if not os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "w") as f:
            f.write(secrets.token_hex(16))
        os.chmod(TOKEN_FILE, 0o600)
    return open(TOKEN_FILE).read().strip()


def run(script, *args, timeout=60):
    r = subprocess.run([sys.executable, os.path.join(HERE, script), *args], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or f"exit {r.returncode}")[:300])
    return r.stdout


SCAN = {"at": 0, "data": None}


def scan():
    """The sessions, at most every 5 seconds; new end-of-turn reports join the message archive."""
    with LOCK:
        if SCAN["data"] is not None and time.time() - SCAN["at"] < 5:
            return SCAN["data"]
        me = open(SESSION).read().strip() if os.path.exists(SESSION) else ""  # written by the mod: decides which account is "this" one
        data = json.loads(run("scan.py", me))
        log = load(ARCHIVE, [])
        known = {m["id"] for m in log}
        fresh = [
            {"id": k["sumId"], "sid": k["id"], "proj": k["proj"], "title": k["title"], "acc": k["acc"],
             "cat": k["cat"], "text": (k["need"] or k["detail"] or k["cat"])[:500], "at": k["last"], "read": False}
            for k in data["sessions"]
            if k["sumId"] and k["sumId"] not in known and (k["cat"] or k["need"] or k["detail"])
        ]
        if fresh:
            log = sorted(log + fresh, key=lambda m: m["at"])[-KEEP:]
            save(ARCHIVE, log)
        data["messages"] = log
        data["readAt"] = load(READ, {})
        data["order"] = load(ORDER, [])
        data["homeDir"] = os.path.expanduser("~")
        # the page speaks the language the owner chose in the Claude app (config.json "locale"); the browser decides otherwise
        data["lang"] = load(os.path.join(CLAUDE, "config.json"), {}).get("locale", "")
        data["results"] = load(RESULTS, {})
        data["at"] = int(time.time() * 1000)
        SCAN.update(at=time.time(), data=data)
    try:  # this computer's summary for the owner's other computers; a sync folder that fails must not stop the map
        sync.publish(data["sessions"])
    except OSError:
        pass
    return data


def publisher():
    """Keeps this computer's summary fresh in the sync folder while no page asks for scans."""
    while True:
        time.sleep(30)
        try:
            if sync.folder():
                scan()
        except Exception:  # noqa: BLE001 - try again next round
            pass


def remote(sid):
    """The row of a session that lives on another computer, or None."""
    k = next((x for x in scan()["sessions"] if x["id"] == sid), None)
    return k if k and k.get("remote") else None


def local_file(sid):
    return bool(glob.glob(os.path.join(CLAUDE, "claude-code-sessions", "*", "*", f"{sid}.json")))


def enqueue(job):
    job = {**job, "job": secrets.token_hex(6), "at": int(time.time() * 1000)}
    with LOCK, open(QUEUE, "a", encoding="utf-8") as f:
        f.write(json.dumps(job, ensure_ascii=False) + "\n")
    return job["job"]


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost") and secrets.compare_digest(self.headers.get("X-Qosmopol-Token") or "", TOKEN)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        static = {"/icon.png": "image/png", "/icon-192.png": "image/png", "/icon.svg": "image/svg+xml", "/manifest.webmanifest": "application/manifest+json", "/sw.js": "text/javascript"}
        if url.path in static:  # the app icon and manifest: no token, nothing private
            with open(os.path.join(WEB, url.path[1:]), "rb") as f:
                return self.reply(200, f.read(), static[url.path])
        if url.path in ("/", "/index.html"):
            # the page carries the API token: only for this computer's own address, never for a name a DNS
            # rebinding page could point here (found by the public-repo review, 2026-11-01)
            if (self.headers.get("Host") or "").split(":")[0] not in ("127.0.0.1", "localhost"):
                return self.reply(403, {"error": "forbidden"})
            html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read().replace("__QOSMOPOL_TOKEN__", TOKEN)
            return self.reply(200, html.encode(), "text/html")
        if not url.path.startswith("/api/"):
            return self.reply(404, {"error": "not found"})
        if not self.allowed():
            return self.reply(403, {"error": "forbidden"})
        q = urllib.parse.parse_qs(url.query)
        try:
            if url.path == "/api/scan":
                return self.reply(200, scan())
            if url.path == "/api/sync":
                return self.reply(200, sync.state())
            if url.path == "/api/konu":
                sid = q.get("id", [""])[0]
                if sid == "home":  # the Qosmopol home session, by its transcript id
                    sid = open(SESSION).read().strip() if os.path.exists(SESSION) else ""
                elif not sid.startswith("local_"):
                    sid = ""
                return self.reply(200, json.loads(run("konu.py", sid)))
        except Exception as err:  # noqa: BLE001 - the page shows it
            return self.reply(500, {"error": str(err)[:300]})
        return self.reply(404, {"error": "not found"})

    def do_POST(self):
        if not self.allowed():
            return self.reply(403, {"error": "forbidden"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.reply(400, {"error": "bad request"})
        path = urllib.parse.urlparse(self.path).path
        sid = str(body.get("id") or "")
        if sid and not (sid.startswith("local_") and sid.replace("-", "").replace("_", "").isalnum()):
            return self.reply(400, {"error": "invalid session"})
        try:
            if path == "/api/sync":  # the shared folder ('' turns sync off) and this computer's name
                err = sync.configure(body.get("folder"), body.get("name"))
                if err:
                    return self.reply(400, {"error": err})
                SCAN["at"] = 0
                return self.reply(200, sync.state())
            # a session on another computer: this computer's Claude app cannot open, message or change it
            if path in ("/api/open", "/api/send", "/api/set") and sid and remote(sid):
                return self.reply(409, {"error": "this session is on another computer; open it on claude.ai"})
            if path == "/api/open":
                if sys.platform == "win32":
                    os.startfile(f"claude://claude.ai/epitaxy/{sid}")
                else:
                    subprocess.run(["/usr/bin/open", f"claude://claude.ai/epitaxy/{sid}"], timeout=10, check=True)
                return self.reply(200, {"ok": True})
            if path == "/api/reveal":  # show a session's own working folder in Finder; never a path from the page
                sessions = scan()["sessions"]
                k = next((x for x in sessions if x["id"] == sid), None) if sid else next((x for x in sessions if x.get("home")), None)
                folder = (k or {}).get("cwd") or ""
                if not folder or not os.path.isdir(folder):
                    return self.reply(404, {"error": "no folder"})
                if sys.platform == "win32":
                    os.startfile(folder)  # File Explorer
                else:
                    subprocess.run(["/usr/bin/open", folder], timeout=10, check=True)
                return self.reply(200, {"ok": True})
            if path == "/api/read":
                with LOCK:
                    r = load(READ, {})
                    r[sid] = int(time.time() * 1000)
                    save(READ, r)
                    SCAN["at"] = 0
                return self.reply(200, {"ok": True})
            if path == "/api/send":
                text = str(body.get("text") or "").strip()[:8000]
                if not text:
                    return self.reply(400, {"error": "empty message"})
                return self.reply(200, {"job": enqueue({"kind": "send", "id": sid or "self", "text": text})})
            if path == "/api/close":
                sess = {k["id"]: k for k in scan()["sessions"]}
                k = sess.get(sid)
                run("scan.py", "--gizle", sid, (k or {}).get("proj", ""), (k or {}).get("title", sid))
                job = enqueue({"kind": "archive", "id": sid}) if k and not k.get("remote") and k["acc"] == scan()["current"] else None
                SCAN["at"] = 0
                return self.reply(200, {"ok": True, "job": job})
            if path == "/api/reopen":
                run("scan.py", "--ac", sid)
                SCAN["at"] = 0
                return self.reply(200, {"ok": True, "job": enqueue({"kind": "unarchive", "id": sid}) if local_file(sid) else None})
            if path == "/api/group":  # sessions or a whole planet under one of the owner's project names ('' takes them out)
                rows = scan()["sessions"]
                rules = sync.groups().get("rules") or {}
                if sid:
                    keys = ["s:" + sid]
                else:
                    planet = str(body.get("planet") or "")[:200]
                    keys = sorted({("s:" + k["id"]) if ("s:" + k["id"]) in rules else f"p:{k.get('dev', '')}:{k.get('proj0') or k['proj']}"
                                   for k in rows if k["proj"] == planet})
                if not keys:
                    return self.reply(404, {"error": "nothing to move"})
                sync.set_groups({key: body.get("name") or "" for key in keys})
                SCAN["at"] = 0
                return self.reply(200, {"ok": True, "moved": len(keys)})
            if path == "/api/order":  # the owner's own order of projects; [] goes back to automatic
                order = body.get("order")
                if not isinstance(order, list) or len(order) > 1000 or not all(isinstance(n, str) and len(n) <= 200 for n in order):
                    return self.reply(400, {"error": "invalid order"})
                with LOCK:
                    save(ORDER, order)
                    SCAN["at"] = 0
                return self.reply(200, {"ok": True})
            if path == "/api/set":  # model, effort or permission mode of a session; '' is the home session
                what, value = body.get("what"), str(body.get("value") or "")
                ok = (what == "effort" and value in ("low", "medium", "high", "xhigh", "max")) \
                    or (what == "mode" and value in ("default", "acceptEdits", "plan", "auto")) \
                    or (what == "model" and re.fullmatch(r"claude-[a-z0-9.\-]{1,60}(\[1m\])?", value) is not None)
                if not ok:
                    return self.reply(400, {"error": "invalid setting"})
                return self.reply(200, {"job": enqueue({"kind": "set", "id": sid or "self", "what": what, "value": value})})
            if path == "/api/ping":
                return self.reply(200, {"job": enqueue({"kind": "ping"})})
        except Exception as err:  # noqa: BLE001
            return self.reply(500, {"error": str(err)[:300]})
        return self.reply(404, {"error": "not found"})


def answering(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def take():
    """Hand the queued jobs to the mod and empty the queue, atomically."""
    os.makedirs(HOME, exist_ok=True)
    tmp = QUEUE + ".alindi"
    try:
        os.replace(QUEUE, tmp)
    except FileNotFoundError:
        print("[]")
        return
    jobs = []
    for line in open(tmp, encoding="utf-8"):
        try:
            jobs.append(json.loads(line))
        except ValueError:
            pass
    os.remove(tmp)
    print(json.dumps(jobs, ensure_ascii=False))


def done(raw):
    results = load(RESULTS, {})
    for r in json.loads(raw):
        results[r["job"]] = {"ok": bool(r.get("ok")), "text": str(r.get("text", ""))[:400], "at": int(time.time() * 1000)}
    save(RESULTS, dict(sorted(results.items(), key=lambda kv: kv[1]["at"])[-200:]))


def started(port):
    """Exit code of --daemon: 0 once the new server answers, 1 with the last line of its log when it never does."""
    for _ in range(30):
        time.sleep(0.2)
        if answering(port):
            print(f"http://127.0.0.1:{port}/")
            return 0
    try:
        with open(os.path.join(HOME, "server.log"), errors="replace") as f:
            lines = [l.strip() for l in f.read()[-2000:].splitlines() if l.strip()]
    except OSError:
        lines = []
    print(f"the server did not start on port {port}" + (f": {lines[-1]}" if lines else ""), file=sys.stderr)
    return 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["claim"] and len(args) > 1:
        # The session that ran /qosmopol becomes the home: it runs the bridge and gets "self" messages.
        os.makedirs(HOME, exist_ok=True)
        with open(SESSION, "w") as f:
            f.write(args[1])
        sys.exit(0)
    if args[:1] == ["home"]:
        print(open(SESSION).read().strip() if os.path.exists(SESSION) else "")
        sys.exit(0)
    if args[:1] == ["take"]:
        home = open(SESSION).read().strip() if os.path.exists(SESSION) else ""
        if len(args) > 1 and args[1] != home:
            print("[]")  # only the home session carries out the queue
        else:
            take()
        sys.exit(0)
    if args[:1] == ["rc"] and len(args) > 1:
        try:
            seen = json.loads(args[1])
        except ValueError:
            sys.exit(1)
        os.makedirs(HOME, exist_ok=True)
        save(RC, {"at": int(time.time() * 1000),
                  "rc": {str(k): bool(v) for k, v in (seen.items() if isinstance(seen, dict) else []) if str(k).startswith("local_")}})
        sys.exit(0)
    if args[:1] == ["done"]:
        done(args[1] if len(args) > 1 else "[]")
        sys.exit(0)
    if "--port" in args:
        PORT = int(args[args.index("--port") + 1])
    if "--daemon" in args:
        if answering(PORT):
            print(f"http://127.0.0.1:{PORT}/ already running")
            sys.exit(0)
        if sys.platform == "win32":
            # No fork on Windows: start a copy of this server with no console that outlives its caller.
            os.makedirs(HOME, exist_ok=True)
            out = open(os.path.join(HOME, "server.log"), "a")
            argv = [sys.executable, os.path.abspath(__file__), "--port", str(PORT)]
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=out, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB)
            except OSError:  # the caller's job does not allow leaving it
                subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=out, creationflags=flags)
            sys.exit(started(PORT))
        if os.fork():
            sys.exit(started(PORT))
        os.setsid()
        if os.fork():
            os._exit(0)
        os.makedirs(HOME, exist_ok=True)
        out = open(os.path.join(HOME, "server.log"), "a")
        os.dup2(out.fileno(), 1)
        os.dup2(out.fileno(), 2)
    TOKEN = token()
    threading.Thread(target=publisher, daemon=True).start()
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
