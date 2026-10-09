import {
  api,
  type Bracket,
  type DirectoryUser,
  type FirstRoundPairing,
  type MatchActionInput,
  type MatchConfigInput,
  type MatchView,
  type ProblemCatalogEntry,
  type RosterEntry,
  type Tournament,
} from '../api/client'

export interface MatchAdminTransport {
  readonly mode: 'http' | 'development-scenario'
  tournament(id: string): Promise<Tournament>
  roster(id: string): Promise<RosterEntry[]>
  directory(query: string): Promise<DirectoryUser[]>
  problems(): Promise<ProblemCatalogEntry[]>
  bracket(id: string): Promise<Bracket>
  generateBracket(id: string, key: string): Promise<Bracket>
  savePairings(id: string, pairings: FirstRoundPairing[], reason: string, key: string): Promise<Bracket>
  match(id: string): Promise<MatchView>
  updateConfig(id: string, input: MatchConfigInput, key: string): Promise<MatchView>
  action(id: string, input: MatchActionInput, key: string): Promise<MatchView>
  simulateReady?(id: string, userId: string): Promise<MatchView>
}

const httpTransport: MatchAdminTransport = {
  mode: 'http',
  tournament: (id) => api.tournament(id),
  roster: async (id) => (await api.roster(id)).results,
  directory: async (query) => (await api.directory(query)).results,
  problems: async () => (await api.readyProblems()).results,
  bracket: (id) => api.bracket(id),
  generateBracket: (id, key) => api.generateBracket(id, key),
  savePairings: (id, pairings, reason, key) => api.saveFirstRoundPairings(id, pairings, reason, key),
  match: (id) => api.match(id),
  updateConfig: (id, input, key) => api.updateMatchConfig(id, input, key),
  action: (id, input, key) => api.matchAction(id, input, key),
}

export async function resolveMatchAdminTransport(search: string): Promise<MatchAdminTransport> {
  if (!import.meta.env.DEV) return httpTransport
  const params = new URLSearchParams(search)
  if (params.get('scenario') === 'match-ui') {
    const { createDevMatchTransport } = await import('./devTransport')
    return createDevMatchTransport(Number(params.get('participants')))
  }
  return httpTransport
}
