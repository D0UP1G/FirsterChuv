import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type DraftSnapshot } from '../api/client'
import type { WorkspaceTransport } from './transport'
import { useDraftController } from './useDraftController'

const baseProps = {
  userId: 'user-1', runId: 'run-1', problemId: 'problem-1', languageId: 'cpp20',
  template: 'template A', matchId: 'match-1', enabled: true,
}

function makeTransport(overrides: Partial<WorkspaceTransport> = {}): WorkspaceTransport {
  return {
    devScenario: false,
    submissionsEnabled: false,
    match: vi.fn(),
    problem: vi.fn(),
    languages: vi.fn(),
    draft: vi.fn().mockResolvedValue(null),
    saveDraft: vi.fn().mockImplementation(async (_matchId, problemId, languageId, input) => ({
      runId: input.runId, problemId, languageId, source: input.source,
      revision: input.expectedRevision + 1, updatedAt: '2026-10-09T18:00:00Z',
    })),
    submit: vi.fn(),
    submissions: vi.fn(),
    submission: vi.fn(),
    ...overrides,
  } as unknown as WorkspaceTransport
}

describe('useDraftController', () => {
  beforeEach(() => localStorage.clear())

  it('keeps typing made while the server draft is loading', async () => {
    let resolveDraft!: (snapshot: DraftSnapshot | null) => void
    const pendingDraft = new Promise<DraftSnapshot | null>((resolve) => { resolveDraft = resolve })
    const transport = makeTransport({ draft: vi.fn(() => pendingDraft) })
    const { result } = renderHook(() => useDraftController({ ...baseProps, transport }))

    await waitFor(() => expect(result.current.scopeReady).toBe(true))
    act(() => result.current.changeSource('typed before server response'))
    await act(async () => { resolveDraft(null); await pendingDraft })

    expect(result.current.source).toBe('typed before server response')
    expect(result.current.draft?.source).toBe('typed before server response')
  })

  it('starts a task switch from that task and language scoped draft', async () => {
    const transport = makeTransport()
    const { result, rerender } = renderHook(
      (props: { problemId: string; template: string }) => useDraftController({ ...baseProps, ...props, transport }),
      { initialProps: { problemId: 'problem-1', template: 'template A' } },
    )

    await waitFor(() => expect(result.current.scopeReady).toBe(true))
    act(() => result.current.changeSource('solution A'))
    rerender({ problemId: 'problem-2', template: 'template B' })
    await waitFor(() => expect(result.current.scopeReady).toBe(true))

    expect(result.current.source).toBe('template B')
    expect(result.current.source).not.toBe('solution A')
  })

  it('stops autosave on a revision conflict and exposes both copies', async () => {
    const remote: DraftSnapshot = {
      runId: 'run-1', problemId: 'problem-1', languageId: 'cpp20',
      source: 'server copy', revision: 4, updatedAt: '2026-10-09T18:00:00Z',
    }
    const transport = makeTransport({
      saveDraft: vi.fn().mockRejectedValue(new ApiError('Revision conflict', 409, 'revision_conflict', {
        current_draft: {
          run_id: remote.runId,
          problem_id: remote.problemId,
          language_id: remote.languageId,
          source: remote.source,
          revision: remote.revision,
          updated_at: remote.updatedAt,
        },
      })),
    })
    const { result } = renderHook(() => useDraftController({ ...baseProps, transport }))

    await waitFor(() => expect(result.current.scopeReady).toBe(true))
    act(() => result.current.changeSource('local copy'))
    await act(async () => { await result.current.flush() })

    expect(result.current.status).toBe('conflict')
    expect(result.current.draft?.conflict?.localSource).toBe('local copy')
    expect(result.current.draft?.conflict?.serverDraft?.source).toBe('server copy')
    expect(transport.saveDraft).toHaveBeenCalledTimes(1)
  })
})
