// The rehydrate picker's state: what `dehydrate.py list --picker` prints, and the pane's own values.

export type Group = 'today' | 'week' | 'month' | 'older'

export type AgentsMode = 'live' | 'cached' | 'unavailable'

// `loading`, `refreshing` and `empty` follow the list; `ready` is a loaded list (no match is drawn from the
// query, not a phase); `rehydrating`, `done` and `error` follow a pick. While a pick runs, a list that comes back
// leaves the phase alone.
export type Phase = 'loading' | 'refreshing' | 'ready' | 'empty' | 'rehydrating' | 'done' | 'error'

// The `claude agents` row a session already has: `live` when it has a pid or works or waits (tag `running`),
// else it is only still listed (tag `open`). Rows cached by 0.2.0 before these fields have neither: read as live.
export type RunningCopy = { bg_id: string | null; session_id: string | null; state?: string | null; live?: boolean }

// One row per session of each manifest record (the row key is `id + ':' + bg_id`).
export type Row = {
  id: string
  kind: 'session' | 'worktree' | 'orphan' | 'main-snapshot'
  name: string
  bg_id: string | null
  session_id: string | null
  group: Group
  dehydrated_at: string
  dehydrated_ts: number
  description: string
  first_prompt: string
  branch: string | null
  repo: string | null
  repo_path: string | null
  cwd: string | null
  removed: boolean
  // its restore still stands (the worktree is back at its path): Enter launches without restoring again
  restored: boolean
  auto: boolean
  rehydrations: number
  running: RunningCopy | null
  search: string
}

// `total` counts every matching row; `rows` holds at most the 500 newest of them.
export type PickerData = { now: number; agents: AgentsMode; total?: number; rows: Row[] }

declare module 'claude-code' {
  interface PluginState {
    dehydrate: {
      query: string
      rows: Shaped<Row[]>
      phase: Phase
      status: string
      total: number
      agents: AgentsMode
    }
  }
}
