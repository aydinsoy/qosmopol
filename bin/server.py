#!/usr/bin/env python3
"""Qosmos web server: the sky as a local web app.

Serves web/index.html and a small JSON API on 127.0.0.1 only. Every API call must carry the
token from ~/.qosmos/token, which the page receives embedded in its HTML, so another site
open in the same browser cannot drive it. Reading sessions and opening one in the app happen
here; sending a message, archiving and unarchiving need the app itself, so they are written
to a queue that the Qosmos mod (running inside a Claude Code session) carries out.

  server.py [--port N]      serve in the foreground
  server.py --daemon        serve in the background, unless one already answers
  server.py claim ID        (for the mod) make this session the home one
  server.py take [ID]       (for the mod) print and clear the queued jobs, if ID is the home
  server.py done JSON       (for the mod) store results: [{"job": ..., "ok": ..., "text": ...}]
"""
import http.server
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(os.path.dirname(HERE), "web")
HOME = os.path.expanduser("~/.qosmos")
QUEUE = os.path.join(HOME, "kuyruk.jsonl")
RESULTS = os.path.join(HOME, "sonuc.json")
ARCHIVE = os.path.join(HOME, "mesajlar.json")
READ = os.path.join(HOME, "okundu.json")
TOKEN_FILE = os.path.join(HOME, "token")
SESSION = os.path.join(HOME, "oturum")
PORT = 47321
KEEP = 1000
LOCK = threading.Lock()


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
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
    r = subprocess.run([sys.executable, os.path.join(HERE, script), *args], capture_output=True, text=True, timeout=timeout)
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
        data["results"] = load(RESULTS, {})
        data["at"] = int(time.time() * 1000)
        SCAN.update(at=time.time(), data=data)
        return data


def enqueue(job):
    job = {**job, "job": secrets.token_hex(6), "at": int(time.time() * 1000)}
    with LOCK, open(QUEUE, "a") as f:
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
        return host in ("127.0.0.1", "localhost") and secrets.compare_digest(self.headers.get("X-Qosmos-Token") or "", TOKEN)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read().replace("__QOSMOS_TOKEN__", TOKEN)
            return self.reply(200, html.encode(), "text/html")
        if not url.path.startswith("/api/"):
            return self.reply(404, {"error": "yok"})
        if not self.allowed():
            return self.reply(403, {"error": "izin yok"})
        q = urllib.parse.parse_qs(url.query)
        try:
            if url.path == "/api/scan":
                return self.reply(200, scan())
            if url.path == "/api/konu":
                sid = q.get("id", [""])[0]
                if sid == "home":  # the Qosmos home session, by its transcript id
                    sid = open(SESSION).read().strip() if os.path.exists(SESSION) else ""
                elif not sid.startswith("local_"):
                    sid = ""
                return self.reply(200, json.loads(run("konu.py", sid)))
        except Exception as err:  # noqa: BLE001 - the page shows it
            return self.reply(500, {"error": str(err)[:300]})
        return self.reply(404, {"error": "yok"})

    def do_POST(self):
        if not self.allowed():
            return self.reply(403, {"error": "izin yok"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.reply(400, {"error": "bozuk istek"})
        path = urllib.parse.urlparse(self.path).path
        sid = str(body.get("id") or "")
        if sid and not (sid.startswith("local_") and sid.replace("-", "").replace("_", "").isalnum()):
            return self.reply(400, {"error": "geçersiz konu"})
        try:
            if path == "/api/open":
                subprocess.run(["/usr/bin/open", f"claude://claude.ai/epitaxy/{sid}"], timeout=10, check=True)
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
                    return self.reply(400, {"error": "boş mesaj"})
                return self.reply(200, {"job": enqueue({"kind": "send", "id": sid or "self", "text": text})})
            if path == "/api/close":
                sess = {k["id"]: k for k in scan()["sessions"]}
                k = sess.get(sid)
                run("scan.py", "--gizle", sid, (k or {}).get("proj", ""), (k or {}).get("title", sid))
                job = enqueue({"kind": "archive", "id": sid}) if k and k["acc"] == scan()["current"] else None
                SCAN["at"] = 0
                return self.reply(200, {"ok": True, "job": job})
            if path == "/api/reopen":
                run("scan.py", "--ac", sid)
                SCAN["at"] = 0
                return self.reply(200, {"ok": True, "job": enqueue({"kind": "unarchive", "id": sid})})
            if path == "/api/ping":
                return self.reply(200, {"job": enqueue({"kind": "ping"})})
        except Exception as err:  # noqa: BLE001
            return self.reply(500, {"error": str(err)[:300]})
        return self.reply(404, {"error": "yok"})


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


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["claim"] and len(args) > 1:
        # The session that ran /qosmos becomes the home: it runs the bridge and gets "self" messages.
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
    if args[:1] == ["done"]:
        done(args[1] if len(args) > 1 else "[]")
        sys.exit(0)
    if "--port" in args:
        PORT = int(args[args.index("--port") + 1])
    if "--daemon" in args:
        if answering(PORT):
            print(f"http://127.0.0.1:{PORT}/ zaten açık")
            sys.exit(0)
        if os.fork():
            time.sleep(0.6)
            print(f"http://127.0.0.1:{PORT}/")
            sys.exit(0)
        os.setsid()
        if os.fork():
            os._exit(0)
        os.makedirs(HOME, exist_ok=True)
        out = open(os.path.join(HOME, "server.log"), "a")
        os.dup2(out.fileno(), 1)
        os.dup2(out.fileno(), 2)
    TOKEN = token()
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
