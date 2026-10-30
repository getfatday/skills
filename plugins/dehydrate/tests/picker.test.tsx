import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import type { Row } from '../types'

const NOW = 1_800_000_000
const ROW: Row = {
  id: 'r1', kind: 'session', name: 'alpha sprites', bg_id: 'aaaa1111', session_id: 'aaaa1111-0', group: 'today',
  dehydrated_at: '2027-01-15T07:00:00+00:00', dehydrated_ts: NOW - 3600, description: 'alpha work',
  first_prompt: 'make the sprites', branch: 'wt-alpha', repo: 'vault', repo_path: '/x/src/vault',
  cwd: '/x/src/vault/.claude/worktrees/alpha', removed: true, restored: false, auto: false, rehydrations: 0, running: null,
  search: 'r1 alpha work vault wt-alpha alpha sprites aaaa1111',
}
const ROWS: Row[] = [
  ROW,
  { ...ROW, id: 'r2', name: 'beta capacity', bg_id: 'bbbb2222', group: 'week', repo: 'product-portfolio', branch: null,
    running: { bg_id: '8d13edb4', session_id: '8d13edb4-0', state: 'working', live: true }, search: 'r2 beta capacity product-portfolio 8d13edb4' },
  { ...ROW, id: 'r3', name: 'gamma dots', bg_id: null, kind: 'worktree', group: 'month', repo: 'vault',
    search: 'r3 gamma dots vault' },
  { ...ROW, id: 'r4', name: 'delta old', bg_id: 'dddd4444', group: 'older', repo: 'dotfiles', search: 'r4 delta old dotfiles' },
]
const LIST = JSON.stringify({ now: NOW, agents: 'live', rows: ROWS })

const PANE = {
  plugin: 'dehydrate', component: 'Pane', requestId: 'dehydrate-picker',
  props: { title: 'Rehydrate', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 30 }, view: {} },
} as const

const RUN = { command: 'dehydrate:rehydrate', origin: { kind: 'composer' }, presentation: { isFullscreen: true, columns: 160 } } as const

type Result = { exitCode: number; stdout: string; stderr?: string }

type Opts = {
  surfaces?: readonly ('terminal' | 'desktop' | 'mobile')[]
  open?: () => { value: { isPlaced: true } | { isPlaced: false; reason: string } }
}

// The engine beneath the plugin: process.run answered by `answer`, a skill run counted, the pane placed.
function world(on: On, answer: (argv: readonly string[]) => Result | Promise<Result>, opts: Opts = {}) {
  const calls: string[][] = []
  const skill = { runs: 0, opened: 0 }
  const closed: string[] = []
  const toasts: string[] = []
  on('session.surfaces', () => ({ value: opts.surfaces ?? ['terminal'] }))
  on('ui.toast', (_, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.open', () => {
    skill.opened++
    return (opts.open ? opts.open() : { value: { isPlaced: true } }) as never
  })
  on('ui.close', (_, e) => {
    closed.push(e.id)
    return { value: undefined }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('command.run', () => {
    skill.runs++
    return { text: 'skill ran' }
  })
  on('process.run', async (_, e) => {
    calls.push([...e.argv])
    const r = await answer(e.argv)
    return { value: { stderr: '', isStdoutTruncated: false, isStderrTruncated: false, ...r } }
  })
  return { calls, skill, closed, toasts }
}

function listing(argv: readonly string[]): Result {
  return argv.includes('list') ? { exitCode: 0, stdout: LIST } : { exitCode: 0, stdout: '{}' }
}

// A process answer held until the test releases it.
function gate(): { promise: Promise<Result>; release: (r: Result) => void } {
  let release: (r: Result) => void = () => undefined
  const promise = new Promise<Result>(res => {
    release = res
  })
  return { promise, release }
}

const rehydrated = (out: object): Result => ({ exitCode: 0, stdout: JSON.stringify(out) })

for (const surface of ['terminal', 'desktop'] as const) {
  test('bare /rehydrate opens the picker and runs no skill, on ' + surface, async ($, on) => {
    mock.store(on)
    const w = world(on, listing, { surfaces: [surface] })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    const ran = await $.command.run({ ...RUN, args: '' })
    expect(ran.text).toBe('Rehydrate picker open. Type to search, Enter to pick, Esc to close.')
    expect(w.skill.runs).toBe(0)
    expect(w.calls[0]).toContain('--picker')
    // args left out (the kit's default) is bare too
    await $.command.run({ ...RUN } as never)
    expect(w.skill.runs).toBe(0)
  })

  test('/rehydrate <words> runs the skill and opens nothing, on ' + surface, async ($, on) => {
    mock.store(on)
    const w = world(on, listing, { surfaces: [surface] })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    const ran = await $.command.run({ ...RUN, args: 'auth flow' })
    expect(ran.text).toBe('skill ran')
    expect(w.skill.runs).toBe(1)
    expect(w.skill.opened).toBe(0)
    expect(w.calls).toHaveLength(0)
  })

  test('a failing mod falls back to the skill, on ' + surface, async ($, on) => {
    mock.store(on)
    const w = world(
      on,
      () => {
        throw new Error('boom')
      },
      {
        surfaces: [surface],
        open: () => {
          throw new Error('no panes today')
        },
      },
    )
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    const ran = await $.command.run({ ...RUN, args: '' })
    expect(ran.text).toBe('skill ran')
    expect(w.skill.runs).toBe(1)
  })

  test('groups in order, no empty group, running tag, search filters, on ' + surface, async ($, on) => {
    mock.store(on)
    world(on, listing, { surfaces: [surface] })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
    const heads = texts.filter(t => ['Today', 'This week', 'This month', 'Older'].includes(t))
    expect(heads).toEqual(['Today', 'This week', 'This month', 'Older'])
    expect(texts).toContain('4 of 4 · live')
    expect(texts).not.toContain('Loading dehydrated sessions...')
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(4)
    const running = await ui.find({ type: 'Button', key: 'r2:bbbb2222' })
    expect(running?.text).toMatch(/beta capacity/)
    expect(running?.text).toMatch(/8d13edb4/) // the live copy's id, not the original
    expect(running?.text).toMatch(/running/)
    expect((await ui.find({ type: 'Button', key: 'r1:aaaa1111' }))?.text).not.toMatch(/running/)
    await ui.input({ key: 'q', text: 'vault', kind: 'change' })
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(2)
    const after = (await ui.findAll({ type: 'Text' })).map(t => t.text)
    expect(after).not.toContain('This week') // an empty group is not drawn
    await ui.input({ key: 'q', text: 'zzz', kind: 'change' })
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    expect((await ui.find({ type: 'Text', text: /No match/ }))?.text).toBe('No match for "zzz".')
    expect(await ui.find({ type: 'Text', text: /Esc to close, or keep typing/ })).toBeDefined()
    await ui.unmount()
  })

  test('picking a row rehydrates and launches it, then closes, on ' + surface, async ($, on) => {
    mock.store(on)
    const clock = mock.clock(on, { now: NOW * 1000 })
    const w = world(on, argv =>
      argv.includes('rehydrate')
        ? { exitCode: 0, stdout: JSON.stringify({ id: 'r1', path: '/x/wt', launched: [{ bg_id: '1be4ed48', reused: false, note: null }] }) }
        : listing(argv),
    )
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: 'r1:aaaa1111' })
    expect(w.calls.at(-1)).toEqual(expect.arrayContaining(['rehydrate', 'r1', '--launch', '--json']))
    expect((await ui.find({ type: 'Text', text: /Back as/ }))?.text).toBe('Back as 1be4ed48 in claude agents · /x/wt')
    expect(w.toasts).toEqual(['Back as 1be4ed48 in claude agents · /x/wt'])
    await clock.advance(1000)
    expect(w.closed).toContain('dehydrate-picker')
    await ui.unmount()
  })

  test('a running row is not rehydrated again, on ' + surface, async ($, on) => {
    mock.store(on)
    const w = world(on, listing, { surfaces: [surface] })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    const before = w.calls.length
    await ui.press({ key: 'r2:bbbb2222' })
    expect(w.calls.length).toBe(before)
    expect((await ui.find({ type: 'Text', text: /Already running/ }))?.text).toBe(
      'Already running as 8d13edb4. claude attach 8d13edb4',
    )
    await ui.unmount()
  })

  test('cached rows draw while the list refreshes; an empty list says so, on ' + surface, async ($, on) => {
    mock.store(on, { 'picker-cache': { now: NOW, agents: 'cached', rows: [ROW] } })
    let release: (r: Result) => void = () => undefined
    const gate = new Promise<Result>(res => {
      release = res
    })
    world(on, argv => (argv.includes('list') ? gate : { exitCode: 0, stdout: '{}' }))
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    const running = $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /of 1/ }))?.text).toBe('1 of 1 · cached · refreshing')
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(1)
    release({ exitCode: 0, stdout: JSON.stringify({ now: NOW, agents: 'live', rows: [] }) })
    await running
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    expect((await ui.find({ type: 'Text', text: /Nothing has been dehydrated/ }))?.text).toBe(
      'Nothing has been dehydrated yet. /dehydrate closes idle sessions.',
    )
    await ui.unmount()
  })

  test('a failed rehydrate shows the error and leaves the rows live, on ' + surface, async ($, on) => {
    mock.store(on)
    const w = world(on, argv =>
      argv.includes('rehydrate')
        ? { exitCode: 1, stdout: JSON.stringify({ error: 'archived transcript for x fails its checksum' }) }
        : listing(argv),
    )
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: 'r4:dddd4444' })
    expect((await ui.find({ type: 'Text', text: /Failed/ }))?.text).toBe('Failed: archived transcript for x fails its checksum')
    const n = w.calls.length
    await ui.press({ key: 'r1:aaaa1111' }) // rows are live again after an error
    expect(w.calls.length).toBe(n + 1)
    await ui.unmount()
  })
  test('no cache: Loading shows while the list call runs, on ' + surface, async ($, on) => {
    mock.store(on)
    const g = gate()
    world(on, argv => (argv.includes('list') ? g.promise : { exitCode: 0, stdout: '{}' }), { surfaces: [surface] })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    const running = $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.find({ type: 'Text', text: 'Loading dehydrated sessions...' })).toBeDefined()
    g.release({ exitCode: 0, stdout: LIST })
    await running
    expect(await ui.find({ type: 'Text', text: /Loading/ })).toBeUndefined()
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(4)
    await ui.unmount()
  })

  test('a list failure with no cache is the error state, not the empty one, on ' + surface, async ($, on) => {
    mock.store(on)
    world(on, argv => (argv.includes('list') ? { exitCode: 1, stdout: '', stderr: 'manifest unreadable' } : listing(argv)), {
      surfaces: [surface],
    })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(0)
    expect((await ui.find({ type: 'Text', text: /Failed/ }))?.text).toBe('Failed: Error: manifest unreadable')
    expect(await ui.find({ type: 'Text', text: /Nothing has been dehydrated/ })).toBeUndefined()
    await ui.unmount()
  })

  test('a truncated list output says so instead of a parse error, on ' + surface, async ($, on) => {
    mock.store(on)
    on('session.surfaces', () => ({ value: [surface] }))
    on('ui.open', () => ({ value: { isPlaced: true } }))
    on('session.start', (_, e) => ({ cwd: e.cwd }))
    on('process.run', () => ({
      value: { exitCode: 0, stdout: LIST.slice(0, 100), stderr: '', isStdoutTruncated: true, isStderrTruncated: false },
    }))
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /Failed/ }))?.text).toMatch(/over 4 MiB/)
    await ui.unmount()
  })

  test('a second press while one runs, and a list that returns meanwhile, start nothing, on ' + surface, async ($, on) => {
    mock.store(on, { 'picker-cache': { now: NOW, agents: 'live', rows: ROWS } })
    const lg = gate()
    const rg = gate()
    let reached: () => void = () => undefined
    const reachedP = new Promise<void>(res => {
      reached = res
    })
    const w = world(
      on,
      argv => {
        if (argv.includes('list')) return lg.promise
        reached()
        return rg.promise
      },
      { surfaces: [surface] },
    )
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    const opening = $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    const first = ui.press({ key: 'r1:aaaa1111' })
    await reachedP // the press is at its process call
    expect(w.calls.filter(c => c.includes('rehydrate'))).toHaveLength(1)
    lg.release({ exitCode: 0, stdout: LIST }) // the refresh lands mid-restore
    await opening
    expect((await ui.find({ type: 'Text', text: /Rehydrating/ }))?.text).toBe('Rehydrating alpha sprites (aaaa1111)...')
    await ui.press({ key: 'r4:dddd4444' })
    expect(w.calls.filter(c => c.includes('rehydrate'))).toHaveLength(1)
    rg.release(rehydrated({ id: 'r1', path: '/x/wt', launched: [{ bg_id: '1be4ed48', reused: false, note: null }] }))
    await first
    expect((await ui.find({ type: 'Text', text: /Back as/ }))?.text).toBe('Back as 1be4ed48 in claude agents · /x/wt')
    await ui.unmount()
  })

  test('done texts: already running, still open, and restored but not launched, on ' + surface, async ($, on) => {
    mock.store(on)
    let answer: object = {}
    world(on, argv => (argv.includes('rehydrate') ? rehydrated(answer) : listing(argv)), { surfaces: [surface] })
    mock.clock(on, { now: NOW * 1000 })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    answer = { id: 'r1', path: '/x/wt', launched: [{ bg_id: '77777777', reused: true, note: null }] }
    await ui.press({ key: 'r1:aaaa1111' })
    expect((await ui.find({ type: 'Text', text: /Already running/ }))?.text).toBe('Already running as 77777777. claude attach 77777777')
    answer = {
      id: 'r1', path: '/x/wt',
      launched: [{ bg_id: 'f0f0f0f0', reused: true, note: 'still open in claude agents as f0f0f0f0 (state done); claude attach f0f0f0f0' }],
    }
    await ui.press({ key: 'r1:aaaa1111' })
    expect((await ui.find({ type: 'Text', text: /still open/ }))?.text).toMatch(/^still open in claude agents as f0f0f0f0/)
    answer = {
      id: 'r4', path: '/x/wt', notes: ['dd: no transcript archived; resume will fail'],
      launched: [{ bg_id: null, reused: false, skipped: true, note: 'no transcript archived; resume will fail' }],
    }
    await ui.press({ key: 'r4:dddd4444' })
    expect((await ui.find({ type: 'Text', text: /Restored/ }))?.text).toBe(
      'Restored /x/wt. Not launched: no transcript archived; resume will fail',
    )
    await ui.unmount()
  })

  test('rows still in place, still open, or restored are tagged; in place and open are not restored again, on ' + surface, async ($, on) => {
    const rows: Row[] = [
      { ...ROW, id: 'w1', kind: 'worktree', name: 'kept tree', bg_id: null, removed: false, search: 'w1 kept' },
      { ...ROW, id: 's1', name: 'left open', bg_id: 'f0f0f0f0', running: { bg_id: 'f0f0f0f0', session_id: 'f0f0f0f0-0', state: 'done', live: false }, search: 's1' },
      { ...ROW, id: 'r9', name: 'back again', bg_id: 'abab0000', restored: true, search: 'r9' },
    ]
    mock.store(on)
    const w = world(on, argv => (argv.includes('list') ? { exitCode: 0, stdout: JSON.stringify({ now: NOW, agents: 'live', rows }) } : rehydrated({})), {
      surfaces: [surface],
    })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Button', key: 'w1:' }))?.text).toMatch(/in place/)
    expect((await ui.find({ type: 'Button', key: 's1:f0f0f0f0' }))?.text).toMatch(/ open$/)
    expect((await ui.find({ type: 'Button', key: 's1:f0f0f0f0' }))?.text).not.toMatch(/running/)
    expect((await ui.find({ type: 'Button', key: 'r9:abab0000' }))?.text).toMatch(/restored/)
    const before = w.calls.length
    await ui.press({ key: 'w1:' })
    expect((await ui.find({ type: 'Text', text: /Still in place/ }))?.text).toBe('Still in place at /x/src/vault/.claude/worktrees/alpha')
    await ui.press({ key: 's1:f0f0f0f0' })
    expect((await ui.find({ type: 'Text', text: /Still open/ }))?.text).toBe('Still open in claude agents as f0f0f0f0 (done). claude attach f0f0f0f0')
    expect(w.calls.length).toBe(before)
    await ui.unmount()
  })

  test('a session claude rm refused is not relaunched from a cached listing, on ' + surface, async ($, on) => {
    const rows: Row[] = [{ ...ROW, id: 's2', name: 'refused rm', bg_id: 'b0000005', removed: false, search: 's2' }]
    mock.store(on, { 'picker-cache': { now: NOW, agents: 'cached', rows } })
    const w = world(on, argv => (argv.includes('list') ? { exitCode: 0, stdout: JSON.stringify({ now: NOW, agents: 'cached', rows }) } : rehydrated({})), {
      surfaces: [surface],
    })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: 's2:b0000005' })
    expect(w.calls.filter(c => c.includes('rehydrate'))).toHaveLength(0)
    expect((await ui.find({ type: 'Text', text: /May still be open/ }))?.text).toMatch(/claude rm refused it/)
    await ui.unmount()
  })

  test('a failed pick does not close the pane; a reopen is not closed by an earlier timer, on ' + surface, async ($, on) => {
    mock.store(on)
    const clock = mock.clock(on, { now: NOW * 1000 })
    let fail = true
    const w = world(on, argv =>
      argv.includes('rehydrate')
        ? fail
          ? { exitCode: 1, stdout: JSON.stringify({ error: 'repo /x is gone; clone it there first' }) }
          : rehydrated({ id: 'r1', path: '/x/wt', launched: [{ bg_id: '1be4ed48', reused: false, note: null }] })
        : listing(argv),
      { surfaces: [surface] },
    )
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    await ui.press({ key: 'r1:aaaa1111' })
    await clock.advance(2000)
    expect(w.closed).toHaveLength(0)
    fail = false
    await ui.press({ key: 'r1:aaaa1111' })
    await $.command.run({ ...RUN, args: '' }) // reopened inside the second
    await clock.advance(2000)
    expect(w.closed).toHaveLength(0)
    await ui.unmount()
  })

  test('a narrow pane cuts rows to its width and drops repo and branch, on ' + surface, async ($, on) => {
    const long: Row = { ...ROW, name: 'n'.repeat(120), branch: 'b'.repeat(80), search: 'long' }
    mock.store(on)
    world(on, argv => (argv.includes('list') ? { exitCode: 0, stdout: JSON.stringify({ now: NOW, agents: 'live', rows: [long] }) } : listing(argv)), {
      surfaces: [surface],
    })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const narrow = await $.ui.mount({ ...PANE, surface, props: { ...PANE.props, bodyColumns: 50 } })
    const t = (await narrow.find({ type: 'Button', key: 'r1:aaaa1111' }))?.text ?? ''
    expect(t.length).toBeLessThanOrEqual(50)
    expect(t).not.toMatch(/vault|bbbb/)
    expect(t).toMatch(/aaaa1111/)
    await narrow.unmount()
    const wide = await $.ui.mount({ ...PANE, surface, props: { ...PANE.props, bodyColumns: 160 } })
    const t2 = (await wide.find({ type: 'Button', key: 'r1:aaaa1111' }))?.text ?? ''
    expect(t2.length).toBeLessThanOrEqual(160)
    expect(t2).toMatch(/vault/)
    await wide.unmount()
  })

  test('only 50 rows are drawn, the header says when the list is the 500 newest, on ' + surface, async ($, on) => {
    const many: Row[] = Array.from({ length: 120 }, (_, i) => ({ ...ROW, id: 'm' + i, bg_id: 'cc' + String(i).padStart(6, '0'), search: 'm' + i + ' many' }))
    mock.store(on)
    world(on, argv => (argv.includes('list') ? { exitCode: 0, stdout: JSON.stringify({ now: NOW, agents: 'live', total: 900, rows: many }) } : listing(argv)), {
      surfaces: [surface],
    })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.command.run({ ...RUN, args: '' })
    const ui = await $.ui.mount({ ...PANE, surface })
    expect(await ui.findAll({ type: 'Button' })).toHaveLength(50)
    expect(await ui.find({ type: 'Text', text: '+70 more. Keep typing to narrow.' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '120 of 120 newest (of 900) · live' })).toBeDefined()
    await ui.input({ key: 'q', text: 'zzz', kind: 'change' })
    expect((await ui.find({ type: 'Text', text: /No match/ }))?.text).toBe('No match for "zzz" in the 120 newest. /rehydrate zzz searches them all.')
    await ui.unmount()
  })
}

test('the mobile pane says search needs a keyboard', async ($, on) => {
  mock.store(on)
  world(on, listing, { surfaces: ['mobile'] })
  await $.session.start({ cwd: '/', surface: 'mobile', isInteractive: true })
  const ui = await $.ui.mount({ ...PANE, surface: 'mobile' })
  expect((await ui.find({ type: 'Text' }))?.text).toBe('Search needs a keyboard: use /rehydrate with words here.')
  await ui.unmount()
})

test('a terminal beside a phone opens the picker', async ($, on) => {
  mock.store(on)
  const w = world(on, listing, { surfaces: ['terminal', 'mobile'] })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ran = await $.command.run({ ...RUN, args: '' })
  expect(ran.text).toBe('Rehydrate picker open. Type to search, Enter to pick, Esc to close.')
  expect(w.skill.runs).toBe(0)
})

test('a pane that is not placed says why and points at the words form', async ($, on) => {
  mock.store(on)
  world(on, listing, { open: () => ({ value: { isPlaced: false, reason: 'unasked under 144 columns (80 now)' } }) })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  const ran = await $.command.run({ ...RUN, args: '' })
  expect(ran.text).toBe('Picker not shown (unasked under 144 columns (80 now)). Use /rehydrate <words>.')
})

test('a mobile-only session runs the skill (no Input there)', async ($, on) => {
  mock.store(on)
  const w = world(on, listing, { surfaces: ['mobile'] })
  await $.session.start({ cwd: '/', surface: 'mobile', isInteractive: true })
  const ran = await $.command.run({ ...RUN, args: '' })
  expect(ran.text).toBe('skill ran')
  expect(w.skill.runs).toBe(1)
})
