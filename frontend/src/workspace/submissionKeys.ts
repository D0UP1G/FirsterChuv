import type { DraftScope } from './localDrafts'

const KEY_VERSION = 1

interface StoredSubmissionKey {
  version: 1
  fingerprint: string
  key: string
}

export function submissionKeyStorageKey(scope: DraftScope): string {
  return `firsterchuv:submission-key:v${KEY_VERSION}:${[scope.userId, scope.runId, scope.problemId, scope.languageId].map(encodeURIComponent).join(':')}`
}

function readStored(storage: Storage, storageKey: string): StoredSubmissionKey | null {
  const raw = storage.getItem(storageKey)
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return null
    const value = parsed as Partial<StoredSubmissionKey>
    if (value.version !== KEY_VERSION || typeof value.fingerprint !== 'string' || typeof value.key !== 'string') return null
    return value as StoredSubmissionKey
  } catch {
    return null
  }
}

export function loadOrCreateSubmissionKey(
  scope: DraftScope,
  fingerprint: string,
  storage?: Storage,
): { key: string; persisted: boolean } {
  const storageKey = submissionKeyStorageKey(scope)
  try {
    const target = storage ?? window.localStorage
    const existing = readStored(target, storageKey)
    if (existing?.fingerprint === fingerprint) return { key: existing.key, persisted: true }
    const key = crypto.randomUUID()
    const record: StoredSubmissionKey = { version: KEY_VERSION, fingerprint, key }
    target.setItem(storageKey, JSON.stringify(record))
    return { key, persisted: true }
  } catch {
    return { key: crypto.randomUUID(), persisted: false }
  }
}

export function clearSubmissionKey(
  scope: DraftScope,
  fingerprint: string,
  storage?: Storage,
): boolean {
  try {
    const target = storage ?? window.localStorage
    const storageKey = submissionKeyStorageKey(scope)
    const existing = readStored(target, storageKey)
    if (existing?.fingerprint === fingerprint) target.removeItem(storageKey)
    return true
  } catch {
    return false
  }
}
