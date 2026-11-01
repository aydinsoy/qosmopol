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
  /** Remote Control's id: claude.ai/code/<id> opens the session from any device while it is valid. */
  bridge?: string
  /** Its Remote Control is on now (the home session reads it from the app); absent when not known. */
  rc?: boolean
  /** The session lives on another of the owner's computers (bin/sync.py); its project name ends with that computer's name. */
  remote?: boolean
  dev?: string
  devName?: string
  /** That computer has not written its summary for a while. */
  stale?: boolean
  /** The owner put it under one of their own project names; proj0 is its folder's. */
  group?: boolean
  proj0?: string
}

export type Tarama = {
  at: number
  current: string
  accounts: string[]
  sessions: Konu[]
  /** Sessions the owner closed in the pane, newest last. */
  hidden?: { id: string; proj: string; title: string }[]
  /** The language chosen in the Claude app (config.json "locale"), such as "tr" or "en-US"; empty when unknown. */
  lang?: string
  /** The owner's other computers that share a sync folder. */
  devices?: { id: string; name: string; at: number; stale: boolean; os: string; sessions: number }[]
  /** The owner's own project names. */
  groups?: string[]
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
    qosmopol: {
      tarama: Shaped<Tarama>
      mesajlar: Shaped<Mesaj[]>
      gorunum: Shaped<Gorunum>
      okundu: Shaped<Record<string, number>>
      konusma: Shaped<Record<string, Satir[]>>
    }
  }
}
