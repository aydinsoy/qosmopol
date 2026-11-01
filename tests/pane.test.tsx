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
