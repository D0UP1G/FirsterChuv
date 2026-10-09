import { afterEach, describe, expect, it, vi } from 'vitest'
import { createDevWorkspaceTransport } from './devTransport'

describe('participant workspace dev transport', () => {
  afterEach(() => vi.useRealTimers())

  it('decreases the fixture timer as the running match progresses', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-09T18:00:00Z'))
    const transport = createDevWorkspaceTransport(new URLSearchParams('scenario=workspace-ui'))
    const first = await transport.match('match-1')

    vi.advanceTimersByTime(5000)
    const later = await transport.match('match-1')

    expect(later.remainingMs).toBe(first.remainingMs - 5000)
    expect(later.elapsedMs).toBe(first.elapsedMs + 5000)
  })
})
