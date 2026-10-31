# Qosmos

**All your Claude Code projects and sessions on one sky.** Projects are planets, their sessions are moons on thin lines. A session that needs you blinks **red**, one where the agent is working glows **orange**, closed ones turn **grey**. Built for people who run many projects with many open sessions in the Claude desktop app and keep missing the one question that has been waiting for hours.

> Qosmos is an independent project, not affiliated with or endorsed by Anthropic. "Claude" and "Claude Code" are trademarks of Anthropic, PBC.

## What you get

- **The sky** — every project and session, sized by how busy it is. Red = waiting for you (a question, an approval, a blocked task), orange = the agent is working right now, grey = closed, a white ring = an answer you have not read.
- **A pane beside the chat** — counts, the waiting list, a project tree, the message archive with filters (unread / read / waiting) and a mini mode when the pane is narrow.
- **A full-screen web view** at `http://127.0.0.1:47321/` — click any circle to open it: a moon opens the session, a planet opens the project. Opened items sit side by side as columns (up to four). One command bar with a microphone writes to the focused session, or to the Qosmos home session itself.
- **Close sessions** from anywhere (✕): sessions on the signed-in account are archived in the app, others are hidden from the sky. "Closed" keeps a list with *Reopen*.
- **Old waiting items** can be closed in bulk, after a confirmation.

## Install

```
/plugin install qosmos --marketplace aydinsoy/qosmos
```

The repository is private: you need access to it and GitHub set up on your computer (`gh auth login`).

Then, in the Claude Code session you want as the home, run:

```
/qosmos
```

That session opens the pane, starts the local web server and becomes the **home**: messages you send from the web view to "Qosmos" arrive there, and it relays your messages, archive and reopen actions to the app. Keep it open (a small pop-out window works well).

## Use it as a desktop app

The web view installs like any desktop app, with its own window and Dock icon:

- **Chrome:** open `http://127.0.0.1:47321/`, then ⋮ → *Cast, save, and share* → *Install page as app…*
- **Safari:** open the page, then *File* → *Add to Dock…*

The microphone works in both (Chrome and Safari speech recognition, Turkish by default).

## How it works

- `bin/scan.py` reads the desktop app's own session records (`~/Library/Application Support/Claude/claude-code-sessions`). Waiting = the end-of-turn report says the session is blocked on you, or a turn is paused on a permission. Working = the session's transcript was written in the last 90 seconds.
- `bin/konu.py` reads the last turns of a session's transcript for the conversation view.
- `bin/server.py` serves the web view on `127.0.0.1` only. Every API call needs a random token stored in `~/.qosmos/token` (mode 600) and embedded in the page, so other sites in your browser cannot drive it. Opening a session uses `open claude://…`; sending, archiving and reopening are queued in `~/.qosmos/` and carried out by the home session's mod.
- State lives in `~/.qosmos/`: the message archive, read marks, closed sessions, the queue and the server log.

## Requirements and limits

- macOS with the Claude desktop app (Code tab) and `python3`.
- Sessions of other accounts can be seen and hidden, but not archived or messaged from here.
- The microphone uses the browser's speech recognition (Chrome and Safari). Where it is missing, macOS dictation (press 🌐/fn twice) works in the command bar.
- Inside the pane the sky is a picture you cannot click (the app draws it in a sandboxed frame); use the lists, or the web view.

---

## Türkçe

**Qosmos**, Claude masaüstü uygulamasındaki bütün projeleri ve konuları tek bir siyah haritada gösterir. Senden bir şey bekleyen konu kırmızı yanıp söner, ajanın çalıştığı konu turuncu yanar, kapanmış konular gri olur. Kurduktan sonra ana oturumda `/qosmos` yaz. Tam ekran hâli `http://127.0.0.1:47321/` adresinde: dairelere basınca konu ya da proje sağda sütun olarak açılır, tek yazma çubuğu ve mikrofonla oradan yönetirsin.

## License

Proprietary, all rights reserved. See [LICENSE](LICENSE).
