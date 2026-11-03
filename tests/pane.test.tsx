import { expect, mock, test } from 'claude-code/testing'

const PANE = {
  plugin: 'qosmopol',
  component: 'Pane',
  requestId: 'qosmopol',
  props: { title: 'Qosmopol', isFocused: false, bodyColumns: 90, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, view: {} },
} as const

const now = Date.now()
const k = (id: string, proj: string, title: string, mins: number, extra: object = {}) => ({
  id, acc: 'A', title, proj, cwd: `/x/${proj}`, last: now - mins * 60_000, seen: now - 9e9, created: 0, turns: 4,
  star: false, cat: 'completed', need: '', detail: 'bitti', sumId: `s-${id}`, error: false, ...extra,
})
const SCAN = {
  current: 'A',
  accounts: ['A', 'B'],
  sessions: [
    k('local_1', 'Website', 'Upload a video to the new channel', 5, { cat: 'blocked', need: 'brew install approval?' }),
    k('local_2', 'Website', 'Subtitle translation', 60),
    k('local_5', 'Podcast', 'Render running', 1, { cat: 'blocked', need: 'old question', busy: true }),
    k('local_3', 'Podcast', 'Phone line', 300, { seen: now }),
    k('local_4', 'Shop', 'SEO report', 2000, { acc: 'B' }),
  ],
}

test('the sky, the waiting list and the archive draw on desktop and mobile', async ($, on) => {
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  const argvs: (readonly string[])[] = []
  on('process.run', (_, e) => {
    argvs.push(e.argv)
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    return { value: { exitCode: 0, stdout: JSON.stringify(SCAN), stderr: '' } }
  })
  on('env.get', () => ({ value: undefined })) // macOS: no OS variable
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  expect(argvs.length).toBeGreaterThan(0)
  expect(argvs.every(a => a[0] === '/usr/bin/python3')).toBe(true)

  // A narrow pane is the mini sky: the map, the waiting and the running, nothing else.
  for (const surface of ['desktop', 'mobile'] as const) {
    const mini = await $.ui.mount({ ...PANE, surface, props: { ...PANE.props, bodyColumns: 50 } })
    expect(await mini.find({ type: 'Svg' })).toBeDefined()
    expect(await mini.find({ key: 'mw-local_1' })).toBeDefined()
    expect(await mini.find({ key: 'pb-Website' })).toBeUndefined()
    if (surface === 'desktop') expect(await mini.find({ key: 'mini-bar-ben' })).toBeDefined()
    await mini.unmount()
  }

  for (const [surface, bodyColumns] of [['desktop', 180], ['desktop', 90], ['mobile', 80]] as const) {
    const ui = await $.ui.mount({ ...PANE, surface, props: { ...PANE.props, bodyColumns } })
    expect((await ui.find({ type: 'Text', text: /1 waiting for you/ }))).toBeDefined()
    expect((await ui.find({ type: 'Text', text: /1 running/ }))).toBeDefined()
    const svg = await ui.find({ type: 'Svg' })
    expect(svg).toBeDefined()
    await ui.press({ key: 'w-local_1' })
    expect(await ui.find({ type: 'Text', text: /Waiting: brew install/ })).toBeDefined()
    await ui.press({ key: 'pb-Website' })
    expect(await ui.find({ key: 'Website-local_2' })).toBeDefined()
    expect(await ui.find({ key: 'pr-Website-local_2' })).toBeDefined()
    await ui.press({ key: 'pr-Website-local_2' })
    expect(await ui.find({ type: 'Text', text: /Conversation/ })).toBeDefined()
    // Wide panes keep up to four columns side by side; narrow ones keep the last two.
    if (bodyColumns >= 110) expect(await ui.find({ key: 'cx-k:local_1' })).toBeDefined()
    else expect(await ui.find({ key: 'cx-k:local_1' })).toBeUndefined()
    expect(await ui.find({ key: 'cx-p:Website' })).toBeDefined()
    expect(await ui.find({ key: 'cx-k:local_2' })).toBeDefined()
    await ui.press({ key: 'kapat' })
    expect(await ui.find({ key: 'x-local_1' })).toBeDefined()
    await ui.press({ key: 't-mesaj' })
    expect(await ui.find({ key: 'm-s-local_4' })).toBeDefined()
    await ui.press({ key: 'f-bekleyen' })
    expect(await ui.find({ key: 'm-s-local_4' })).toBeUndefined()
    expect(await ui.find({ key: 'm-s-local_1' })).toBeDefined()
    await ui.press({ key: 'f-hepsi' })
    await ui.press({ key: 't-harita' })
    await ui.press({ key: 'harita-buyut' })
    expect(await ui.find({ key: 'kucult' })).toBeDefined()
    await ui.press({ key: 'kucult' })
    await ui.press({ key: 'pb-Website' })
    expect(await ui.find({ key: 'cx-p:Website' })).toBeDefined()
    await ui.press({ key: 'pb-Website' })
    expect(await ui.find({ key: 'cx-p:Website' })).toBeUndefined()
    expect(await ui.find({ key: 'Website-local_2' })).toBeUndefined()
    await ui.unmount()
  }
})

test('on Windows the scripts run under the py launcher', async ($, on) => {
  const argvs: (readonly string[])[] = []
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    argvs.push(e.argv)
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    return { value: { exitCode: 0, stdout: JSON.stringify(SCAN), stderr: '' } }
  })
  on('env.get', (_, e) => ({ value: e.name === 'OS' ? 'Windows_NT' : undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: 'C:/', surface: 'desktop', isInteractive: true })
  expect(argvs.length).toBeGreaterThan(0)
  expect(argvs.map(a => `${a[0]} ${a[1]} ${a[2].replace(/.*\/bin\//, 'bin/')}`)).toContain('py -3 bin/scan.py')
  expect(argvs.every(a => a[0] === 'py' && a[1] === '-3')).toBe(true)
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /1 waiting for you/ })).toBeDefined()
  await ui.unmount()
})

test('the band above the prompt counts what waits and opens the map, in the app language', async ($, on) => {
  const argvs: (readonly string[])[] = []
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    argvs.push(e.argv)
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    return { value: { exitCode: 0, stdout: JSON.stringify({ ...SCAN, lang: 'tr' }), stderr: '' } }
  })
  on('env.get', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const band = await $.ui.mount({
    plugin: 'qosmopol', component: 'AbovePrompt', surface: 'desktop',
    props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 90, scroll: { offset: 0, bodyRows: 10 }, view: {} },
  } as any)
  expect(await band.find({ type: 'Text', text: /1 bekliyor/ })).toBeDefined()
  await band.press({ key: 'map' })
  expect(argvs.some(a => a[0] === '/usr/bin/open' && a[1] === 'http://127.0.0.1:47321/')).toBe(true)
  await band.unmount()
})

test('/qosmopol says why it could not start instead of reporting success', async ($, on) => {
  const opened: string[] = []
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', (_, e) => { opened.push(e.id); return { value: { isPlaced: true } } })
  on('process.run', (_, e) => {
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    if (e.argv.includes('claim')) return { value: { exitCode: 1, stdout: '', stderr: 'Traceback (most recent call last):\n  ...\nKeyError: \'APPDATA\'\n' } }
    return { value: { exitCode: 0, stdout: JSON.stringify(SCAN), stderr: '' } }
  })
  on('env.get', (_, e) => ({ value: e.name === 'OS' ? 'Windows_NT' : undefined }))
  mock.store(on)
  mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  const toasts: string[] = []
  on('ui.toast', (_, e) => { toasts.push(String(e.text)); return { value: undefined } })

  const r = await $.command.run({ command: 'qosmopol' })
  expect(r.text).toMatch(/could not start: .*KeyError: 'APPDATA'/)
  expect(toasts.some(t => t.includes("KeyError: 'APPDATA'"))).toBe(true)
  expect(opened).toEqual([])
})

test('what the owner writes to the home session from the web view arrives as their own words', async ($, on) => {
  const prompts: any[] = []
  let queued = [{ job: 'j1', kind: 'send', id: 'self', text: 'merhaba' }]
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    if (e.argv.includes('take')) {
      const jobs = queued
      queued = []
      return { value: { exitCode: 0, stdout: JSON.stringify(jobs), stderr: '' } }
    }
    return { value: { exitCode: 0, stdout: JSON.stringify(SCAN), stderr: '' } }
  })
  on('prompt.submit', (_, e) => {
    prompts.push(e)
    return { text: e.text }
  })
  on('env.get', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  const clock = mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/x', surface: 'desktop', isInteractive: true })
  await clock.advance(3000)
  expect(prompts.map(p => p.text)).toEqual(['merhaba'])
  expect(prompts[0].origin).toMatchObject({ kind: 'plugin', asUser: true })
})

test('sessions on the owner\'s other computers: counted apart in the band, opened on claude.ai, never archived here', async ($, on) => {
  const far = { ...k('local_9', 'Space Game · MacBook', 'Ship the level', 3, { cat: 'blocked', need: 'which ending?' }), remote: true, dev: 'd1', devName: 'MacBook', bridge: 'session_01abc', cwd: '' }
  const argvs: (readonly string[])[] = []
  const mcp: string[] = []
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    argvs.push(e.argv)
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    return { value: { exitCode: 0, stdout: JSON.stringify({ ...SCAN, sessions: [...SCAN.sessions, far], devices: [{ id: 'd1', name: 'MacBook', at: now, stale: false, os: 'darwin', sessions: 1 }] }), stderr: '' } }
  })
  on('mcp.call', (_, e) => { mcp.push(`${e.tool} ${JSON.stringify(e.args)}`); return { value: { content: [], isError: false } } })
  on('env.get', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/x', surface: 'desktop', isInteractive: true })
  const band = await $.ui.mount({ plugin: 'qosmopol', component: 'AbovePrompt', surface: 'desktop', props: { hasSurvey: false, bodyColumns: 100 } } as any)
  expect(await band.find({ type: 'Text', text: /^1 waiting for you$/ })).toBeDefined()
  expect(await band.find({ type: 'Text', text: /\+1 on your other computers/ })).toBeDefined()
  await band.unmount()
  expect(argvs.some(a => a.some(x => x.includes('epitaxy/local_9')))).toBe(false)
  expect(mcp.some(m => m.includes('local_9'))).toBe(false)
})

test('the home session reports which sessions have Remote Control on, for the other computers', async ($, on) => {
  const argvs: (readonly string[])[] = []
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    argvs.push(e.argv)
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    if (e.argv.includes('home')) return { value: { exitCode: 0, stdout: 'cli-1\n', stderr: '' } }
    if (e.argv.includes('take')) return { value: { exitCode: 0, stdout: '[]', stderr: '' } }
    return { value: { exitCode: 0, stdout: JSON.stringify(SCAN), stderr: '' } }
  })
  on('mcp.call', (_, e) => ({ value: { isError: false, content: [{ type: 'text', text: JSON.stringify([
    { sessionId: 'local_1', remoteControlActive: true, group: { id: 'g1', name: 'Client Ads' } },
    { sessionId: 'local_2', remoteControlActive: false, group: null }, { sessionId: 'x' }]) }] } }))
  on('env.get', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  const clock = mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/x', surface: 'desktop', isInteractive: true })
  await clock.advance(3000)
  const rc = argvs.find(a => a.includes('rc'))
  expect(rc).toBeDefined()
  expect(JSON.parse(rc![rc!.indexOf('rc') + 1])).toEqual({ local_1: true, local_2: false })
  expect(JSON.parse(rc![rc!.indexOf('rc') + 2])).toEqual({ local_1: 'Client Ads' })  // the sidebar group names the project
})

test('what the owner writes to any other session arrives there as their own words, through its own inbox', async ($, on) => {
  const prompts: any[] = [], writes: [string, string][] = [], argvs: (readonly string[])[] = []
  const files: Record<string, string> = { '/q/gelen/cli-2/abc.json': JSON.stringify({ job: 'abc', id: 'local_2', text: 'devam et' }) }
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    argvs.push(e.argv)
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    if (e.argv.includes('home')) return { value: { exitCode: 0, stdout: 'cli-home\n', stderr: '' } }  // not this one
    if (e.argv.includes('inbox')) return { value: { exitCode: 0, stdout: '/q/gelen/cli-2\n', stderr: '' } }
    if (e.argv.includes('take')) return { value: { exitCode: 0, stdout: '[]', stderr: '' } }
    return { value: { exitCode: 0, stdout: JSON.stringify(SCAN), stderr: '' } }
  })
  on('fs.list', () => ({ value: Object.entries(files).map(([p, t]) => ({ name: p.split('/').pop()!, kind: 'file' as const, size: t.length, mtimeMs: 0, isLink: false })) }))
  // the engine hands paths on in the platform's own spelling (C:\q\gelen\... on Windows): compare them as /q/gelen/...
  const norm = (p: string) => p.replace(/\\/g, '/').replace(/^[A-Za-z]:/, '')
  on('fs.read', (_, e) => ({ value: files[norm(e.path)] }))
  on('fs.write', (_, e) => {
    const path = norm(e.path)
    writes.push([path, e.text])
    if (path in files) files[path] = e.text
    return { value: undefined }
  })
  on('prompt.submit', (_, e) => {
    prompts.push(e)
    return { text: e.text }
  })
  on('env.get', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  const clock = mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-2' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/x', surface: 'desktop', isInteractive: true })
  await clock.advance(3000)
  await clock.advance(3000)
  expect(prompts.map(p => p.text)).toEqual(['devam et'])  // once, though the bridge ran twice
  expect(prompts[0].origin).toMatchObject({ kind: 'plugin', asUser: true })
  expect(files['/q/gelen/cli-2/abc.json']).toBe('')  // the receipt
  expect(writes.some(([p]) => p === '/q/gelen/cli-2/.canli')).toBe(true)  // the heartbeat the server checks
  const done = argvs.find(a => a.includes('done'))
  expect(JSON.parse(done![done!.indexOf('done') + 1])[0]).toMatchObject({ job: 'abc', ok: true })
})

for (const lang of ['en-US', 'tr-TR']) test(`the pane speaks the app's language only (${lang})`, async ($, on) => {
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    return { value: { exitCode: 0, stdout: JSON.stringify({ ...SCAN, lang }), stderr: '' } }
  })
  on('env.get', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop', props: { ...PANE.props, bodyColumns: 180 } })
  const seen: string[] = []
  const look = async () => { for (const e of [...await ui.findAll({ type: 'Text' }), ...await ui.findAll({ type: 'Button' })]) seen.push(e.text || String(e.props.label ?? '')) }
  await look()
  await ui.press({ key: 'w-local_1' })  // a session's column
  await look()
  await ui.press({ key: 'kapat' })  // back to the lists: the waiting and the messages tabs
  await look()
  await ui.press({ key: 't-mesaj' })
  await look()
  await ui.unmount()
  const words = seen.join(' | ')
  if (lang === 'en-US') {
    // the sample sessions' own titles are English: any Turkish here came from the pane itself
    expect(words).not.toMatch(/[ğüşöçıİĞÜŞÖÇ]|\b(Yenile|Projeler|Bekleyenler|Daha fazla|Sen|Konuşma|Hepsi|bekliyor)\b/)
    expect(words).toMatch(/Projects/)
  } else {
    expect(words).toMatch(/Projeler/)
    expect(words).toMatch(/Yenile/)
    expect(words).toMatch(/Konuşma/)
    expect(words).not.toMatch(/\b(Projects|Refresh|Conversation|Open in app|Mark read)\b/)
  }
})

test('a session renamed on the map is renamed in the Claude app itself, the home session too', async ($, on) => {
  let queued = [{ job: 't1', kind: 'set', id: 'local_1', what: 'title', value: 'Space Game' }, { job: 't2', kind: 'set', id: 'self', what: 'title', value: 'Home' }]
  const mcp: string[] = []
  on('command.register', () => ({ value: { command: 'qosmopol' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', (_, e) => {
    if (e.argv.includes('--version')) return { value: { exitCode: 0, stdout: 'Python 3.12.1\n', stderr: '' } }
    if (e.argv.includes('take')) {
      const jobs = queued
      queued = []
      return { value: { exitCode: 0, stdout: JSON.stringify(jobs), stderr: '' } }
    }
    return { value: { exitCode: 0, stdout: JSON.stringify(SCAN), stderr: '' } }
  })
  on('mcp.call', (_, e) => { mcp.push(`${e.tool} ${JSON.stringify(e.args)}`); return { value: { content: [], isError: false } } })
  on('env.get', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  const clock = mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/x', surface: 'desktop', isInteractive: true })
  await clock.advance(3000)
  expect(mcp.filter(m => m.startsWith('set_session_title'))).toEqual([
    'set_session_title {"session_id":"local_1","title":"Space Game"}', 'set_session_title {"session_id":"self","title":"Home"}'])
})
