import type { Konu, Mesaj, Tarama } from '../types'

// Pure drawing and status rules of the Qosmos pane: no $, so plain node can render a sky too.

export const DAY = 86_400_000
export const ORANGE = '#ff8a00'
export const RED = '#ff2020'
export const DONE = '#8c8c8c'

// Red: the owner has to act. Orange: the agent is working. A blocked report stops counting once a new turn runs.
export const waiting = (k: Konu) => !!k.ask || (k.cat === 'blocked' && !k.busy)
export const running = (k: Konu) => !!k.busy && !k.ask
export const unread = (k: Konu, readAt: Record<string, number>) => Math.max(k.seen, readAt[k.id] ?? 0) < k.last - 1000
export const msgUnread = (m: Mesaj, byId: Map<string, Konu>, readAt: Record<string, number>) => {
  if (m.read) return false
  const k = byId.get(m.sid)
  return Math.max(k?.seen ?? 0, readAt[m.sid] ?? 0) < m.at - 1000
}

export function ago(ms: number, now: number) {
  const m = Math.max(0, Math.round((now - ms) / 60_000))
  if (m < 60) return `${m} dk`
  if (m < 48 * 60) return `${Math.round(m / 60)} sa`
  return `${Math.round(m / 1440)} g`
}

export const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
export const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s)

export function visible(all: Konu[], days: number, now: number) {
  return all.filter(k => days === 0 || now - k.last < days * DAY || (waiting(k) && now - k.last < 30 * DAY))
}

export function accLabel(t: Tarama, acc: string) {
  const i = t.accounts.indexOf(acc)
  return `H${i + 1}${acc === t.current ? '' : '·başka'}`
}

export type Planet = { name: string; moons: Konu[]; r: number; outer: number; x: number; y: number }

export function layout(groups: Map<string, Konu[]>) {
  const planets: Planet[] = [...groups.entries()].map(([name, list]) => {
    const moons = [...list].sort((a, b) => b.last - a.last).slice(0, 24)
    const r = Math.min(48, 16 + 5 * Math.sqrt(list.length) + (list.some(k => k.star) ? 4 : 0))
    const outer = r + 22 + (moons.length > 12 ? 18 : 0) + 10
    return { name, moons, r, outer, x: 0, y: 0 }
  })
  planets.sort((a, b) => b.outer - a.outer)
  const placed: Planet[] = []
  for (const p of planets) {
    for (let t = 0; ; t += 1) {
      const a = t * 0.45
      const d = t * 3
      const x = Math.cos(a) * d
      const y = Math.sin(a) * d * 0.75
      if (placed.every(q => Math.hypot(q.x - x, q.y - y) >= q.outer + p.outer + 18)) {
        p.x = x
        p.y = y
        break
      }
    }
    placed.push(p)
  }
  return placed
}

export function sky(groups: Map<string, Konu[]>, now: number, readAt: Record<string, number>, sel: string) {
  const planets = layout(groups)
  if (planets.length === 0) return ''
  const minX = Math.min(...planets.map(p => p.x - p.outer)) - 20
  const maxX = Math.max(...planets.map(p => p.x + p.outer)) + 20
  const minY = Math.min(...planets.map(p => p.y - p.outer)) - 20
  const maxY = Math.max(...planets.map(p => p.y + p.outer)) + 34
  const w = Math.round(maxX - minX)
  const hgt = Math.round(maxY - minY)
  const blink = '<animate attributeName="opacity" values="1;0.15;1" dur="0.9s" repeatCount="indefinite"/>'
  const out: string[] = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${Math.round(minX)} ${Math.round(minY)} ${w} ${hgt}" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" font-family="-apple-system, Helvetica, sans-serif">`,
    `<rect x="${Math.round(minX)}" y="${Math.round(minY)}" width="${w}" height="${hgt}" fill="#181818"/>`,
  ]
  for (const p of planets) {
    const all = groups.get(p.name) ?? []
    const nWait = all.filter(waiting).length
    const nNew = all.filter(k => !waiting(k) && unread(k, readAt)).length
    const lively = all.some(k => now - k.last < 7 * DAY)
    const ring1 = p.r + 22
    const ring2 = ring1 + 18
    out.push(`<circle cx="${p.x}" cy="${p.y}" r="${ring1}" fill="none" stroke="#2b2b2b" stroke-width="0.8"/>`)
    if (p.moons.length > 12) out.push(`<circle cx="${p.x}" cy="${p.y}" r="${ring2}" fill="none" stroke="#2b2b2b" stroke-width="0.8"/>`)
    p.moons.forEach((k, i) => {
      const inner = i < 12
      const n = inner ? Math.min(12, p.moons.length) : p.moons.length - 12
      const j = inner ? i : i - 12
      const a = -Math.PI / 2 + (j / n) * Math.PI * 2 + (inner ? 0 : Math.PI / n)
      const R = inner ? ring1 : ring2
      const mx = +(p.x + Math.cos(a) * R).toFixed(1)
      const my = +(p.y + Math.sin(a) * R).toFixed(1)
      const ex = +(p.x + Math.cos(a) * p.r).toFixed(1)
      const ey = +(p.y + Math.sin(a) * p.r).toFixed(1)
      const mr = +(3 + Math.min(5, Math.sqrt(k.turns) / 1.4)).toFixed(1)
      const isWait = waiting(k)
      const isNew = !isWait && unread(k, readAt)
      const isRun = running(k)
      const fill = isWait ? RED : isRun ? ORANGE : DONE
      const tip = `${p.name} · ${k.title}\n${isWait ? 'SENİ BEKLİYOR' : isRun ? 'Ajan çalışıyor' : isNew ? 'Okunmamış cevap' : 'Okundu'} · ${ago(k.last, now)} önce${k.need ? `\n${k.need}` : ''}`
      out.push(`<a href="claude://claude.ai/epitaxy/${k.id}" target="_top" style="cursor:pointer"><g><title>${esc(tip)}</title>`)
      out.push(`<line x1="${ex}" y1="${ey}" x2="${mx}" y2="${my}" stroke="${isWait ? RED : isRun ? ORANGE : '#3a3a3a'}" stroke-width="${isWait || isRun ? 0.9 : 0.6}"/>`)
      if (isWait) out.push(`<circle cx="${mx}" cy="${my}" r="${mr + 5}" fill="${RED}" opacity="0.45"><animate attributeName="opacity" values="0.5;0;0.5" dur="0.9s" repeatCount="indefinite"/></circle>`)
      if (isRun) out.push(`<circle cx="${mx}" cy="${my}" r="${mr + 6}" fill="${ORANGE}" opacity="0.35"><animate attributeName="opacity" values="0.45;0.1;0.45" dur="2s" repeatCount="indefinite"/></circle>`)
      if (isRun) out.push(`<circle cx="${mx}" cy="${my}" r="${mr + 4}" fill="none" stroke="${ORANGE}" stroke-width="0.8"><animate attributeName="r" values="${mr + 2};${mr + 8};${mr + 2}" dur="2s" repeatCount="indefinite"/></circle>`)
      if (isNew && !isRun) out.push(`<circle cx="${mx}" cy="${my}" r="${mr + 2}" fill="none" stroke="#ffffff" stroke-width="1.2"/>`)
      if (k.id === sel) out.push(`<circle cx="${mx}" cy="${my}" r="${mr + 3}" fill="none" stroke="#4da3ff" stroke-width="1.4"/>`)
      out.push(`<circle cx="${mx}" cy="${my}" r="${mr}" fill="${fill}">${isWait ? blink : ''}</circle></g></a>`)
    })
    if (nWait) out.push(`<circle cx="${p.x}" cy="${p.y}" r="${p.r + 6}" fill="none" stroke="${RED}" stroke-width="2.5">${blink}</circle>`)
    else if (all.some(running)) out.push(`<circle cx="${p.x}" cy="${p.y}" r="${p.r + 6}" fill="none" stroke="${ORANGE}" stroke-width="2"/>`)
    const top = [...all].sort((a, b) => Number(waiting(b)) - Number(waiting(a)) || b.last - a.last)[0]
    out.push(`<a href="claude://claude.ai/epitaxy/${top?.id ?? ''}" target="_top" style="cursor:pointer"><g><title>${esc(`${p.name}: ${all.length} konu · ${nWait} seni bekliyor · ${nNew} okunmamış · basınca en acil konu açılır`)}</title>`)
    out.push(`<circle cx="${p.x}" cy="${p.y}" r="${p.r}" fill="${lively ? '#ffffff' : '#9a9a9a'}"/>`)
    out.push(`<text x="${p.x}" y="${p.y + 4}" text-anchor="middle" font-size="11" font-weight="700" fill="#000">${all.length}</text></g></a>`)
    if (nWait) {
      out.push(`<circle cx="${p.x + p.r * 0.75}" cy="${p.y - p.r * 0.75}" r="8" fill="${RED}"/>`)
      out.push(`<text x="${p.x + p.r * 0.75}" y="${p.y - p.r * 0.75 + 3.5}" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">${nWait}</text>`)
    }
    out.push(`<text x="${p.x}" y="${p.y + p.outer + 4}" text-anchor="middle" font-size="12" fill="#e8e8e8">${esc(cut(p.name, 22))}</text>`)
  }
  out.push('</svg>')
  return out.join('')
}
