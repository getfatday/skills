import { expect, test } from 'claude-code/testing'

const SID = 'ff385cfe-dde4-4e0e-9bdb-5ec4042d9190'

for (const surface of ['terminal', 'desktop'] as const) {
  test('an ended session kicks a detached auto run and still ends, on ' + surface, async ($, on) => {
    const calls: string[][] = []
    let ended = 0
    on('session.start', (_, e) => ({ cwd: e.cwd }))
    on('session.end', (_, e) => {
      ended++
      return { sessionId: e.sessionId }
    })
    on('process.run', (_, e) => {
      calls.push([...e.argv])
      return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    await $.session.end({ reason: 'prompt_input_exit', sessionId: SID, resume: { id: SID } })
    expect(calls).toHaveLength(1)
    expect(calls[0]?.[0]).toBe('/bin/sh')
    expect(calls[0]?.join(' ')).toContain('auto --detach --session')
    expect(calls[0]?.[2]).toMatch(/^\(trap '' HUP; nice -n 19 python3 /) // a closing terminal must not kill it
    expect(calls[0]?.at(-1)).toBe(SID)
    expect(ended).toBe(1)
    // a /clear goes on in the same process: no kick
    await $.session.end({ reason: 'clear', sessionId: SID, resume: { id: SID } })
    expect(calls).toHaveLength(1)
    expect(ended).toBe(2)
  })

  test('a kick that fails still lets the session end, on ' + surface, async ($, on) => {
    let ended = 0
    on('session.start', (_, e) => ({ cwd: e.cwd }))
    on('session.end', (_, e) => {
      ended++
      return { sessionId: e.sessionId }
    })
    on('process.run', () => {
      throw new Error('spawn refused')
    })
    await $.session.start({ cwd: '/', surface, isInteractive: true })
    const r = await $.session.end({ reason: 'other', sessionId: SID, resume: { id: SID } })
    expect(r.sessionId).toBe(SID)
    expect(ended).toBe(1)
  })
}
