// dehydrate mod: a bare /rehydrate opens a searchable picker of dehydrated sessions and worktrees, and a
// session that ends kicks a detached `dehydrate.py auto --session <id>` (DESIGN 4 and 5). Everything that
// reads or writes the manifest stays in scripts/dehydrate.py; this module only draws and runs it.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { AgentsMode, Group, PickerData, Row } from '../types'

const PANE = 'dehydrate-picker'
const CACHE = 'picker-cache'
const MAX_ROWS = 500
const MAX_DRAWN = 50 // rows drawn at once; the rest are a "+N more" line (a drawing holds 100,000 characters)
const SEARCH_CAP = 2048
const NARROW = 60 // under this many body columns a row drops its repo and branch

// Change the shape tag when Row's fields change: it declines what an earlier version stored.
const query = atom({ plugin: 'dehydrate', key: 'query' } as const, '')
const rows = atom({ plugin: 'dehydrate', key: 'rows' } as const, [], { shape: 'rows-2' })
const phase = atom({ plugin: 'dehydrate', key: 'phase' } as const, 'loading')
const status = atom({ plugin: 'dehydrate', key: 'status' } as const, '')
const total = atom({ plugin: 'dehydrate', key: 'total' } as const, 0)
const agents = atom({ plugin: 'dehydrate', key: 'agents' } as const, 'unavailable')

// Not drawn from, so module values (a hot reload resets them, and `phase` still guards a pick then).
// A pick in flight: a list that returns, or a reopen, must not reset the phase under it.
let inFlight = false
// Which open of the pane a pick's close timer belongs to: a pane reopened since is not closed by it.
let openSeq = 0

const GROUPS: readonly [Group, string][] = [
  ['today', 'Today'],
  ['week', 'This week'],
  ['month', 'This month'],
  ['older', 'Older'],
]

// The session ended for good: /exit, a signal, a -p run finishing, a logout. `clear` and `resume` go on.
const KICK = new Set(['prompt_input_exit', 'other', 'logout'])

function script($: EngineInterface): string {
  return $.plugin.root + '/scripts/dehydrate.py'
}

// Every word must be a substring of the row's haystack, as `dehydrate.py list <words>` matches.
function matches(row: Row, q: string): boolean {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean)
  return words.every(w => row.search.includes(w))
}

function rowKey(row: Row): string {
  return row.id + ':' + (row.bg_id ?? '')
}

function shownId(row: Row): string {
  return row.running?.bg_id ?? row.bg_id ?? ''
}

function isLive(row: Row): boolean {
  return row.running !== null && row.running.live !== false
}

function isPickerData(v: unknown): v is PickerData {
  return typeof v === 'object' && v !== null && Array.isArray((v as PickerData).rows)
}

// What the store keeps: at most 500 rows, descriptions and haystacks cut, so it stays far under the 4 MiB cap.
function trimmed(list: readonly Row[]): Row[] {
  return list.slice(0, MAX_ROWS).map(r => ({
    ...r,
    restored: r.restored ?? false,
    description: r.description.slice(0, 200),
    search: r.search.slice(0, SEARCH_CAP),
  }))
}

async function show($: EngineInterface, data: PickerData) {
  const list = trimmed(data.rows)
  await update($, rows, () => list)
  await update($, agents, () => data.agents)
  await update($, total, () => data.total ?? list.length)
  if (!inFlight) await update($, phase, () => (list.length === 0 ? 'empty' : 'ready'))
}

async function load($: EngineInterface) {
  try {
    const r = await $.process.run(
      ['python3', script($), 'list', '--picker', '--agents-timeout', '15'],
      { timeoutMs: 30_000 },
    )
    if (r.isStdoutTruncated) throw new Error('the list is over 4 MiB, more than the pane can read. Use /rehydrate <words>')
    if (r.exitCode !== 0) throw new Error(r.stderr.trim() || 'list --picker exited ' + r.exitCode)
    const data: unknown = JSON.parse(r.stdout)
    if (!isPickerData(data)) throw new Error('list --picker printed no rows')
    await show($, data)
    await $.store.set(CACHE, { ...data, rows: trimmed(data.rows) }).catch(() => undefined)
  } catch (err) {
    if (inFlight) return // the pick's own status and phase stand
    const had = (await read($, rows)).length
    await update($, phase, () => (had > 0 ? 'ready' : 'error'))
    await update($, status, () => 'Failed: ' + String(err).slice(0, 200))
  }
}

async function openPicker($: EngineInterface): Promise<{ text: string }> {
  openSeq++
  await update($, query, () => '')
  if (!inFlight) await update($, status, () => '')
  const cached = await $.store.get(CACHE)
  if (isPickerData(cached) && cached.rows.length > 0) {
    await show($, cached)
    if (!inFlight) await update($, phase, () => 'refreshing')
  } else if (!inFlight) {
    await update($, rows, () => [])
    await update($, phase, () => 'loading')
  }
  const opened = await $.ui.open({ id: PANE, title: 'Rehydrate', focus: true, closeOnEscape: true, holdToasts: true })
  await load($)
  return {
    text: opened.isPlaced
      ? 'Rehydrate picker open. Type to search, Enter to pick, Esc to close.'
      : 'Picker not shown (' + opened.reason + '). Use /rehydrate <words>.',
  }
}

type Launched = { bg_id?: string | null; reused?: boolean; skipped?: boolean; note?: string | null }
type Rehydrated = {
  path?: string | null
  notes?: string[]
  launched?: Launched[]
  resume?: { cwd?: string }[]
  error?: string
}

function doneText(row: Row, out: Rehydrated): string {
  const l = out.launched?.[0]
  const where = out.path ?? out.resume?.[0]?.cwd ?? row.cwd ?? ''
  if (l?.reused && l.note) return l.note
  if (l?.reused) return 'Already running as ' + (l.bg_id ?? '') + '. claude attach ' + (l.bg_id ?? '')
  if (l?.bg_id && !l.note) return 'Back as ' + l.bg_id + ' in claude agents · ' + where
  const why = l?.note ?? out.notes?.find(n => /transcript|launch/.test(n)) ?? 'no session to resume'
  return 'Restored ' + where + '. Not launched: ' + why
}

async function pick($: EngineInterface, row: Row) {
  if (inFlight || (await read($, phase)) === 'rehydrating') return
  if (row.running) {
    const id = row.running.bg_id ?? ''
    const text = isLive(row)
      ? 'Already running as ' + id + '. claude attach ' + id
      : 'Still open in claude agents as ' + id + (row.running.state ? ' (' + row.running.state + ')' : '') +
        '. claude attach ' + id
    await update($, status, () => text)
    return
  }
  if (!row.removed && row.kind === 'worktree') {
    await update($, status, () => 'Still in place at ' + (row.cwd ?? ''))
    return
  }
  // `claude rm` refused this session when it was dehydrated. A live listing that no longer shows it means it was
  // closed since; any other listing cannot tell, and a launch could start a copy beside it.
  if (!row.removed && row.kind === 'session' && (await read($, agents)) !== 'live') {
    await update($, status, () => 'May still be open (claude rm refused it): check claude agents, then /rehydrate ' + row.id)
    return
  }
  inFlight = true
  const seq = openSeq
  await update($, phase, () => 'rehydrating')
  await update($, status, () => 'Rehydrating ' + row.name + ' (' + shownId(row) + ')...')
  let text = ''
  let ok = false
  try {
    const r = await $.process.run(['python3', script($), 'rehydrate', row.id, '--launch', '--json'], {
      timeoutMs: 600_000,
    })
    let out: Rehydrated = {}
    try {
      out = JSON.parse(r.stdout) as Rehydrated
    } catch {
      out = {}
    }
    ok = r.exitCode === 0 && out.error === undefined
    text = ok ? doneText(row, out) : 'Failed: ' + (out.error ?? (r.stderr.trim() || r.stdout.trim())).slice(0, 200)
  } catch (err) {
    text = 'Failed: ' + String(err).slice(0, 200)
  } finally {
    inFlight = false
  }
  await update($, status, () => text)
  // The pane holds toasts while open, so this shows once it closes, Esc during a long restore included.
  try {
    $.ui.toast(text)
  } catch {
    // no toast surface: the status line already says it
  }
  // An error leaves the rows live again. rehydrate checks every archive file before it changes anything, and a
  // restore that did change the disk is recorded, so the row then reads restored and Enter only launches.
  await update($, phase, () => (ok ? 'done' : 'error'))
  if (ok) {
    $.clock.after(1000, () => {
      if (seq === openSeq) void $.ui.close({ id: PANE })
    })
  }
}

async function pickFirst($: EngineInterface, q: string) {
  const first = (await read($, rows)).find(r => matches(r, q))
  if (first) await pick($, first)
}

async function setQuery($: EngineInterface, v: string) {
  await update($, query, () => v)
}

function fit(s: string, n: number): string {
  if (n <= 0) return ''
  return s.length <= n ? s : s.slice(0, Math.max(0, n - 1)) + '…'
}

// One row's texts, cut to the pane's width so a row never wraps: name, then id · kind · repo  branch (only the
// id and kind when narrow), then its tags.
function rowParts(r: Row, cols: number): { name: string; dim: string; tags: string[] } {
  const tags: string[] = []
  if (r.running) tags.push(isLive(r) ? 'running' : 'open')
  if (r.restored) tags.push('restored')
  if (!r.removed && r.kind === 'worktree') tags.push('in place')
  const tagLen = tags.reduce((n, t) => n + t.length + 1, 0)
  const wide = cols >= NARROW
  const dimFull =
    [shownId(r), r.kind, wide ? r.repo ?? '' : ''].filter(Boolean).join(' · ') + (wide && r.branch ? '  ' + r.branch : '')
  const room = cols - tagLen - 1 // the Button's own mark
  const name = fit(r.name, Math.max(8, room - Math.min(dimFull.length + 2, Math.floor(room / 2))))
  const dim = fit(dimFull, room - name.length - 2)
  return { name, dim: dim.length >= 4 ? dim : '', tags }
}

export const register: Register = on => {
  on('command.run', { command: 'dehydrate:rehydrate' }, async ($, e, next) => {
    const args = (e.args ?? '').trim()
    if (args !== '') return next(e) // /rehydrate <words>: the skill, unchanged
    const surfaces = await $.session.surfaces()
    if (surfaces.length > 0 && surfaces.every(s => s === 'mobile')) return next(e) // no Input there
    return openPicker($)
  }).catch(($, e, next) => next(e)) // any failure of the mod falls back to the skill

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    if (e.surface === 'mobile') {
      const { Text } = $.ui.resolve(e)
      return <Text dimColor>Search needs a keyboard: use /rehydrate with words here.</Text>
    }
    const { Box, Text, Button, Input } = $.ui.resolve(e)
    const q = await read($, query)
    const all = await read($, rows)
    const ph = await read($, phase)
    const st = await read($, status)
    const ag = await read($, agents)
    const tot = Math.max(await read($, total), all.length)
    const cols = e.props.bodyColumns > 0 ? e.props.bodyColumns : 80
    const shown = all.filter(r => matches(r, q))
    const drawn = shown.slice(0, MAX_DRAWN)
    const busy = ph === 'rehydrating'
    const partial = tot > all.length
    const agentsLabel: Record<AgentsMode, string> = { live: 'live', cached: 'cached', unavailable: 'agents unavailable' }
    const head =
      shown.length + ' of ' + all.length + (partial ? ' newest (of ' + tot + ')' : '') + ' · ' + agentsLabel[ag] +
      (ph === 'refreshing' ? ' · refreshing' : '')
    const empty =
      ph === 'loading' && all.length === 0
        ? 'Loading dehydrated sessions...'
        : ph === 'empty' || (all.length === 0 && ph !== 'error')
          ? 'Nothing has been dehydrated yet. /dehydrate closes idle sessions.'
          : all.length > 0 && shown.length === 0
            ? 'No match for "' + q + '"' + (partial ? ' in the ' + all.length + ' newest. /rehydrate ' + q + ' searches them all.' : '.')
            : ''
    return (
      <Box flexDirection="column">
        <Text dimColor>{head}</Text>
        <Input
          key="q"
          label="Search: "
          placeholder="name, prompt, branch, repo"
          value={q}
          autoFocus
          onInput={(v: string) => setQuery($, v)}
          onSubmit={(v: string) => pickFirst($, v)}
        />
        {empty !== '' && <Text dimColor>{empty}</Text>}
        {empty.startsWith('No match') && <Text dimColor>Esc to close, or keep typing.</Text>}
        {GROUPS.map(([g, label]) => {
          const list = drawn.filter(r => r.group === g)
          if (list.length === 0) return null
          return (
            <Box key={'g-' + g} flexDirection="column">
              <Text bold>{label}</Text>
              {list.map(r => {
                const p = rowParts(r, cols)
                return (
                  <Button key={rowKey(r)} plain onPress={() => pick($, r)}>
                    <Text dimColor={busy}>{p.name}</Text>
                    {p.dim ? '  ' : ''}
                    {p.dim ? <Text dimColor>{p.dim}</Text> : ''}
                    {p.tags.includes('running') ? <Text color="success"> running</Text> : ''}
                    {p.tags.some(t => t !== 'running') ? (
                      <Text dimColor>{' ' + p.tags.filter(t => t !== 'running').join(' ')}</Text>
                    ) : (
                      ''
                    )}
                  </Button>
                )
              })}
            </Box>
          )
        })}
        {shown.length > drawn.length && (
          <Text dimColor>{'+' + (shown.length - drawn.length) + ' more. Keep typing to narrow.'}</Text>
        )}
        <Text dimColor>Enter rehydrate · Tab/arrows move · Esc close</Text>
        {st !== '' && <Text>{st}</Text>}
      </Box>
    )
  })

  // Best effort: the SessionStart sweep catches what this misses (`claude stop` fires no session.end). HUP is
  // ignored in the subshell, and so in the python it starts: until the script's setsid it is in this process's
  // group, and a closing terminal or pane hangs that group up.
  on('session.end', async ($, e, next) => {
    if (KICK.has(e.reason)) {
      await $.process
        .run(
          [
            '/bin/sh',
            '-c',
            '(trap \'\' HUP; nice -n 19 python3 "$0" auto --detach --session "$1" >/dev/null 2>&1 &) >/dev/null 2>&1',
            script($),
            e.sessionId,
          ],
          { timeoutMs: 1000 },
        )
        .catch(() => undefined)
    }
    return next(e)
  }).catch(($, e, next) => next(e))
}
