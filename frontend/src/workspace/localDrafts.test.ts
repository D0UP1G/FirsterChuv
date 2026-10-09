import { beforeEach, describe, expect, it } from 'vitest'
import type { DraftSnapshot } from '../api/client'
import {
  MAX_DRAFT_BYTES,
  createLocalDraft,
  draftStorageKey,
  readLocalDraft,
  reconcileDraft,
  resolveDraftConflict,
  setDraftConflict,
  sourceByteLength,
  updateLocalSource,
  writeLocalDraft,
  type DraftScope,
} from './localDrafts'

const scope: DraftScope = { userId: 'user-1', runId: 'run-1', problemId: 'problem-1', languageId: 'cpp20' }

function snapshot(source: string, revision: number): DraftSnapshot {
  return { ...scope, source, revision, updatedAt: '2026-10-09T18:00:00Z' }
}

describe('private local drafts', () => {
  beforeEach(() => localStorage.clear())

  it('namespaces drafts by user, run, problem, and language and restores saved text', () => {
    const draft = updateLocalSource(createLocalDraft(scope, 'template'), 'int main() {}')
    writeLocalDraft(draft)

    expect(readLocalDraft(scope)?.source).toBe('int main() {}')
    expect(draftStorageKey(scope)).not.toBe(draftStorageKey({ ...scope, userId: 'user-2' }))
    expect(draftStorageKey(scope)).not.toBe(draftStorageKey({ ...scope, runId: 'run-2' }))
    expect(draftStorageKey(scope)).not.toBe(draftStorageKey({ ...scope, problemId: 'problem-2' }))
    expect(draftStorageKey(scope)).not.toBe(draftStorageKey({ ...scope, languageId: 'python3' }))
  })

  it('counts UTF-8 bytes and rejects drafts above 32 KiB', () => {
    const tooLarge = 'я'.repeat(Math.floor(MAX_DRAFT_BYTES / 2) + 1)
    expect(sourceByteLength(tooLarge)).toBeGreaterThan(MAX_DRAFT_BYTES)
    expect(() => updateLocalSource(createLocalDraft(scope), tooLarge)).toThrow('32 KiB')
  })

  it('preserves the local and server versions until the owner chooses one', () => {
    const local = updateLocalSource(createLocalDraft(scope), 'local solution')
    const conflicted = setDraftConflict(local, snapshot('server solution', 4))

    expect(conflicted.source).toBe('local solution')
    expect(conflicted.conflict?.localSource).toBe('local solution')
    expect(conflicted.conflict?.serverDraft?.source).toBe('server solution')
    expect(resolveDraftConflict(conflicted, 'server')).toMatchObject({
      source: 'server solution', serverSource: 'server solution', serverRevision: 4, conflict: null,
    })
    expect(resolveDraftConflict(conflicted, 'local')).toMatchObject({
      source: 'local solution', serverSource: 'server solution', serverRevision: 4, conflict: null,
    })
  })

  it('detects concurrent edits during server reconciliation instead of overwriting either copy', () => {
    const edited = updateLocalSource(createLocalDraft(scope, ''), 'typed while loading')
    const result = reconcileDraft(edited, snapshot('another browser', 1), scope)

    expect(result.kind).toBe('conflict')
    expect(result.draft.source).toBe('typed while loading')
    expect(result.draft.conflict?.serverDraft?.source).toBe('another browser')
  })
})
