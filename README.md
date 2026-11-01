# Qosmopol

**The interactive project map for Claude Code** — see every project and session at a glance, and what needs you blinks **red**. Projects are planets, their sessions are moons on thin lines; a session where the agent is working glows **orange**, closed ones turn **grey**. Built for people who run many projects with many open sessions in the Claude desktop app and keep missing the one question that has been waiting for hours.

> Qosmopol is an independent project, not affiliated with or endorsed by Anthropic. "Claude" and "Claude Code" are trademarks of Anthropic, PBC.

## What you get

- **The sky** — every project and session, sized by how busy it is. Red = waiting for you (a question, an approval, a blocked task), orange = the agent is working right now, grey = closed, a white ring = an answer you have not read.
- **A pane beside the chat** — counts, the waiting list, a project tree, the message archive with filters (unread / read / waiting) and a mini mode when the pane is narrow.
- **A full-screen web view** at `http://127.0.0.1:47321/` — the sky opens from *Map* in the sidebar; click any circle to open it: a moon opens the session, a planet opens the project. Opened items sit side by side as columns (up to four). One command bar with a microphone writes to the focused session, or to the Qosmopol home session itself.
- **Close sessions** from anywhere (✕): sessions on the signed-in account are archived in the app, others are hidden from the sky. "Closed" keeps a list with *Reopen*.
- **Old waiting items** can be closed in bulk, after a confirmation.
- **Your own order:** drag projects up and down in the sidebar; the order is kept by the local server, so every browser and the installed app show it. Sessions started without a project folder are listed one by one under *Loose sessions*.

## Install

```
/plugin install qosmopol --marketplace aydinsoy/qosmopol
```

**Before you install: Python 3.9 or newer is required** (nothing else: no model, no packages). On macOS it comes with Apple's Command Line Tools (`xcode-select --install`); on Windows install it from python.org and restart the Claude app. If it is missing, `/qosmopol` says so.

Then, in the Claude Code session you want as the home, run:

```
/qosmopol
```

That session opens the pane, starts the local web server and becomes the **home**: messages you send from the web view to "Qosmopol" arrive there, and it relays your messages, archive and reopen actions to the app. Keep it open (a small pop-out window works well).

## How to use: getting to the map

Once installed, there are four ways in, none of them needs typing an address:

1. **The band above the prompt.** Every Claude Code session shows one line above the message box: *Qosmopol · 3 waiting for you · Open map*. Click **Open map**.
2. **The pane beside the chat.** Type `/` and pick **/qosmopol** from the menu (or type it). The Qosmopol pane opens next to the session; its **Open web view** button opens the map.
3. **The Dock icon.** Install the web view as an app once (see below); after that the Qosmopol icon in the Dock opens it directly.
4. **Inside the web view.** The map is the first column, right of the sidebar. If you closed it, click **Map** in the sidebar's Qosmopol section; it also comes back on every reload. The ⤢ button makes it full screen (Esc leaves). The sidebar folds away with the icon right of the Qosmopol name; the same icon in the first column's header brings it back.

On the map, click a moon to open that session as a column, a planet to open its project. *Open in app* in a column header switches the Claude app to that session.

## Use it as a desktop app

The web view installs like any desktop app, with its own window and Dock icon:

- **Chrome:** open `http://127.0.0.1:47321/`, then ⋮ → *Cast, save, and share* → *Install page as app…*
- **Safari:** open the page, then *File* → *Add to Dock…*

Qosmopol speaks the language you chose in the Claude app (Turkish or English for now; the browser's language when no choice is found).

The microphone works in both (Chrome and Safari speech recognition, Turkish by default).

## Several computers on one map

Running Claude Code on more than one computer (two Macs, a Mac and a Windows PC)? Each Qosmopol sees only its own computer's sessions, because Claude keeps them on that computer's disk. Turn on **Other computers** in the web view's sidebar on each of them and pick the same shared folder (iCloud Drive, Google Drive, Dropbox or OneDrive; Qosmopol suggests the ones it finds):

- Each computer writes a summary of its own sessions to `<folder>/Qosmopol/cihazlar/<device>.json` at most every 2 minutes (every 10 when nothing changed, because a sync service uploads a file only once it stops changing), covering the last 30 days and everything still waiting: titles, status, the waiting question and the Remote Control id. No folder paths, no conversations.
- The others' projects show on the map with the computer's name ("Space Game · MacBook"), and the band above the prompt says "3 waiting for you (+2 on your other computers)".
- Another computer's session cannot be opened in this computer's Claude app. **Open on claude.ai** opens it to read and reply, as long as that session's Remote Control is on.
- It is off until you pick a folder, opens no network port, and the server stays on 127.0.0.1. `QOSMOPOL_SYNC_DIR` sets the folder without the web view.

**Your own projects.** Qosmopol groups sessions by the folder they run in, and Claude's own project names are not open to plugins, so one piece of work can be spread over several planets. Use **Move to project…** in a project's ⋯ menu (a whole planet) or **Move to project** in a session's column (one session) to gather them under a name of your choosing; the groups travel with the summary, so every computer shows the same project. **Take out of this project** undoes it.

The design and what comes next (replying and closing across computers) are in [docs/coklu-bilgisayar-tasarim.md](docs/coklu-bilgisayar-tasarim.md).

## How it works

- `bin/scan.py` reads the desktop app's own session records (`~/Library/Application Support/Claude/claude-code-sessions`). Waiting = the end-of-turn report says the session is blocked on you, or a turn is paused on a permission. Working = the session's transcript was written in the last 90 seconds.
- `bin/konu.py` reads the last turns of a session's transcript for the conversation view.
- `bin/server.py` serves the web view on `127.0.0.1` only. Every API call needs a random token stored in `~/.qosmopol/token` (mode 600) and embedded in the page, so other sites in your browser cannot drive it. Opening a session uses `open claude://…`; sending, archiving and reopening are queued in `~/.qosmopol/` and carried out by the home session's mod.
- State lives in `~/.qosmopol/`: the message archive, read marks, closed sessions, the queue and the server log.

## Requirements and limits

- macOS with the Claude desktop app (Code tab) and Python 3.9 or newer at `/usr/bin/python3` (Apple's Command Line Tools: `xcode-select --install`).
- Windows: the same, with Python 3.9 or newer from python.org (its `py` launcher runs the scripts; restart the Claude app after installing Python so it sees the new PATH). Session records are read from `%APPDATA%\Claude\claude-code-sessions`.
- Another Python can be named with the `QOSMOPOL_PYTHON` environment variable.
- Sessions of other accounts can be seen and hidden, but not archived or messaged from here.
- The microphone uses the browser's speech recognition (Chrome and Safari). Where it is missing, macOS dictation (press 🌐/fn twice) works in the command bar.
- Inside the pane the sky is a picture you cannot click (the app draws it in a sandboxed frame); use the lists, or the web view.

---

## Türkçe

**Qosmopol**, Claude masaüstü uygulamasındaki bütün projeleri ve konuları tek bir siyah haritada gösterir. Senden bir şey bekleyen konu kırmızı yanıp söner, ajanın çalıştığı konu turuncu yanar, kapanmış konular gri olur. Kurduktan sonra ana oturumda `/qosmopol` yaz. Tam ekran hâli `http://127.0.0.1:47321/` adresinde: dairelere basınca konu ya da proje sağda sütun olarak açılır, tek yazma çubuğu ve mikrofonla oradan yönetirsin.

**Birden çok bilgisayar:** Her bilgisayarda web görünümünün sol menüsündeki **Diğer bilgisayarlar**'ı aç ve aynı ortak klasörü seç (iCloud Drive, Google Drive, Dropbox ya da OneDrive). Diğer bilgisayarların projeleri haritada bilgisayarın adıyla görünür; konularını **claude.ai'de aç** ile okuyup cevaplarsın.

**Haritaya nasıl geçilir:** her Claude Code konusunda yazma kutusunun hemen üstündeki şeritte (*Qosmopol · 3 bekliyor · Haritayı aç*) **Haritayı aç**'a bas; ya da `/` menüsünden **/qosmopol**'u seçip açılan paneldeki **Open web view** düğmesini, ya da Dock'a eklediğin Qosmopol simgesini kullan. Sayfada harita ilk sütundur; kapattıysan soldaki menüde **Harita**'ya bas, sayfa yenilenince de geri gelir. Gereken tek şey Python 3.9 ya da daha yenisi.

## License

MIT. See [LICENSE](LICENSE). The name "Qosmopol" is not covered by the license.
