import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, type DraftSnapshot } from '../api/client'
import {
  createLocalDraft,
  draftStorageKey,
  readLocalDraft,
  reconcileDraft,
  resolveDraftConflict,
  setDraftConflict,
  updateLocalSource,
  writeLocalDraft,
  type DraftScope,
  type LocalDraft,
} from './localDrafts'
import type { WorkspaceTransport } from './transport'

export type DraftSyncStatus = 'locked' | 'loading' | 'local' | 'saving' | 'saved' | 'conflict' | 'unavailable' | 'storage-error'

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось синхронизировать черновик.'
}

function snapshotFromConflict(error: ApiError): DraftSnapshot | null | undefined {
  if (!error.fields || typeof error.fields !== 'object') return undefined
  const fields = error.fields as Record<string, unknown>
  const raw = Object.hasOwn(fields, 'current_draft') ? fields.current_draft : fields.currentDraft
  if (raw === null) return null
  if (!raw || typeof raw !== 'object') return undefined
  const value = raw as Record<string, unknown>
  const runId = value.runId ?? value.run_id
  const problemId = value.problemId ?? value.problem_id
  const languageId = value.languageId ?? value.language_id
  const updatedAt = value.updatedAt ?? value.updated_at
  if (typeof runId !== 'string' || typeof problemId !== 'string' || typeof languageId !== 'string'
    || typeof value.source !== 'string' || typeof value.revision !== 'number' || typeof updatedAt !== 'string') return undefined
  return { runId, problemId, languageId, source: value.source, revision: value.revision, updatedAt }
}

export function useDraftController({
  userId,
  runId,
  problemId,
  languageId,
  template,
  matchId,
  enabled,
  transport,
}: {
  userId: string
  runId: string
  problemId: string
  languageId: string
  template: string
  matchId: string
  enabled: boolean
  transport: WorkspaceTransport
}) {
  const scope = useMemo<DraftScope>(() => ({ userId, runId, problemId, languageId }), [userId, runId, problemId, languageId])
  const key = useMemo(() => draftStorageKey(scope), [scope])
  const [draft, setDraft] = useState<LocalDraft | null>(null)
  const [source, setSource] = useState('')
  const [status, setStatus] = useState<DraftSyncStatus>(enabled ? 'loading' : 'locked')
  const [syncError, setSyncError] = useState<string | null>(null)
  const [readyKey, setReadyKey] = useState('')
  const draftRef = useRef<LocalDraft | null>(null)
  const activeKeyRef = useRef(key)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const flushRef = useRef<() => Promise<void>>(async () => undefined)
  const inFlightRef = useRef(new Map<string, Promise<void>>())

  const persist = useCallback((next: LocalDraft): boolean => {
    try {
      writeLocalDraft(next)
      setSyncError(null)
      return true
    } catch {
      setSyncError('Локальное хранилище недоступно; несохранённый текст останется только в этой вкладке.')
      setStatus('storage-error')
      return false
    }
  }, [])

  const scheduleSave = useCallback((delay = 500) => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      timerRef.current = null
      void flushRef.current()
    }, delay)
  }, [])

  const flush = useCallback(async () => {
    const current = draftRef.current
    if (!enabled || !current || current.conflict || current.source === current.serverSource || current.localRevision === 0) return
    const scopeKey = draftStorageKey(current.scope)
    const activeRequest = inFlightRef.current.get(scopeKey)
    if (activeRequest) return activeRequest

    const sent: LocalDraft = { ...current }
    setStatus('saving')
    const save = (async () => {
      try {
        const remote = await transport.saveDraft(matchId, problemId, languageId, {
          runId,
          source: sent.source,
          expectedRevision: sent.serverRevision,
        })
        const latest = draftRef.current && draftStorageKey(draftRef.current.scope) === scopeKey ? draftRef.current : sent
        const next = { ...latest, serverRevision: remote.revision, serverSource: remote.source, updatedAt: new Date().toISOString() }
        try { writeLocalDraft(next) } catch {
          setSyncError('Черновик записан на сервере, но локальную копию обновить не удалось.')
        }
        if (activeKeyRef.current === scopeKey) {
          draftRef.current = next
          setDraft(next)
          setStatus(next.source === next.serverSource ? 'saved' : 'local')
          if (next.source !== next.serverSource) scheduleSave(0)
        }
        if (next.source === next.serverSource) setSyncError(null)
      } catch (error) {
        const latest = draftRef.current && draftStorageKey(draftRef.current.scope) === scopeKey ? draftRef.current : sent
        if (error instanceof ApiError && error.status === 409) {
          const serverDraft = snapshotFromConflict(error)
          if (serverDraft !== undefined) {
            const conflicted = setDraftConflict(latest, serverDraft)
            try { writeLocalDraft(conflicted) } catch { /* memory copy stays available */ }
            if (activeKeyRef.current === scopeKey) {
              draftRef.current = conflicted
              setDraft(conflicted)
              setStatus('conflict')
            }
            setSyncError('Черновик изменился на сервере. Выберите, какую версию оставить.')
            return
          }
        }
        if (activeKeyRef.current === scopeKey) {
          setStatus('unavailable')
          setSyncError(`Локальная копия сохранена. Синхронизация с сервером не удалась: ${errorMessage(error)}`)
        }
      }
    })()
    inFlightRef.current.set(scopeKey, save)
    try {
      await save
    } finally {
      inFlightRef.current.delete(scopeKey)
    }
  }, [enabled, languageId, matchId, problemId, runId, scheduleSave, transport])

  useEffect(() => {
    flushRef.current = flush
  }, [flush])

  useEffect(() => {
    activeKeyRef.current = key
    let active = true
    if (timerRef.current) clearTimeout(timerRef.current)
    setSyncError(null)
    setReadyKey('')
    if (!enabled) {
      setDraft(null)
      draftRef.current = null
      setSource('')
      setStatus('locked')
      return () => { active = false }
    }

    setStatus('loading')
    let local: LocalDraft
    try {
      local = readLocalDraft(scope) ?? createLocalDraft(scope, template)
    } catch {
      local = createLocalDraft(scope, template)
      setSyncError('Не удалось прочитать локальный черновик; откройте сохранённую копию или начните новый.')
    }
    draftRef.current = local
    setDraft(local)
    setSource(local.source)
    setReadyKey(key)
    try { writeLocalDraft(local) } catch { setStatus('storage-error') }

    void transport.draft(matchId, problemId, runId, languageId).then((remote) => {
      if (!active) return
      const latestLocal = draftRef.current && draftStorageKey(draftRef.current.scope) === key ? draftRef.current : local
      const result = reconcileDraft(latestLocal, remote, scope)
      draftRef.current = result.draft
      setDraft(result.draft)
      setSource(result.draft.source)
      try { writeLocalDraft(result.draft) } catch { setSyncError('Локальное хранилище недоступно; серверная копия не заменена.') }
      if (result.kind === 'conflict') {
        setStatus('conflict')
        setSyncError('Локальная и серверная версии различаются. Обе сохранены до вашего выбора.')
      } else if (result.draft.conflict) {
        setStatus('conflict')
      } else if (result.draft.source !== result.draft.serverSource && result.draft.localRevision > 0) {
        setStatus('local')
        scheduleSave(0)
      } else {
        setStatus(result.draft.serverRevision > 0 ? 'saved' : 'local')
      }
    }).catch((error: unknown) => {
      if (!active) return
      setStatus('unavailable')
      setSyncError(`Локальный черновик доступен. Серверное хранилище недоступно: ${errorMessage(error)}`)
    })

    const flushOnHide = () => { void flush() }
    window.addEventListener('pagehide', flushOnHide)
    document.addEventListener('visibilitychange', flushOnHide)
    return () => {
      active = false
      window.removeEventListener('pagehide', flushOnHide)
      document.removeEventListener('visibilitychange', flushOnHide)
      if (timerRef.current) clearTimeout(timerRef.current)
      void flush()
    }
  }, [enabled, flush, key, languageId, matchId, problemId, runId, scheduleSave, scope, template, transport])

  const changeSource = useCallback((nextSource: string) => {
    const previous = draftRef.current ?? createLocalDraft(scope, template)
    try {
      const next = updateLocalSource(previous, nextSource)
      draftRef.current = next
      setDraft(next)
      setSource(nextSource)
      persist(next)
      if (next.conflict) {
        setStatus('conflict')
      } else {
        setStatus('local')
        if (next.localRevision > 0 && next.source !== next.serverSource) scheduleSave()
      }
    } catch (error) {
      setSource(nextSource)
      setSyncError(errorMessage(error))
      setStatus('storage-error')
    }
  }, [persist, scheduleSave, scope, template])

  const chooseConflictVersion = useCallback((choice: 'local' | 'server') => {
    const current = draftRef.current
    if (!current?.conflict) return
    const resolved = resolveDraftConflict(current, choice)
    draftRef.current = resolved
    setDraft(resolved)
    setSource(resolved.source)
    persist(resolved)
    setSyncError(null)
    if (resolved.source !== resolved.serverSource && resolved.localRevision > 0) {
      setStatus('local')
      scheduleSave(0)
    } else {
      setStatus(resolved.serverRevision > 0 ? 'saved' : 'local')
    }
  }, [persist, scheduleSave])

  return { source, changeSource, draft, status, syncError, flush, chooseConflictVersion, scopeReady: enabled && readyKey === key }
}
