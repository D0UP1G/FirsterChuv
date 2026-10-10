import { ApiError, api, type DraftSnapshot, type DraftWriteInput, type MatchProblemDetails, type MatchProblemLanguage, type MatchView, type Page, type SubmissionDetail, type SubmissionInput, type SubmissionReceipt } from '../api/client'

export interface WorkspaceTransport {
  readonly devScenario: boolean
  readonly submissionsEnabled: boolean
  match(matchId: string): Promise<MatchView>
  problem(matchId: string, problemId: string): Promise<MatchProblemDetails>
  languages(matchId: string, problemId: string): Promise<MatchProblemLanguage[]>
  draft(matchId: string, problemId: string, runId: string, languageId: string): Promise<DraftSnapshot | null>
  saveDraft(matchId: string, problemId: string, languageId: string, input: DraftWriteInput): Promise<DraftSnapshot>
  submit(matchId: string, input: SubmissionInput, idempotencyKey: string): Promise<SubmissionReceipt>
  submissions(matchId: string, problemId: string): Promise<Page<SubmissionReceipt>>
  submission(submissionId: string): Promise<SubmissionDetail>
}

const httpTransport: WorkspaceTransport = {
  devScenario: false,
  submissionsEnabled: true,
  match: (matchId) => api.match(matchId),
  problem: (matchId, problemId) => api.matchProblem(matchId, problemId),
  languages: (matchId, problemId) => api.matchProblemLanguages(matchId, problemId),
  async draft(matchId, problemId, runId, languageId) {
    try {
      return await api.draft(matchId, problemId, runId, languageId)
    } catch (error) {
      // The draft contract defines 404 as "no saved draft yet"; no local data is removed.
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    }
  },
  saveDraft: (matchId, problemId, languageId, input) => api.saveDraft(matchId, problemId, languageId, input),
  submit: (matchId, input, idempotencyKey) => api.submitSolution(matchId, input, idempotencyKey),
  submissions: (matchId, problemId) => api.submissions(matchId, problemId),
  submission: (submissionId) => api.submission(submissionId),
}

export async function resolveWorkspaceTransport(search: URLSearchParams): Promise<WorkspaceTransport> {
  if (import.meta.env.DEV && search.get('scenario') === 'workspace-ui') {
    const { createDevWorkspaceTransport } = await import('./devTransport')
    return createDevWorkspaceTransport(search)
  }
  return httpTransport
}
