import { expect, mock, test } from 'claude-code/testing'

const PANE = {
  plugin: 'qosmos',
  component: 'Pane',
  requestId: 'qosmos',
  props: { title: 'Qosmos', isFocused: false, bodyColumns: 90, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, view: {} },
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
    k('local_1', 'Website', 'Yeni kanala video yükle', 5, { cat: 'blocked', need: 'brew install onayı?' }),
    k('local_2', 'Website', 'Altyazı çevirisi', 60),
    k('local_5', 'Podcast', 'Render sürüyor', 1, { cat: 'blocked', need: 'eski soru', busy: true }),
    k('local_3', 'Podcast', 'Phone line', 300, { seen: now }),
    k('local_4', 'Shop', 'SEO report', 2000, { acc: 'B' }),
  ],
}

test('the sky, the waiting list and the archive draw on desktop and mobile', async ($, on) => {
  on('command.register', () => ({ value: { command: 'qosmos' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('process.run', () => ({ value: { exitCode: 0, stdout: JSON.stringify(SCAN), stderr: '' } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  mock.store(on)
  mock.clock(on, { now: Date.now() })
  on('session.id', () => ({ value: 'cli-1' }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', () => ({ value: undefined }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })

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
    expect((await ui.find({ type: 'Text', text: /1 seni bekliyor/ }))).toBeDefined()
    expect((await ui.find({ type: 'Text', text: /1 çalışıyor/ }))).toBeDefined()
    const svg = await ui.find({ type: 'Svg' })
    expect(svg).toBeDefined()
    await ui.press({ key: 'w-local_1' })
    expect(await ui.find({ type: 'Text', text: /Bekliyor: brew install/ })).toBeDefined()
    await ui.press({ key: 'pb-Website' })
    expect(await ui.find({ key: 'Website-local_2' })).toBeDefined()
    expect(await ui.find({ key: 'pr-Website-local_2' })).toBeDefined()
    await ui.press({ key: 'pr-Website-local_2' })
    expect(await ui.find({ type: 'Text', text: /Konuşma/ })).toBeDefined()
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
