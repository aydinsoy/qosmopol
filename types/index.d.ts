/** One Code session as bin/scan.py reports it. */
export type Konu = {
  id: string
  acc: string
  title: string
  proj: string
  cwd: string
  last: number
  seen: number
  created: number
  turns: number
  star: boolean
  cat: string
  need: string
  detail: string
  sumId: string
  error: boolean
  /** A turn is running now. */
  busy?: boolean
  /** The turn is paused on a permission or question for the owner. */
  ask?: boolean
}

export type Tarama = {
  at: number
  current: string
  accounts: string[]
  sessions: Konu[]
  /** Sessions the owner closed in the pane, newest last. */
  hidden?: { id: string; proj: string; title: string }[]
  error?: string
}

/** One end-of-turn report, kept after the session moves on. */
export type Mesaj = {
  id: string
  sid: string
  proj: string
  title: string
  acc: string
  cat: string
  text: string
  at: number
  read: boolean
}

/** One turn of a session's transcript. */
export type Satir = { role: 'sen' | 'claude'; text: string }

export type Gorunum = {
  tab: 'harita' | 'mesajlar'
  days: number
  filter: 'hepsi' | 'okunmamis' | 'okunmus' | 'bekleyen'
  proj: string
  open: string[]
  sel: string
  limit: number
  /** A bulk close waiting for its second press. */
  onay?: string
  /** Columns open on the right: 'k:<session>', 'p:<project>' or 'harita'. */
  cols?: string[]
}

declare module 'claude-code' {
  interface PluginState {
    qosmos: {
      tarama: Shaped<Tarama>
      mesajlar: Shaped<Mesaj[]>
      gorunum: Shaped<Gorunum>
      okundu: Shaped<Record<string, number>>
      konusma: Shaped<Record<string, Satir[]>>
    }
  }
}
