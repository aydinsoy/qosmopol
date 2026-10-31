import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Gorunum, Konu, Mesaj, Satir, Tarama } from '../types'
import { DAY, ORANGE, RED, running, accLabel, ago, cut, msgUnread, sky, unread, visible, waiting } from './sky.ts'

// Qosmopol: every Code session on this Mac as a black sky. A project is a white planet, its
// sessions are moons tied to it by a thin line; a session waiting for the owner blinks orange.
// Source of truth is the app's own session files (bin/scan.py); end-of-turn reports are kept
// as a filtered message archive in $.store so they outlive this session.

const PANE = 'qosmopol'
const TITLE = 'Qosmopol'
const EVERY_MS = 30_000
const KEEP = 1000

const tarama = atom({ plugin: 'qosmopol', key: 'tarama' } as const, { at: 0, current: '', accounts: [], sessions: [] } as Tarama, { shape: 'tarama-1' })
const mesajlar = atom({ plugin: 'qosmopol', key: 'mesajlar' } as const, [] as Mesaj[], { shape: 'mesajlar-1' })
const okundu = atom({ plugin: 'qosmopol', key: 'okundu' } as const, {} as Record<string, number>, { shape: 'okundu-1' })
const konusma = atom({ plugin: 'qosmopol', key: 'konusma' } as const, {} as Record<string, Satir[]>, { shape: 'konusma-1' })
const gorunum = atom(
  { plugin: 'qosmopol', key: 'gorunum' } as const,
  { tab: 'harita', days: 7, filter: 'hepsi', proj: '', open: [], sel: '', limit: 40 } as Gorunum,
  { shape: 'gorunum-1' },
)

let stopTimer: (() => void) | undefined
let stopBridge: (() => void) | undefined
let bridging = false
const WEB = 'http://127.0.0.1:47321/'
const server = ($: EngineInterface, ...args: string[]) =>
  $.process.run(['/usr/bin/python3', `${$.plugin.root}/bin/server.py`, ...args], { timeoutMs: 15_000 })

// The web page (bin/server.py) cannot reach the app: it queues what needs it, and the home
// session's mod carries each job out here and writes the result back for the page to show.
async function bridge($: EngineInterface) {
  if (bridging) return
  bridging = true
  try {
    const r = await server($, 'take', String(await $.session.id()))
    let jobs: any[] = []
    try {
      jobs = JSON.parse(r.stdout)
    } catch {
      return
    }
    if (!Array.isArray(jobs) || !jobs.length) return
    const out: { job: string; ok: boolean; text: string }[] = []
    for (const j of jobs) {
      try {
        if (j.kind === 'ping') out.push({ job: j.job, ok: true, text: 'bridge is working' })
        else if (j.kind === 'send' && j.id === 'self') {
          // Not awaited: a submitted prompt resolves only once its turn has run, and the bridge must stay free.
          void $.prompt.submit({ text: String(j.text) })
          out.push({ job: j.job, ok: true, text: 'delivered to the Qosmopol session (runs once it is idle)' })
        } else if (j.kind === 'set') {
          // The app refuses a session re-pricing its own turns: the home session changes only its mode from here.
          if (j.id === 'self' && j.what !== 'mode') {
            out.push({ job: j.job, ok: false, text: "the home session's model and effort change in the Claude app's menu" })
            continue
          }
          const tool = { model: 'set_session_model', effort: 'set_session_effort', mode: 'set_session_permission_mode' }[j.what as string]
          if (!tool) {
            out.push({ job: j.job, ok: false, text: 'unknown setting' })
            continue
          }
          const res = await $.mcp.call('ccd_session_mgmt', tool, { session_id: j.id, [j.what]: String(j.value) })
          out.push({ job: j.job, ok: !res.isError, text: cut((res.content ?? []).map((c: any) => c.text ?? '').join(' '), 300) })
        } else {
          const tool = { send: 'send_message', archive: 'archive_session', unarchive: 'unarchive_session' }[j.kind as string]
          if (!tool) {
            out.push({ job: j.job, ok: false, text: 'unknown job' })
            continue
          }
          const args = j.kind === 'send' ? { session_id: j.id, message: String(j.text) } : j.kind === 'archive' ? { session_id: j.id, reason: 'Closed from the Qosmopol web view' } : { session_id: j.id }
          const res = await $.mcp.call('ccd_session_mgmt', tool, args)
          out.push({ job: j.job, ok: !res.isError, text: cut((res.content ?? []).map((c: any) => c.text ?? '').join(' '), 300) })
        }
      } catch (err) {
        out.push({ job: j.job, ok: false, text: cut(String(err), 300) })
      }
    }
    await server($, 'done', JSON.stringify(out))
    void scan($)
  } finally {
    bridging = false
  }
}

async function scan($: EngineInterface) {
  try {
    const me = await $.session.id()
    const r = await $.process.run(['/usr/bin/python3', `${$.plugin.root}/bin/scan.py`, String(me)], { timeoutMs: 60_000 })
    if (r.exitCode !== 0) throw new Error(r.stderr.slice(0, 300) || `exit ${r.exitCode}`)
    const d = JSON.parse(r.stdout) as Omit<Tarama, 'at'>
    const now = await $.clock.now()
    await update($, tarama, () => ({ ...d, at: now }))
    const known = new Set((await read($, mesajlar)).map(m => m.id))
    const fresh: Mesaj[] = d.sessions
      .filter(k => k.sumId && !known.has(k.sumId) && (k.cat || k.need || k.detail))
      .map(k => ({ id: k.sumId, sid: k.id, proj: k.proj, title: k.title, acc: k.acc, cat: k.cat, text: cut(k.need || k.detail || k.cat, 500), at: k.last, read: false }))
    if (fresh.length) {
      const list = await update($, mesajlar, old => [...old, ...fresh].sort((a, b) => a.at - b.at).slice(-KEEP))
      await $.store.set('mesajlar', list)
      const newWait = fresh.filter(m => m.cat === 'blocked' && now - m.at < 10 * 60_000)
      if (known.size && newWait.length) $.ui.toast(`Qosmopol: ${newWait[0].proj} · ${cut(newWait[0].title, 50)} seni bekliyor`)
    }
    const nWait = d.sessions.filter(waiting).filter(k => now - k.last < 30 * DAY).length
    for (const c of (await read($, gorunum)).cols ?? []) if (c.startsWith('k:')) await loadTalk($, c.slice(2))
    $.ui.status(nWait ? `● ${nWait} waiting for you` : undefined)
  } catch (err) {
    await update($, tarama, t => ({ ...t, error: String(err).slice(0, 300) }))
  }
}

// Closing drops a session from the sky at once; one on this account is also archived in the app,
// so the sidebar empties too. Another account's session can only be hidden from here.
async function closeTopics($: EngineInterface, ks: Konu[], current: string) {
  let archived = 0
  const notes: string[] = []
  for (const k of ks) {
    await $.process.run(['/usr/bin/python3', `${$.plugin.root}/bin/scan.py`, '--gizle', k.id, k.proj, k.title], { timeoutMs: 10_000 })
    if (k.acc !== current) continue
    try {
      const r = await $.mcp.call('ccd_session_mgmt', 'archive_session', { session_id: k.id, reason: 'Closed from the Qosmopol pane' })
      if (r.isError) notes.push(cut((r.content ?? []).map((c: any) => c.text ?? '').join(' '), 90))
      else archived++
    } catch (err) {
      notes.push(cut(String(err), 90))
    }
  }
  $.ui.toast(`${ks.length} closed · ${archived} archived${notes.length ? ` · not archived: ${notes[0]}` : ''}`)
  await scan($)
}

// The last turns of a session's own transcript, so a column reads like the conversation itself.
async function loadTalk($: EngineInterface, id: string) {
  try {
    const r = await $.process.run(['/usr/bin/python3', `${$.plugin.root}/bin/konu.py`, id], { timeoutMs: 20_000 })
    const d = JSON.parse(r.stdout)
    const msgs: Satir[] = Array.isArray(d?.msgs) ? d.msgs : []
    await update($, konusma, all => ({ ...all, [id]: msgs }))
  } catch {
    await update($, konusma, all => ({ ...all, [id]: [] }))
  }
}

async function reopen($: EngineInterface, id: string) {
  await $.process.run(['/usr/bin/python3', `${$.plugin.root}/bin/scan.py`, '--ac', id], { timeoutMs: 10_000 })
  try {
    await $.mcp.call('ccd_session_mgmt', 'unarchive_session', { session_id: id })
  } catch {
    // Only hidden, or on another account: nothing to unarchive.
  }
  await scan($)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'qosmopol', description: 'Open all projects and sessions on the Qosmopol sky' })
    const kept = await $.store.get('mesajlar')
    if (Array.isArray(kept) && (await read($, mesajlar)).length === 0) await update($, mesajlar, () => kept as Mesaj[])
    const keptRead = await $.store.get('okundu')
    if (keptRead && typeof keptRead === 'object') await update($, okundu, o => ({ ...(keptRead as Record<string, number>), ...o }))
    stopTimer?.()
    const timer = $.clock.every(EVERY_MS, () => void scan($))
    stopTimer = () => timer.cancel()
    void scan($)
    stopBridge?.()
    const bt = $.clock.every(2500, () => void bridge($))
    stopBridge = () => bt.cancel()
    void server($, '--daemon')
    // Only the home session (the last one that ran /qosmopol) opens the pane by itself.
    const home = (await server($, 'home')).stdout.trim()
    if (home && home === String(await $.session.id())) void $.ui.open({ id: PANE, title: TITLE })
    return next(e)
  })

  on('command.run', { command: 'qosmopol' }, async $ => {
    await server($, 'claim', String(await $.session.id()))
    await server($, '--daemon')
    await $.ui.open({ id: PANE, title: TITLE })
    return { text: `Qosmopol is open. Full-screen web view: ${WEB} (this session is now Qosmopol's home session: what you write in the web view comes here).` }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e) as any
    const { Box, Text, Button, Svg } = els
    const Input = els.Input
    const Select = els.Select
    const t = await read($, tarama)
    const v = await read($, gorunum)
    const readAt = await read($, okundu)
    const log = await read($, mesajlar)
    const talks = await read($, konusma)
    const now = Date.now()
    const byId = new Map(t.sessions.map(k => [k.id, k] as const))
    const shown = visible(t.sessions, v.days, now)
    const groups = new Map<string, Konu[]>()
    for (const k of shown) groups.set(k.proj, [...(groups.get(k.proj) ?? []), k])
    const order = [...groups.entries()].sort((a, b) => b[1].filter(waiting).length - a[1].filter(waiting).length || Math.max(...b[1].map(k => k.last)) - Math.max(...a[1].map(k => k.last)))
    const waitList = shown.filter(waiting).sort((a, b) => b.last - a.last)
    const old = waitList.filter(k => now - k.last > 7 * DAY)
    const closed = t.hidden ?? []
    const nNew = shown.filter(k => !waiting(k) && unread(k, readAt)).length
    const cols = e.props.bodyColumns ?? 80
    const set = (fn: (g: Gorunum) => Gorunum) => update($, gorunum, fn)
    const markRead = async (sid: string) => {
      const o = await update($, okundu, r => ({ ...r, [sid]: Date.now() }))
      await $.store.set('okundu', o)
    }
    const openSession = async (k: Konu) => {
      await markRead(k.id)
      if (k.acc !== t.current) {
        $.ui.toast(`This session belongs to another account (${accLabel(t, k.acc)}); it opens once you sign in with it.`)
      }
      const r = await $.process.run(['/usr/bin/open', `claude://claude.ai/epitaxy/${k.id}`], { timeoutMs: 10_000 })
      if (r.exitCode !== 0) $.ui.toast(`Could not open: ${r.stderr.slice(0, 120)}`)
    }
    const send = async (k: Konu, text: string) => {
      if (!text.trim()) return
      try {
        const r = await $.mcp.call('ccd_session_mgmt', 'send_message', { session_id: k.id, message: text })
        const said = (r.content ?? []).map((c: any) => c.text ?? '').join(' ')
        $.ui.toast(r.isError ? `Could not send: ${cut(said, 160)}` : `Sent → ${cut(k.title, 40)}`)
        if (!r.isError) {
          await markRead(k.id)
          await update($, konusma, all => ({ ...all, [k.id]: [...(all[k.id] ?? []), { role: 'sen', text }] }))
        }
      } catch (err) {
        $.ui.toast(`Could not send: ${cut(String(err), 160)}`)
      }
    }

    const dot = (k: Konu) => (waiting(k) ? <Text color={RED}>●</Text> : running(k) ? <Text color={ORANGE}>●</Text> : unread(k, readAt) ? <Text color="#ffffff">●</Text> : <Text dimColor>○</Text>)
    // Wide panes split in two: a sidebar (counts, project tree, map thumbnail) and the opened item on the right.
    const wide = cols >= 110
    const leftCols = wide ? Math.max(34, Math.round(cols * 0.34)) : cols
    const rightCols = wide ? cols - leftCols - 3 : cols
    const cols0 = v.cols ?? []
    const openCols = cols0.filter(c => c === 'harita' || (c.startsWith('k:') ? byId.has(c.slice(2)) : groups.has(c.slice(2))))
    const MAXCOLS = wide ? 4 : 2
    const openCol = (c: string, sel?: string) => set(g => {
      const cur = g.cols ?? []
      return { ...g, sel: sel ?? g.sel, cols: cur.includes(c) ? cur : [...cur, c].slice(-MAXCOLS) }
    })
    const closeCol = (c: string) => set(g => ({ ...g, cols: (g.cols ?? []).filter(x => x !== c), sel: c === `k:${g.sel}` ? '' : g.sel }))
    const pick = (k: Konu) => {
      void loadTalk($, k.id)
      return openCol(`k:${k.id}`, k.id)
    }
    const closeBtn = (k: Konu, where = '') => (
      <Button key={where ? `x-${where}-${k.id}` : `x-${k.id}`} plain onPress={() => closeTopics($, [k], t.current)}>
        <Text dimColor>✕</Text>
      </Button>
    )
    const openWeb = async () => {
      await server($, '--daemon')
      const r = await $.process.run(['/usr/bin/open', WEB], { timeoutMs: 10_000 })
      if (r.exitCode !== 0) $.ui.toast(`Could not open: ${r.stderr.slice(0, 120)}`)
    }
    const toInbox = <Button key="kapat" label="Close all" onPress={() => set(g => ({ ...g, sel: '', cols: [] }))} />
    const row = (k: Konu, prefix: string) => (
      <Box key={`r-${prefix}-${k.id}`} flexDirection="row" gap={1}>
        {closeBtn(k, 't')}
        <Button key={`${prefix}-${k.id}`} plain onPress={() => pick(k)}>
          {dot(k)} <Text weight={k.id === v.sel ? 'bold' : 'regular'}>{cut(k.title, Math.max(16, leftCols - 14))}</Text> <Text dimColor>{ago(k.last, now)}</Text>
        </Button>
      </Box>
    )

    const header = (
      <Box flexDirection="column" marginBottom={1}>
        <Text>
          <Text color={RED} weight="bold">{waitList.length} waiting for you</Text> · <Text color={ORANGE}>{shown.filter(running).length} running</Text> · {nNew} unread
        </Text>
        <Text dimColor>
          {shown.length} sessions · {groups.size} projects · {t.at ? `scanned ${ago(t.at, now)} ago` : 'scanning…'}
          {t.error ? ` · HATA: ${t.error}` : ''}
        </Text>
        <Box flexDirection="row" gap={1} flexWrap="wrap" marginTop={1}>
          {[1, 7, 30, 0].map(d => (
            <Button key={`gun-${d}`} variant={v.days === d ? 'primary' : 'secondary'} label={d === 0 ? 'All' : `${d} ${d === 1 ? 'day' : 'days'}`} onPress={() => set(g => ({ ...g, days: d }))} />
          ))}
          <Button key="yenile" label="Yenile" onPress={() => scan($)} />
          <Button key="web" variant="primary" label="Open web view" onPress={() => openWeb()} />
        </Box>
      </Box>
    )

    const tree = (
      <Box flexDirection="column">
        <Text weight="bold">Projeler</Text>
        {order.map(([name, list]) => {
          const isOpen = v.open.includes(name)
          const w = list.filter(waiting).length
          const r = list.filter(running).length
          const n = list.filter(k => !waiting(k) && unread(k, readAt)).length
          return (
            <Box key={`p-${name}`} flexDirection="column">
              <Button key={`pb-${name}`} plain onPress={() => set(g => {
                const c = `p:${name}`
                const cur = g.cols ?? []
                if (cur.includes(c) && g.open.includes(name)) return { ...g, cols: cur.filter(x => x !== c), open: g.open.filter(x => x !== name) }
                return { ...g, cols: cur.includes(c) ? cur : [...cur, c].slice(-MAXCOLS), open: g.open.includes(name) ? g.open : [...g.open, name] }
              })}>
                {isOpen ? '▾' : '▸'} <Text weight="bold">{name}</Text> {w ? <Text color={RED}>●{w}</Text> : ''} {r ? <Text color={ORANGE}>●{r}</Text> : ''} {n ? <Text color="#ffffff">○{n}</Text> : ''} <Text dimColor>{list.length}</Text>
              </Button>
              {isOpen && (
                <Box flexDirection="column" paddingLeft={2}>
                  {[...list].sort((a, b) => b.last - a.last).map(k => row(k, name))}
                </Box>
              )}
            </Box>
          )
        })}
        {closed.length > 0 && (
          <Box flexDirection="column" marginTop={1}>
            <Button key="pb-__kapali" plain onPress={() => set(g => ({ ...g, open: g.open.includes('__kapali') ? g.open.filter(x => x !== '__kapali') : [...g.open, '__kapali'] }))}>
              {v.open.includes('__kapali') ? '▾' : '▸'} <Text weight="bold">Closed</Text> <Text dimColor>{closed.length}</Text>
            </Button>
            {v.open.includes('__kapali') && [...closed].reverse().map(h => (
              <Box key={`k-${h.id}`} flexDirection="row" gap={1} paddingLeft={2}>
                <Button key={`geri-${h.id}`} label="Reopen" onPress={() => reopen($, h.id)} />
                <Text dimColor>{h.proj} · {cut(h.title, Math.max(16, leftCols - 24))}</Text>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    )

    const svg = sky(groups, now, readAt, v.sel)
    // The map's frame has no height of its own: size it from the viewBox so it keeps its shape.
    const box = /viewBox="[-\d.]+ [-\d.]+ (\d+) (\d+)"/.exec(svg)
    const ratio = box ? +box[2] / +box[1] : 0.6
    const alt = `${groups.size} projects, ${shown.length} sessions, ${waitList.length} waiting for you`
    const thumbW = Math.max(200, Math.min(520, leftCols * 8 - 16))
    const thumb = svg && (
      <Box flexDirection="column" marginTop={1}>
        <Box backgroundColor="#181818">
          <Svg source={svg} alt={alt} width={thumbW} height={Math.round(thumbW * ratio)} isInteractive />
        </Box>
        <Button key="harita-buyut" plain onPress={() => (openCols.includes('harita') ? closeCol('harita') : openCol('harita'))}>
          <Text dimColor>{openCols.includes('harita') ? '⤡ Close the big map' : '⤢ Enlarge the map'}</Text>
        </Button>
      </Box>
    )

    const legend = <Text dimColor>Blinking red: something needs you · orange: agent working · grey: closed · white ring: unread reply. Hover for the title.</Text>

    const target = v.sel && openCols.includes(`k:${v.sel}`) ? byId.get(v.sel) : undefined
    // One command bar: it writes to the focused topic column, or to this Qosmopol session when none is focused.
    const bar = Input && (
      <Box flexDirection="column" marginTop={1}>
        <Text dimColor>{target ? `→ ${target.proj} · ${cut(target.title, Math.max(16, leftCols - 14))}` : '→ Qosmopol (this session, Claude)'}</Text>
        <Input key={`bar-${target?.id ?? 'ben'}`} rows={2} placeholder="Type or dictate (press 🌐 twice)" submitLabel="Send" onSubmit={(text: string) => {
          if (!text.trim()) return
          if (target) void send(target, text)
          else void $.prompt.submit({ text })
        }} />
      </Box>
    )

    const n = openCols.length
    const colCols = Math.max(24, Math.floor((wide ? rightCols : cols) / Math.max(1, wide ? n : 1)) - 4)
    const column = (c: string) => {
      const k = c.startsWith('k:') ? byId.get(c.slice(2)) : undefined
      const pname = c.startsWith('p:') ? c.slice(2) : ''
      const focused = !!k && k.id === v.sel
      const title = k ? k.title : pname || 'Map'
      let body
      if (k) {
        const talk = (talks[k.id] ?? []).slice(-8)
        const history = log.filter(m => m.sid === k.id).reverse().slice(0, 5)
        body = (
          <Box flexDirection="column">
            <Text dimColor>{k.proj} · {accLabel(t, k.acc)} · {ago(k.last, now)} ago</Text>
            {k.need ? <Text color={RED}>Waiting: {k.need}</Text> : running(k) ? <Text color={ORANGE}>Agent working…</Text> : k.detail ? <Text>{k.detail}</Text> : null}
            <Box flexDirection="row" gap={1} marginY={1} flexWrap="wrap">
              <Button key={`yaz-${k.id}`} variant={focused ? 'primary' : 'secondary'} label={focused ? 'The bar writes here' : 'Write here'} onPress={() => set(g => ({ ...g, sel: k.id }))} />
              <Button key={`ac-${k.id}`} label="Open in app" onPress={() => openSession(k)} />
              <Button key={`ok-${k.id}`} label="Mark read" onPress={() => markRead(k.id)} />
              <Button key={`kk-${k.id}`} label={k.acc === t.current ? 'Close session (archive)' : 'Close session (hide)'} onPress={async () => {
                await closeCol(c)
                await closeTopics($, [k], t.current)
              }} />
            </Box>
            <Text weight="bold">Conversation</Text>
            {talk.length === 0 && history.length === 0 && <Text dimColor>{k.id in talks ? 'No transcript on this Mac (another account or the cloud).' : 'Loading…'}</Text>}
            {talk.length === 0 && history.map(m => (
              <Box key={`h-${m.id}`} flexDirection="column" marginTop={1}>
                <Text dimColor>{ago(m.at, now)} ago · summary</Text>
                <Text>{m.text}</Text>
              </Box>
            ))}
            {talk.map((m, i) => (
              <Box key={`c-${k.id}-${i}`} flexDirection="column" marginTop={1}>
                {m.role === 'sen' ? <Text color="#4da3ff" weight="bold">Sen</Text> : <Text dimColor weight="bold">Claude</Text>}
                <Text>{cut(m.text, colCols * 14)}</Text>
              </Box>
            ))}
          </Box>
        )
      } else if (pname) {
        const list = [...(groups.get(pname) ?? [])].sort((a, b) => Number(waiting(b)) - Number(waiting(a)) || b.last - a.last)
        body = (
          <Box flexDirection="column">
            <Text dimColor>
              {list.length} sessions · {list.filter(waiting).length} waiting for you · {list.filter(running).length} running
            </Text>
            {list.map(k2 => (
              <Box key={`pr-${k2.id}`} flexDirection="column" marginTop={1}>
                <Box flexDirection="row" gap={1}>
                  {closeBtn(k2, 'p')}
                  <Button key={`pr-${pname}-${k2.id}`} plain onPress={() => pick(k2)}>
                    {dot(k2)} <Text weight="bold">{cut(k2.title, Math.max(16, colCols - 16))}</Text> <Text dimColor>{ago(k2.last, now)}</Text>
                  </Button>
                </Box>
                {waiting(k2) ? <Text color={RED}>{cut(k2.need || k2.detail, colCols * 2)}</Text> : <Text dimColor>{cut(k2.detail || 'No summary.', colCols * 2)}</Text>}
              </Box>
            ))}
          </Box>
        )
      } else {
        const bigW = Math.min(2400, colCols * 8)
        body = (
          <Box flexDirection="column">
            <Box backgroundColor="#181818">
              <Svg source={svg} alt={alt} width={bigW} height={Math.max(240, Math.min(1600, Math.round(bigW * ratio)))} isInteractive />
            </Box>
            {legend}
            <Button key="kucult" label="Shrink" onPress={() => closeCol('harita')} />
          </Box>
        )
      }
      return (
        <Box key={`col-${c}`} flexDirection="column" width={wide ? `${Math.floor(100 / n) - 1}%` : '100%'} borderStyle="round" borderColor={focused ? '#4da3ff' : k && waiting(k) ? RED : 'gray'} paddingX={1} marginBottom={1}>
          <Box flexDirection="row" justifyContent="space-between">
            <Button key={`ct-${c}`} plain onPress={() => (k ? set(g => ({ ...g, sel: k.id })) : undefined)}>
              {k ? dot(k) : ''} <Text weight="bold">{cut(title, colCols - 6)}</Text>
            </Button>
            <Button key={`cx-${c}`} plain onPress={() => closeCol(c)}>
              <Text dimColor>✕</Text>
            </Button>
          </Box>
          {body}
        </Box>
      )
    }

    let right
    if (n > 0) {
      right = (
        <Box flexDirection="column">
          <Box flexDirection="row" gap={1} marginBottom={1}>
            {toInbox}
            <Text dimColor>{n} columns open · at most {MAXCOLS}</Text>
          </Box>
          <Box flexDirection={wide ? 'row' : 'column'} gap={1}>
            {openCols.map(column)}
          </Box>
        </Box>
      )
    } else {
      const tabs = (
        <Box flexDirection="row" gap={1} flexWrap="wrap" marginBottom={1}>
          <Button key="t-harita" variant={v.tab === 'harita' ? 'primary' : 'secondary'} label={`Bekleyenler (${waitList.length})`} onPress={() => set(g => ({ ...g, tab: 'harita' }))} />
          <Button key="t-mesaj" variant={v.tab === 'mesajlar' ? 'primary' : 'secondary'} label={`Messages (${log.filter(m => msgUnread(m, byId, readAt)).length} new)`} onPress={() => set(g => ({ ...g, tab: 'mesajlar' }))} />
        </Box>
      )
      if (v.tab === 'mesajlar') {
        const projs = [...new Set(log.map(m => m.proj))].sort()
        const list = log
          .filter(m => !v.proj || m.proj === v.proj)
          .filter(m => {
            const u = msgUnread(m, byId, readAt)
            if (v.filter === 'okunmamis') return u
            if (v.filter === 'okunmus') return !u
            if (v.filter === 'bekleyen') return m.cat === 'blocked'
            return true
          })
          .reverse()
        right = (
          <Box flexDirection="column">
            {tabs}
            <Box flexDirection="row" gap={1} flexWrap="wrap" marginBottom={1}>
              {(['hepsi', 'okunmamis', 'okunmus', 'bekleyen'] as const).map(f => (
                <Button key={`f-${f}`} variant={v.filter === f ? 'primary' : 'secondary'} label={{ hepsi: 'All', okunmamis: 'Unread', okunmus: 'Read', bekleyen: 'Waiting' }[f]} onPress={() => set(g => ({ ...g, filter: f, limit: 40 }))} />
              ))}
              {Select && (
                <Select key="proj" label="Project" value={v.proj} options={[{ value: '', label: 'All projects' }, ...projs.map(p => ({ value: p, label: p }))]} onSelect={(p: string) => set(g => ({ ...g, proj: p, limit: 40 }))} />
              )}
            </Box>
            {list.length === 0 && <Text dimColor>Bu filtrede mesaj yok.</Text>}
            {list.slice(0, v.limit).map(m => {
              const u = msgUnread(m, byId, readAt)
              return (
                <Button key={`m-${m.id}`} plain onPress={async () => {
                  await update($, mesajlar, all => all.map(x => (x.id === m.id ? { ...x, read: true } : x))).then(all => $.store.set('mesajlar', all))
                  const k = byId.get(m.sid)
                  if (k) await pick(k)
                }}>
                  {m.cat === 'blocked' ? <Text color={RED}>●</Text> : u ? <Text color="#ffffff">●</Text> : <Text dimColor>○</Text>} <Text weight={u ? 'bold' : 'regular'}>{m.proj} · {cut(m.title, 50)}</Text> <Text dimColor>{ago(m.at, now)}</Text> — <Text dimColor={!u}>{cut(m.text, Math.max(40, rightCols * 2))}</Text>
                </Button>
              )
            })}
            {list.length > v.limit && <Button key="daha" label={`Daha fazla (${list.length - v.limit})`} onPress={() => set(g => ({ ...g, limit: g.limit + 40 }))} />}
          </Box>
        )
      } else {
        right = (
          <Box flexDirection="column">
            {tabs}
            {waitList.length === 0 && <Text dimColor>Nothing is waiting for you.</Text>}
            {old.length > 0 && (
              <Box flexDirection="row" gap={1} flexWrap="wrap" marginBottom={1}>
                {v.onay !== 'eski' && <Button key="eski" label={`Close older than 7 days (${old.length})`} onPress={() => set(g => ({ ...g, onay: 'eski' }))} />}
                {v.onay === 'eski' && <Button key="eski-onay" variant="primary" label={`Yes, close ${old.length}`} onPress={async () => { await set(g => ({ ...g, onay: '' })); await closeTopics($, old, t.current) }} />}
                {v.onay === 'eski' && <Button key="eski-vazgec" label="Cancel" onPress={() => set(g => ({ ...g, onay: '' }))} />}
              </Box>
            )}
            {waitList.map(k => (
              <Box key={`wr-${k.id}`} flexDirection="column" marginBottom={1}>
                <Box flexDirection="row" gap={1}>
                  {closeBtn(k)}
                  <Button key={`w-${k.id}`} plain onPress={() => pick(k)}>
                    <Text color={RED}>●</Text> <Text weight="bold">{k.proj}</Text> · {cut(k.title, Math.max(20, rightCols - 30))} <Text dimColor>{ago(k.last, now)}</Text>
                  </Button>
                </Box>
                <Text color={RED}>{cut(k.need || k.detail, rightCols * 2)}</Text>
              </Box>
            ))}
          </Box>
        )
      }
    }

    // Mini mode: a narrow pane keeps only the sky and what needs the owner; a press opens the real
    // conversation in the app, whose own split view gives side-by-side columns with their own bar and mic.
    if (cols < 70) {
      const busy = shown.filter(running).sort((a, b) => b.last - a.last)
      const miniW = Math.max(160, cols * 8 - 8)
      const miniTarget = v.sel ? byId.get(v.sel) : undefined
      return (
        <Box flexDirection="column">
          <Text>
            <Text color={RED} weight="bold">{waitList.length} waiting</Text> · <Text color={ORANGE}>{busy.length} running</Text> · {nNew} unread
          </Text>
          {svg ? (
            <Box backgroundColor="#181818" marginY={1}>
              <Svg source={svg} alt={alt} width={miniW} height={Math.round(miniW * ratio)} isInteractive />
            </Box>
          ) : <Text dimColor>No sessions in this time range.</Text>}
          {waitList.map(k => (
            <Button key={`mw-${k.id}`} plain onPress={async () => { await set(g => ({ ...g, sel: k.id })); await openSession(k) }}>
              <Text color={RED}>●</Text> <Text weight="bold">{k.proj}</Text> · {cut(k.title, Math.max(12, cols - 16))}
            </Button>
          ))}
          {busy.map(k => (
            <Button key={`mr-${k.id}`} plain onPress={async () => { await set(g => ({ ...g, sel: k.id })); await openSession(k) }}>
              <Text color={ORANGE}>●</Text> <Text weight="bold">{k.proj}</Text> · {cut(k.title, Math.max(12, cols - 16))}
            </Button>
          ))}
          {Input && (
            <Box flexDirection="column" marginTop={1}>
              <Box flexDirection="row" gap={1}>
                <Text dimColor>{miniTarget ? `→ ${miniTarget.proj} · ${cut(miniTarget.title, Math.max(12, cols - 22))}` : '→ Qosmopol (Claude)'}</Text>
                {miniTarget && <Button key="hedef-sil" plain onPress={() => set(g => ({ ...g, sel: '' }))}><Text dimColor>✕</Text></Button>}
              </Box>
              <Input key={`mini-bar-${miniTarget?.id ?? 'ben'}`} rows={2} placeholder="Type or dictate (🌐 twice)" submitLabel="Send" onSubmit={(text: string) => {
                if (!text.trim()) return
                if (miniTarget) void send(miniTarget, text)
                else void $.prompt.submit({ text })
              }} />
            </Box>
          )}
          <Button key="web-mini" plain onPress={() => openWeb()}>
            <Text color="#4da3ff">⤢ Open the web view: clickable map, columns, microphone</Text>
          </Button>
          <Text dimColor>Click a session to open it in the app. For side by side, drag it from the sidebar or right-click → Open in → Split view. Widen the pane for details.</Text>
        </Box>
      )
    }

    if (!wide) {
      return (
        <Box flexDirection="column">
          {header}
          {right}
          <Box marginTop={1} flexDirection="column">
            {tree}
            {bar}
            {thumb}
          </Box>
        </Box>
      )
    }
    return (
      <Box flexDirection="row" gap={2}>
        <Box flexDirection="column" width="34%">
          {header}
          {tree}
          {bar}
          {thumb}
        </Box>
        <Box flexDirection="column" width="64%">
          {right}
        </Box>
      </Box>
    )
  })
}
