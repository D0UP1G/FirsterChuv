import type { DraftSnapshot } from '../api/client'

export const MAX_DRAFT_BYTES = 32 * 1024
const STORAGE_VERSION = 1

export interface DraftScope {
  userId: string
  runId: string
  problemId: string
  languageId: string
}

export interface DraftConflict {
  localSource: string
  serverDraft: DraftSnapshot | null
  detectedAt: string
}

export interface LocalDraft {
  version: 1
  scope: DraftScope
  source: string
  serverSource: string
  localRevision: number
  serverRevision: number
  updatedAt: string
  conflict: DraftConflict | null
}

export type DraftReconciliation =
  | { kind: 'ready'; draft: LocalDraft }
  | { kind: 'conflict'; draft: LocalDraft }

export function draftStorageKey(scope: DraftScope): string {
  return `firsterchuv:draft:v${STORAGE_VERSION}:${[scope.userId, scope.runId, scope.problemId, scope.languageId].map(encodeURIComponent).join(':')}`
}

export function sourceByteLength(source: string): number {
  return new TextEncoder().encode(source).byteLength
}

export function createLocalDraft(scope: DraftScope, source = '', serverRevision = 0, serverSource = ''): LocalDraft {
  return {
    version: STORAGE_VERSION,
    scope,
    source,
    serverSource,
    localRevision: 0,
    serverRevision,
    updatedAt: new Date().toISOString(),
    conflict: null,
  }
}

function isDraftForScope(value: unknown, scope: DraftScope): value is LocalDraft {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Partial<LocalDraft>
  return record.version === STORAGE_VERSION
    && record.scope?.userId === scope.userId
    && record.scope?.runId === scope.runId
    && record.scope?.problemId === scope.problemId
    && record.scope?.languageId === scope.languageId
    && typeof record.source === 'string'
    && sourceByteLength(record.source) <= MAX_DRAFT_BYTES
    && typeof record.serverSource === 'string'
    && Number.isInteger(record.localRevision)
    && Number.isInteger(record.serverRevision)
}

export function readLocalDraft(scope: DraftScope, storage: Storage = window.localStorage): LocalDraft | null {
  const raw = storage.getItem(draftStorageKey(scope))
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    return isDraftForScope(parsed, scope) ? parsed : null
  } catch {
    return null
  }
}

export function writeLocalDraft(draft: LocalDraft, storage: Storage = window.localStorage): void {
  if (sourceByteLength(draft.source) > MAX_DRAFT_BYTES) {
    throw new Error('Черновик превышает лимит 32 KiB.')
  }
  storage.setItem(draftStorageKey(draft.scope), JSON.stringify(draft))
}

export function updateLocalSource(previous: LocalDraft, source: string): LocalDraft {
  if (sourceByteLength(source) > MAX_DRAFT_BYTES) {
    throw new Error('Черновик превышает лимит 32 KiB.')
  }
  if (previous.source === source) return previous
  return {
    ...previous,
    source,
    localRevision: previous.localRevision + 1,
    updatedAt: new Date().toISOString(),
    conflict: previous.conflict ? { ...previous.conflict, localSource: source } : null,
  }
}

export function reconcileDraft(local: LocalDraft | null, remote: DraftSnapshot | null, scope: DraftScope): DraftReconciliation {
  if (!local) {
    return { kind: 'ready', draft: remote ? createLocalDraft(scope, remote.source, remote.revision, remote.source) : createLocalDraft(scope) }
  }

  if (!remote) {
    if (local.serverRevision === 0 && local.serverSource === '') return { kind: 'ready', draft: local }
    const draft = { ...local, conflict: { localSource: local.source, serverDraft: null, detectedAt: new Date().toISOString() } }
    return { kind: 'conflict', draft }
  }

  if (local.conflict) {
    const draft = { ...local, conflict: { ...local.conflict, serverDraft: remote } }
    return { kind: 'conflict', draft }
  }

  if (remote.revision < local.serverRevision) {
    const draft = { ...local, conflict: { localSource: local.source, serverDraft: remote, detectedAt: new Date().toISOString() } }
    return { kind: 'conflict', draft }
  }

  const hasLocalChanges = local.localRevision > 0 && local.source !== local.serverSource
  const serverHasChanges = remote.revision > local.serverRevision || remote.source !== local.serverSource

  if (serverHasChanges && hasLocalChanges && local.source !== remote.source) {
    const draft = { ...local, conflict: { localSource: local.source, serverDraft: remote, detectedAt: new Date().toISOString() } }
    return { kind: 'conflict', draft }
  }

  if (!hasLocalChanges || remote.source === local.source) {
    return {
      kind: 'ready',
      draft: { ...local, source: remote.source, serverSource: remote.source, serverRevision: remote.revision, updatedAt: new Date().toISOString() },
    }
  }

  return { kind: 'ready', draft: { ...local, serverSource: remote.source, serverRevision: remote.revision, updatedAt: new Date().toISOString() } }
}

export function setDraftConflict(local: LocalDraft, serverDraft: DraftSnapshot | null): LocalDraft {
  return {
    ...local,
    conflict: { localSource: local.source, serverDraft, detectedAt: new Date().toISOString() },
  }
}

export function resolveDraftConflict(local: LocalDraft, choice: 'local' | 'server'): LocalDraft {
  if (!local.conflict) return local
  if (choice === 'local') {
    return {
      ...local,
      localRevision: local.localRevision + 1,
      serverRevision: local.conflict.serverDraft?.revision ?? 0,
      serverSource: local.conflict.serverDraft?.source ?? '',
      conflict: null,
      updatedAt: new Date().toISOString(),
    }
  }

  const serverDraft = local.conflict.serverDraft
  return {
    ...local,
    source: serverDraft?.source ?? '',
    serverSource: serverDraft?.source ?? '',
    localRevision: local.localRevision + 1,
    serverRevision: serverDraft?.revision ?? 0,
    conflict: null,
    updatedAt: new Date().toISOString(),
  }
}
