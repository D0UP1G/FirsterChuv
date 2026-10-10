import { beforeEach, describe, expect, it } from 'vitest'
import { clearSubmissionKey, loadOrCreateSubmissionKey, submissionKeyStorageKey } from './submissionKeys'
import type { DraftScope } from './localDrafts'

const scope: DraftScope = { userId: 'user-1', runId: 'run-1', problemId: 'problem-1', languageId: 'cpp20' }

describe('submission idempotency keys', () => {
  beforeEach(() => localStorage.clear())

  it('reuses a request key after reload for the same source revision', () => {
    const first = loadOrCreateSubmissionKey(scope, 'run-1:problem-1:cpp20:3')
    const afterReload = loadOrCreateSubmissionKey(scope, 'run-1:problem-1:cpp20:3')

    expect(first.persisted).toBe(true)
    expect(afterReload).toEqual(first)
  })

  it('uses a new key for an edited revision and clears only the accepted revision', () => {
    const previous = loadOrCreateSubmissionKey(scope, 'revision-3')
    const current = loadOrCreateSubmissionKey(scope, 'revision-4')

    expect(current.key).not.toBe(previous.key)
    expect(clearSubmissionKey(scope, 'revision-3')).toBe(true)
    expect(loadOrCreateSubmissionKey(scope, 'revision-4')).toEqual(current)
  })

  it('does not store source code and isolates keys by owner', () => {
    const storageKey = submissionKeyStorageKey(scope)
    const request = loadOrCreateSubmissionKey(scope, 'revision-with-private-source-hash')
    const stored = localStorage.getItem(storageKey) ?? ''
    const otherOwner = loadOrCreateSubmissionKey({ ...scope, userId: 'user-2' }, 'revision-with-private-source-hash')

    expect(stored).not.toContain('solution source')
    expect(otherOwner.key).not.toBe(request.key)
    expect(submissionKeyStorageKey({ ...scope, userId: 'user-2' })).not.toBe(storageKey)
  })

  it('keeps the key usable in this tab if browser storage is unavailable', () => {
    const brokenStorage = {
      getItem() { throw new Error('blocked') },
      setItem() { throw new Error('blocked') },
      removeItem() { throw new Error('blocked') },
    } as unknown as Storage

    const first = loadOrCreateSubmissionKey(scope, 'revision-1', brokenStorage)
    const second = loadOrCreateSubmissionKey(scope, 'revision-1', brokenStorage)
    expect(first.persisted).toBe(false)
    expect(second.persisted).toBe(false)
    expect(second.key).not.toBe(first.key)
    expect(clearSubmissionKey(scope, 'revision-1', brokenStorage)).toBe(false)
  })
})
