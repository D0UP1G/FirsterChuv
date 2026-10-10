import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import {
  ApiError,
  type MatchProblemDetails,
  type MatchProblemLanguage,
  type MatchTaskState,
  type MatchView,
  type SubmissionDetail,
  type SubmissionReceipt,
  type SubmissionVerdict,
} from '../api/client'
import { useAuth } from '../auth/useAuth'
import { supportsEditorLanguage } from '../workspace/languageSupport'
import { sourceByteLength } from '../workspace/localDrafts'
import { clearSubmissionKey, loadOrCreateSubmissionKey } from '../workspace/submissionKeys'
import { resolveWorkspaceTransport, type WorkspaceTransport } from '../workspace/transport'
import { useDraftController } from '../workspace/useDraftController'
import './Admin.css'
import '../workspace/workspace.css'

const CodeEditor = lazy(() => import('../workspace/CodeEditor').then((module) => ({ default: module.CodeEditor })))
const ProblemStatement = lazy(() => import('../workspace/ProblemStatement').then((module) => ({ default: module.ProblemStatement })))

const ACTIVE_STATUSES = new Set<MatchView['status']>(['RUNNING', 'PAUSED', 'FINALIZING', 'FINISHED', 'TIED', 'SUPERSEDED'])
const PENDING_SUBMISSION_STATUSES = new Set(['QUEUED', 'RUNNING', 'RETRY_WAIT'])

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось загрузить рабочее пространство.'
}

function matchStatusName(status: MatchView['status']): string {
  const labels: Record<MatchView['status'], string> = {
    WAITING: 'Ожидает соперника', READY: 'Готов к старту', RUNNING: 'Идёт', PAUSED: 'Пауза',
    FINALIZING: 'Проверяем принятые решения', FINISHED: 'Завершён', TIED: 'Переигровка', SUPERSEDED: 'Новый запуск',
  }
  return labels[status]
}

function taskStatusName(status: MatchTaskState['status'] | undefined): string {
  if (status === 'SOLVED') return 'Решена'
  if (status === 'ATTEMPTED') return 'Есть попытки'
  return 'Не начата'
}

function submissionStatusName(status: SubmissionReceipt['status']): string {
  const labels: Record<SubmissionReceipt['status'], string> = {
    QUEUED: 'В очереди', RUNNING: 'Проверяется', RETRY_WAIT: 'Повтор проверки',
    FINISHED: 'Готово', INFRA_FAILED: 'Техническая ошибка', CANCELLED: 'Отменена',
  }
  return labels[status]
}

function verdictName(verdict: SubmissionVerdict | null): string {
  if (!verdict) return '—'
  const labels: Record<SubmissionVerdict, string> = { OK: 'OK', WA: 'WA', TL: 'TL', ML: 'ML', RE: 'RE', CE: 'CE' }
  return labels[verdict]
}

function formatClock(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`
}

function isTerminal(status: SubmissionReceipt['status']): boolean {
  return !PENDING_SUBMISSION_STATUSES.has(status)
}

export function ParticipantWorkspacePage() {
  const { matchId = '' } = useParams()
  const location = useLocation()
  const { user } = useAuth()
  const userId = user?.id ?? ''
  const [transport, setTransport] = useState<WorkspaceTransport | null>(null)
  const [match, setMatch] = useState<MatchView | null>(null)
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)
  const [reloadSequence, setReloadSequence] = useState(0)
  const [selectedProblemId, setSelectedProblemId] = useState('')
  const [problem, setProblem] = useState<MatchProblemDetails | null>(null)
  const [languages, setLanguages] = useState<MatchProblemLanguage[]>([])
  const [selectedLanguageId, setSelectedLanguageId] = useState('')
  const [problemLoading, setProblemLoading] = useState(false)
  const [problemError, setProblemError] = useState<string | null>(null)
  const [remainingMs, setRemainingMs] = useState(0)
  const [history, setHistory] = useState<SubmissionReceipt[]>([])
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [details, setDetails] = useState<Record<string, SubmissionDetail>>({})
  const [submissionBusy, setSubmissionBusy] = useState(false)
  const [submissionMessage, setSubmissionMessage] = useState<string | null>(null)
  const submissionKey = useRef<{ fingerprint: string; key: string; persisted: boolean } | null>(null)
  const remainingAtSync = useRef(0)
  const syncPerfTime = useRef(0)

  const isStarted = Boolean(match && ACTIVE_STATUSES.has(match.status))
  const ownPlayer = useMemo(() => match?.players.find((player) => player.userId === user?.id) ?? null, [match, user?.id])
  const ownTaskById = useMemo(() => new Map((ownPlayer?.tasks ?? []).map((task) => [task.problemId, task])), [ownPlayer])
  const selectedLanguage = useMemo(() => languages.find((language) => language.id === selectedLanguageId) ?? null, [languages, selectedLanguageId])
  const workspaceReady = Boolean(transport && match && ownPlayer && isStarted && selectedProblemId
    && problem?.problemId === selectedProblemId && selectedLanguage)
  const draft = useDraftController({
    userId: user?.id ?? '',
    runId: match?.runId ?? '',
    problemId: selectedProblemId,
    languageId: selectedLanguageId,
    template: selectedLanguage?.template ?? '',
    matchId,
    enabled: workspaceReady,
    transport: transport ?? EMPTY_TRANSPORT,
  })

  const reloadMatch = useCallback(async (source: WorkspaceTransport) => {
    setPageError(null)
    setLoading(true)
    try {
      const nextMatch = await source.match(matchId)
      setMatch(nextMatch)
      setSelectedProblemId((current) => nextMatch.problemVersions.some((problemVersion) => problemVersion.problemId === current)
        ? current
        : nextMatch.problemVersions[0]?.problemId ?? '')
      remainingAtSync.current = nextMatch.remainingMs
      syncPerfTime.current = performance.now()
      setRemainingMs(nextMatch.remainingMs)
    } catch (error) {
      setMatch(null)
      setPageError(messageFor(error))
    } finally {
      setLoading(false)
    }
  }, [matchId])

  useEffect(() => {
    let active = true
    const params = new URLSearchParams(location.search)
    void resolveWorkspaceTransport(params).then((resolved) => {
      if (!active) return
      setTransport(resolved)
    }).catch((error: unknown) => {
      if (active) {
        setPageError(messageFor(error))
        setLoading(false)
      }
    })
    return () => { active = false }
  }, [location.search])

  useEffect(() => {
    if (!transport || !matchId || !userId) return
    void reloadMatch(transport)
  }, [transport, matchId, userId, reloadSequence, reloadMatch])

  useEffect(() => {
    if (!transport || !match?.runId || !isStarted || !ownPlayer?.userId || !selectedProblemId) {
      setProblem(null)
      setLanguages([])
      setSelectedLanguageId('')
      setProblemLoading(false)
      setProblemError(null)
      return
    }
    let active = true
    setProblemLoading(true)
    setProblemError(null)
    setProblem(null)
    setLanguages([])
    void Promise.all([
      transport.problem(matchId, selectedProblemId),
      transport.languages(matchId, selectedProblemId),
    ]).then(([nextProblem, nextLanguages]) => {
      if (!active) return
      setProblem(nextProblem)
      setLanguages(nextLanguages)
      setSelectedLanguageId((current) => nextLanguages.some((language) => language.id === current)
        ? current
        : nextLanguages[0]?.id ?? '')
    }).catch((error: unknown) => {
      if (active) setProblemError(messageFor(error))
    }).finally(() => {
      if (active) setProblemLoading(false)
    })
    return () => { active = false }
  }, [transport, match?.runId, match?.status, matchId, isStarted, ownPlayer?.userId, selectedProblemId])

  const refreshHistory = useCallback(async () => {
    if (!transport || !match?.runId || !ownPlayer?.userId || !isStarted || !selectedProblemId || !transport.submissionsEnabled) return
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const result = await transport.submissions(matchId, selectedProblemId)
      setHistory(result.results)
    } catch (error) {
      setHistoryError(messageFor(error))
    } finally {
      setHistoryLoading(false)
    }
  }, [transport, match?.runId, ownPlayer?.userId, isStarted, selectedProblemId, matchId])

  useEffect(() => {
    setHistory([])
    setDetails({})
    setHistoryError(null)
    void refreshHistory()
  }, [refreshHistory])

  const pendingIds = useMemo(() => history.filter((entry) => PENDING_SUBMISSION_STATUSES.has(entry.status)).map((entry) => entry.submissionId), [history])
  const diagnosticIds = useMemo(() => history
    .filter((entry) => entry.verdict === 'CE' && !details[entry.submissionId])
    .map((entry) => entry.submissionId), [details, history])

  useEffect(() => {
    if (!transport?.submissionsEnabled || diagnosticIds.length === 0) return
    for (const submissionId of diagnosticIds) {
      void transport.submission(submissionId).then((detail) => {
        setDetails((current) => ({ ...current, [submissionId]: detail }))
      }).catch((error: unknown) => setHistoryError(messageFor(error)))
    }
  }, [transport, diagnosticIds])

  useEffect(() => {
    if (!transport || pendingIds.length === 0) return
    const timer = window.setInterval(() => {
      for (const submissionId of pendingIds) {
        void transport.submission(submissionId).then((next) => {
          setHistory((current) => current.map((entry) => entry.submissionId === submissionId ? next : entry))
          setDetails((current) => ({ ...current, [submissionId]: next }))
          if (isTerminal(next.status)) {
            void refreshHistory()
            setReloadSequence((value) => value + 1)
          }
        }).catch((error: unknown) => setHistoryError(messageFor(error)))
      }
    }, 1500)
    return () => window.clearInterval(timer)
  }, [transport, pendingIds, refreshHistory])

  useEffect(() => {
    if (match?.remainingMs === undefined) return
    remainingAtSync.current = match.remainingMs
    syncPerfTime.current = performance.now()
    setRemainingMs(match.remainingMs)
    if (match.status !== 'RUNNING') return
    const timer = window.setInterval(() => {
      const elapsed = performance.now() - syncPerfTime.current
      setRemainingMs(Math.max(0, remainingAtSync.current - elapsed))
    }, 250)
    return () => window.clearInterval(timer)
  }, [match?.status, match?.remainingMs])

  useEffect(() => {
    if (!transport || !match?.runId || match.status !== 'RUNNING') return
    const timer = window.setInterval(() => {
      void transport.match(matchId).then((next) => {
        setMatch(next)
        remainingAtSync.current = next.remainingMs
        syncPerfTime.current = performance.now()
        setRemainingMs(next.remainingMs)
      }).catch(() => undefined)
    }, 10000)
    return () => window.clearInterval(timer)
  }, [transport, match?.status, matchId, match?.runId])

  async function handleSubmit() {
    if (!transport || !match || !problem || !selectedLanguage || !transport.submissionsEnabled || match.status !== 'RUNNING') return
    if (remainingMs <= 0) {
      setSubmissionMessage('Время матча вышло. Новые посылки не отправляются.')
      return
    }
    if (sourceByteLength(draft.source) > 32 * 1024) {
      setSubmissionMessage('Исходный код превышает лимит 32 KiB и не отправлен.')
      return
    }
    setSubmissionBusy(true)
    setSubmissionMessage(null)
    const fingerprint = `${userId}:${match.runId}:${problem.problemId}:${selectedLanguage.id}:${draft.draft?.localRevision ?? 0}`
    const scope = { userId, runId: match.runId, problemId: problem.problemId, languageId: selectedLanguage.id }
    if (submissionKey.current?.fingerprint !== fingerprint) {
      submissionKey.current = { fingerprint, ...loadOrCreateSubmissionKey(scope, fingerprint) }
    }
    const idempotencyKey = submissionKey.current.key
    try {
      const receipt = await transport.submit(matchId, {
        runId: match.runId,
        problemId: problem.problemId,
        languageId: selectedLanguage.id,
        source: draft.source,
      }, idempotencyKey)
      const keyPersisted = clearSubmissionKey(scope, fingerprint)
      if (submissionKey.current?.fingerprint === fingerprint) submissionKey.current = null
      setSubmissionMessage(keyPersisted
        ? `Посылка принята: ${submissionStatusName(receipt.status)}.`
        : `Посылка принята: ${submissionStatusName(receipt.status)}. Ключ повтора не удалось удалить из локального хранилища.`)
      setHistory((current) => [receipt, ...current.filter((entry) => entry.submissionId !== receipt.submissionId)])
      await refreshHistory()
      if (PENDING_SUBMISSION_STATUSES.has(receipt.status)) {
        void transport.submission(receipt.submissionId).then((detail) => {
          setHistory((current) => current.map((entry) => entry.submissionId === receipt.submissionId ? detail : entry))
          setDetails((current) => ({ ...current, [receipt.submissionId]: detail }))
        }).catch(() => undefined)
      }
    } catch (error) {
      const persisted = submissionKey.current?.persisted ?? false
      setSubmissionMessage(`${messageFor(error)}${persisted ? '' : ' Повтор этого запроса в текущей вкладке использует тот же ключ; сохранить его для перезагрузки не удалось.'}`)
    } finally {
      setSubmissionBusy(false)
    }
  }

  const selectedTask = match?.problemVersions.find((entry) => entry.problemId === selectedProblemId)
  const opponent = match?.players.find((player) => player.userId !== user?.id)
  const submitAllowed = Boolean(transport?.submissionsEnabled && match?.status === 'RUNNING' && problem && selectedLanguage
    && remainingMs > 0 && draft.scopeReady && draft.status !== 'loading' && draft.status !== 'conflict')

  if (loading) return <div className="state-card" role="status">Загружаем матч…</div>
  if (pageError || !match) {
    return (
      <section className="page-section workspace-page">
        <div className="workspace-errors" role="alert">{pageError ?? 'Матч недоступен.'}<p>Рабочее пространство не переключается на demo-данные в production.</p></div>
        <button className="button button-small" type="button" onClick={() => setReloadSequence((value) => value + 1)}>Повторить</button>
      </section>
    )
  }
  if (!user || !ownPlayer) {
    return <section className="page-section workspace-page"><div className="workspace-errors" role="alert">Этот матч недоступен вашей учётной записи.</div></section>
  }

  return (
    <section className="page-section workspace-page">
      <div className="workspace-header">
        <div>
          <p className="eyebrow">Рабочее пространство · матч 1 × 1</p>
          <h1>{opponent ? `Матч с ${opponent.displayName}` : 'Рабочее пространство матча'}</h1>
        </div>
        <div className="workspace-meta" aria-label="Состояние матча">
          <span>{matchStatusName(match.status)}</span>
          <span>Раунд {match.runId.slice(-4)}</span>
          <span aria-label={`Осталось ${formatClock(remainingMs)}`}>⏱ {formatClock(remainingMs)}</span>
        </div>
      </div>

      {transport?.devScenario && (
        <div className="workspace-dev-banner" role="note">
          Изолированный dev-сценарий. Условия и версии черновика синтетические; отправка кода и вердикты отключены.
        </div>
      )}

      {!isStarted ? (
        <div className="workspace-main-panel workspace-locked">
          <h2>Задачи откроются после старта матча</h2>
          <p>До старта условие, шаблоны и редактор не запрашиваются. Это правило дополнительно проверяет сервер.</p>
        </div>
      ) : (
        <>
          <div className="workspace-layout">
            <nav className="workspace-task-list" aria-label="Задачи матча">
              <h2>Задачи · {ownPlayer.solvedCount} решено</h2>
              {match.problemVersions.map((task) => {
                const taskState = ownTaskById.get(task.problemId)
                return (
                  <button
                    className="workspace-task-button"
                    type="button"
                    key={task.problemId}
                    aria-current={task.problemId === selectedProblemId ? 'true' : undefined}
                    onClick={() => setSelectedProblemId(task.problemId)}
                  >
                    <span className="workspace-task-label">{task.label}</span>
                    <span className="workspace-task-name"><strong>Задача {task.label}</strong><small>{taskState?.attempts ?? 0} попыток</small></span>
                    <span className={`workspace-task-status${taskState?.status === 'SOLVED' ? ' solved' : ''}`}>{taskStatusName(taskState?.status)}</span>
                  </button>
                )
              })}
              {match.problemVersions.length === 0 && <p className="workspace-loading">Список задач матча недоступен.</p>}
            </nav>

            <div className="workspace-main-panel">
              {problemLoading && <div className="workspace-loading" role="status">Загружаем условие и список языков…</div>}
              {problemError && <div className="workspace-errors" role="alert">{problemError}<p>Проверьте, что problem API интегрирован в develop.</p></div>}
              {problem && (
                <>
                  <div className="workspace-main-toolbar">
                    <h2>{problem.label} · {problem.title}</h2>
                    <div className="workspace-toolbar-actions">
                      <label className="workspace-sr-only" htmlFor="workspace-language">Язык программирования</label>
                      <select id="workspace-language" value={selectedLanguageId} onChange={(event) => setSelectedLanguageId(event.target.value)} disabled={languages.length === 0}>
                        {languages.map((language) => <option value={language.id} key={language.id}>{language.name}</option>)}
                      </select>
                      <span className="workspace-draft-status">{draftStatusLabel(draft.status)}</span>
                    </div>
                  </div>
                  {draft.syncError && <div className="workspace-errors" role="status">{draft.syncError}</div>}
                  {draft.draft?.conflict && (
                    <DraftConflictPanel
                      localSource={draft.draft.conflict.localSource}
                      serverSource={draft.draft.conflict.serverDraft?.source ?? null}
                      onChoose={draft.chooseConflictVersion}
                    />
                  )}
                  <div className="workspace-body">
                    <div className="workspace-statement-panel">
                      <Suspense fallback={<div className="workspace-loading" role="status">Загружаем условие…</div>}>
                        <ProblemStatement problem={problem} />
                      </Suspense>
                    </div>
                    <div className="workspace-editor-wrap">
                      <div className="workspace-editor-heading">
                        <span>{selectedLanguage?.name ?? 'Язык не выбран'}</span>
                        <span>Ctrl/⌘ + Enter — отправить</span>
                      </div>
                      {!draft.scopeReady && <div className="workspace-loading" role="status">Восстанавливаем черновик для выбранной задачи и языка…</div>}
                      {selectedLanguage && draft.scopeReady && (
                        <Suspense fallback={<div className="workspace-loading" role="status">Загружаем редактор…</div>}>
                          <CodeEditor
                            value={draft.source}
                            languageId={selectedLanguage.id}
                            ariaLabel={`Исходный код, задача ${problem.label}, ${selectedLanguage.name}`}
                            onChange={draft.changeSource}
                            onSubmitHotkey={() => void handleSubmit()}
                          />
                        </Suspense>
                      )}
                      {selectedLanguage && !supportsEditorLanguage(selectedLanguage.id) && (
                        <p className="workspace-hint">Для этого server-owned compiler ID нет локального режима подсветки; шаблон и отправка остаются привязаны к ответу API.</p>
                      )}
                      <div className="workspace-hint">Черновик сохраняется локально для вашей учётной записи и синхронизируется по revision. Таймер и запрет посылки определяет сервер.</div>
                    </div>
                  </div>
                  <div className="workspace-submit-row">
                    <p>{match.status === 'PAUSED' ? 'Матч на паузе: новые посылки недоступны.' : match.status !== 'RUNNING' ? 'Матч не принимает новые посылки.' : remainingMs <= 0 ? 'Время матча вышло: новые посылки не принимаются.' : !transport?.submissionsEnabled ? 'Submission API не подключён в этом сценарии.' : 'Посылка попадёт в серверную очередь проверки.'}</p>
                    <button className="button button-small" type="button" onClick={() => void handleSubmit()} disabled={!submitAllowed || submissionBusy || draft.status === 'conflict'}>
                      {submissionBusy ? 'Отправляем…' : 'Отправить решение'}
                    </button>
                  </div>
                  {submissionMessage && <div className="workspace-errors" role="status">{submissionMessage}</div>}
                </>
              )}
            </div>
          </div>

          <div className="workspace-panels">
            <section className="workspace-panel" aria-labelledby="workspace-attempts-heading">
              <h2 id="workspace-attempts-heading">История попыток · {problem?.label ?? selectedTask?.label ?? '—'}</h2>
              <div className="workspace-panel-body">
                {transport && !transport.submissionsEnabled ? <p className="workspace-loading">История API проверок не подключена; синтетические попытки не создаются.</p> : null}
                {historyLoading && <p className="workspace-loading" role="status">Обновляем историю…</p>}
                {historyError && <p className="workspace-errors" role="alert">{historyError}</p>}
                {!historyLoading && !historyError && transport?.submissionsEnabled && history.length === 0 && <p className="workspace-loading">Попыток пока нет.</p>}
                {history.length > 0 && (
                  <ul className="workspace-history-list">
                    {history.map((entry) => {
                      const detail = details[entry.submissionId]
                      return (
                        <li className="workspace-history-item" key={entry.submissionId}>
                          <span className={`submission-state${entry.status === 'INFRA_FAILED' || entry.status === 'CANCELLED' ? ' failed' : isTerminal(entry.status) ? ' terminal' : ''}`}>{submissionStatusName(entry.status)}</span>
                          <span>{new Date(entry.receivedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                          <strong>{verdictName(entry.verdict)}</strong>
                          {detail?.diagnostics && entry.verdict === 'CE' && <pre className="workspace-diagnostics">{detail.diagnostics}</pre>}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            </section>
            <section className="workspace-panel" aria-labelledby="workspace-help-heading">
              <h2 id="workspace-help-heading">Рабочее место</h2>
              <div className="workspace-panel-body">
                <p className="workspace-loading">{ownPlayer.displayName} · {ownPlayer.solvedCount} задач решено · штраф {Math.floor(ownPlayer.penaltyMs / 1000)} с</p>
                <Link className="text-link" to="/dashboard">Назад в кабинет <span aria-hidden="true">↗</span></Link>
              </div>
            </section>
          </div>
        </>
      )}
    </section>
  )
}

function draftStatusLabel(status: ReturnType<typeof useDraftController>['status']): string {
  const labels: Record<ReturnType<typeof useDraftController>['status'], string> = {
    locked: 'Условие закрыто', loading: 'Загружаем черновик…', local: 'Локально сохранено',
    saving: 'Синхронизируем…', saved: 'Сервер и локальная копия синхронизированы',
    conflict: 'Нужно разрешить конфликт', unavailable: 'Нет связи с draft API', 'storage-error': 'Ошибка локального хранилища',
  }
  return labels[status]
}

function DraftConflictPanel({
  localSource,
  serverSource,
  onChoose,
}: {
  localSource: string
  serverSource: string | null
  onChoose(choice: 'local' | 'server'): void
}) {
  return (
    <section className="workspace-conflict" role="alert">
      <h3>Найдены две версии черновика</h3>
      <p>Обе редакции сохранены. Сравните их и явно выберите, какую оставить; до выбора автосохранение на сервер приостановлено.</p>
      <div className="workspace-conflict-grid">
        <label>Локальная версия<textarea value={localSource} readOnly /></label>
        <label>Серверная версия<textarea value={serverSource ?? 'На сервере черновик отсутствует.'} readOnly /></label>
      </div>
      <div className="workspace-conflict-actions">
        <button type="button" className="button button-small" onClick={() => onChoose('local')}>Оставить локальную и синхронизировать</button>
        <button type="button" className="button button-small button-outline" onClick={() => onChoose('server')}>Оставить серверную</button>
      </div>
    </section>
  )
}

const EMPTY_TRANSPORT: WorkspaceTransport = {
  devScenario: false,
  submissionsEnabled: false,
  match: async () => { throw new ApiError('API недоступен.', 503, 'integration_unavailable') },
  problem: async () => { throw new ApiError('API недоступен.', 503, 'integration_unavailable') },
  languages: async () => { throw new ApiError('API недоступен.', 503, 'integration_unavailable') },
  draft: async () => null,
  saveDraft: async () => { throw new ApiError('API недоступен.', 503, 'integration_unavailable') },
  submit: async () => { throw new ApiError('API недоступен.', 503, 'integration_unavailable') },
  submissions: async () => ({ count: 0, next: null, previous: null, results: [] }),
  submission: async () => { throw new ApiError('API недоступен.', 503, 'integration_unavailable') },
}
