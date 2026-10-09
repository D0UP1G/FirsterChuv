import { ApiError, type DraftSnapshot, type MatchProblemDetails, type MatchProblemLanguage, type MatchView, type Page, type SubmissionDetail, type SubmissionInput, type SubmissionReceipt } from '../api/client'
import type { WorkspaceTransport } from './transport'

const taskIds = [
  '00000000-0000-0000-0000-000000000040',
  '00000000-0000-0000-0000-000000000041',
  '00000000-0000-0000-0000-000000000042',
]

const languages: MatchProblemLanguage[] = [
  { id: 'cpp20', name: 'C++20', template: '#include <iostream>\n\nint main() {\n    return 0;\n}\n' },
  { id: 'python3', name: 'Python 3', template: 'def main():\n    pass\n\nif __name__ == "__main__":\n    main()\n' },
]

const problems: MatchProblemDetails[] = [
  {
    problemId: taskIds[0], version: 'synthetic-v1', label: 'A', title: 'Сумма двух чисел · пример',
    conditionAvailable: true,
    statementMarkdown: 'Найдите значение $a + b$.\n\n| Ввод | Вывод |\n|---|---|\n| два целых числа | их сумма |\n\nОграничение по времени и памяти приведено ниже.',
    assetIds: [], examples: [{ input: '2 3\n', output: '5\n' }], timeLimitMs: 2000, memoryLimitBytes: 536870912,
  },
  {
    problemId: taskIds[1], version: 'synthetic-v1', label: 'B', title: 'Последовательность · пример',
    conditionAvailable: true,
    statementMarkdown: 'Посчитайте сумму первых $n$ натуральных чисел.\n\n$$1 + 2 + \\cdots + n = \\frac{n(n+1)}{2}$$',
    assetIds: [], examples: [{ input: '4\n', output: '10\n' }], timeLimitMs: 2000, memoryLimitBytes: 536870912,
  },
  {
    problemId: taskIds[2], version: 'synthetic-v1', label: 'C', title: 'Разность · пример',
    conditionAvailable: true,
    statementMarkdown: 'Для целых $a$ и $b$ выведите $a - b$.\n\nЗадачи можно решать в любом порядке.',
    assetIds: [], examples: [{ input: '9 4\n', output: '5\n' }], timeLimitMs: 2000, memoryLimitBytes: 536870912,
  },
]

function makeMatch(status: MatchView['status'], startedAt: number): MatchView {
  const now = new Date().toISOString()
  const runningDurationMs = status === 'RUNNING' ? Math.max(0, Date.now() - startedAt) : 0
  const tasksForPlayer = () => taskIds.map((problemId, index) => ({
    problemId,
    label: String.fromCharCode(65 + index),
    status: 'NOT_STARTED' as const,
    attempts: 0,
    lastVerdict: null,
  }))
  return {
    matchId: '00000000-0000-0000-0000-000000000020',
    runId: '00000000-0000-0000-0000-000000000030',
    status,
    serverNow: now,
    elapsedMs: status === 'RUNNING' ? 180000 + runningDurationMs : 0,
    remainingMs: status === 'RUNNING' ? Math.max(0, 1020000 - runningDurationMs) : 1200000,
    allowedDurationMs: 1200000,
    leaderUserId: null,
    winnerUserId: null,
    lastEventId: 0,
    scoringRule: {
      order: ['solved_desc', 'penalty_asc', 'last_accepted_asc'],
      wrongAttemptPenaltySec: 60,
      penalizedVerdicts: ['WA', 'TL', 'ML', 'RE'],
      finalTiePolicy: 'rematch',
    },
    players: [
      { userId: '00000000-0000-0000-0000-000000000001', displayName: 'Вы · demo', solvedCount: 0, penaltyMs: 0, lastAcceptedElapsedMs: null, tasks: tasksForPlayer() },
      { userId: '00000000-0000-0000-0000-000000000004', displayName: 'Соперник · demo', solvedCount: 0, penaltyMs: 0, lastAcceptedElapsedMs: null, tasks: tasksForPlayer() },
    ],
    tournamentId: '00000000-0000-0000-0000-000000000010',
    startMode: 'manual',
    readyUserIds: [],
    problemVersions: problems.map(({ problemId, label, version, conditionAvailable }) => ({ problemId, label, version, conditionAvailable })),
  }
}

export function createDevWorkspaceTransport(search: URLSearchParams): WorkspaceTransport {
  const status: MatchView['status'] = search.get('status') === 'READY' ? 'READY' : 'RUNNING'
  const startedAt = Date.now()
  const storedDrafts = new Map<string, DraftSnapshot>()
  const scopeKey = (problemId: string, runId: string, languageId: string) => `${runId}:${problemId}:${languageId}`
  if (search.get('draftConflict') === '1') {
    const problemId = taskIds[0]
    storedDrafts.set(scopeKey(problemId, '00000000-0000-0000-0000-000000000030', 'cpp20'), {
      runId: '00000000-0000-0000-0000-000000000030', problemId, languageId: 'cpp20',
      source: '// Синтетическая серверная версия черновика\n', revision: 3, updatedAt: new Date().toISOString(),
    })
  }
  return {
    devScenario: true,
    submissionsEnabled: false,
    async match() { return makeMatch(status, startedAt) },
    async problem(_matchId, problemId) {
      const problem = problems.find((candidate) => candidate.problemId === problemId)
      if (!problem) throw new ApiError('Задача не найдена в dev-сценарии.', 404, 'not_found')
      return structuredClone(problem)
    },
    async languages() { return structuredClone(languages) },
    async draft(_matchId, problemId, runId, languageId) {
      return storedDrafts.get(scopeKey(problemId, runId, languageId)) ?? null
    },
    async saveDraft(_matchId, problemId, languageId, input) {
      const key = scopeKey(problemId, input.runId, languageId)
      const current = storedDrafts.get(key)
      if ((current?.revision ?? 0) !== input.expectedRevision) {
        throw new ApiError('Dev-сценарий: версия черновика изменилась.', 409, 'revision_conflict', { current_draft: current ?? null })
      }
      const next: DraftSnapshot = {
        runId: input.runId, problemId, languageId, source: input.source,
        revision: input.expectedRevision + 1, updatedAt: new Date().toISOString(),
      }
      storedDrafts.set(key, next)
      return next
    },
    async submit(_matchId: string, _input: SubmissionInput, _idempotencyKey: string): Promise<SubmissionReceipt> {
      throw new ApiError('Проверка кода не подключена; dev-сценарий не создаёт вердикты.', 503, 'integration_unavailable')
    },
    async submissions(): Promise<Page<SubmissionReceipt>> {
      throw new ApiError('История попыток появится после подключения API посылок.', 503, 'integration_unavailable')
    },
    async submission(): Promise<SubmissionDetail> {
      throw new ApiError('Статус посылки появится после подключения API проверок.', 503, 'integration_unavailable')
    },
  }
}
