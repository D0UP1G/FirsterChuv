import { ApiError, api } from '../api/client'
import type { PublicBracketSnapshot, PublicMatchEvent, PublicMatchSnapshot, PublicResyncNotice, SpectatorConnection } from './types'

export interface PublicStreamHandlers {
  onOpen: () => void
  onEvent: (event: PublicMatchEvent) => void
  onResync: (notice: PublicResyncNotice) => void
  onError: () => void
}

export interface SpectatorTransport {
  readonly mode: 'http' | 'development-scenario'
  bracket(tournamentId: string, matchId?: string): Promise<PublicBracketSnapshot>
  snapshot(matchId: string): Promise<PublicMatchSnapshot>
  subscribe(matchId: string, afterEventId: number, handlers: PublicStreamHandlers): () => void
}

const unavailable = (): ApiError => new ApiError(
  'Публичный endpoint ещё не подключён. Зрительская карта недоступна на этой версии сервера.',
  503,
  'public_access_unavailable',
)

// Interim until the public SSE endpoint is integrated: re-read the anonymous snapshot and ask the page to resync on change.
export const PUBLIC_POLL_INTERVAL_MS = 4000

async function readSnapshot(matchId: string): Promise<PublicMatchSnapshot> {
  return await api.publicMatchSnapshot(matchId) as PublicMatchSnapshot
}

const httpTransport: SpectatorTransport = {
  mode: 'http',
  // There is no public bracket endpoint yet. A direct match link is shown as a one-match map built only from
  // the allowlisted public snapshot; without a match id the page reports that the public bracket is unavailable.
  async bracket(tournamentId: string, matchId?: string) {
    if (!matchId) throw unavailable()
    const snapshot = await readSnapshot(matchId)
    const winner = snapshot.players.find((player) => player.userId === snapshot.winnerUserId)
    return {
      tournamentId,
      title: 'Публичный матч',
      bracketSize: 2,
      matches: [{
        id: snapshot.matchId,
        key: 'Матч',
        roundIndex: 0,
        position: 0,
        status: snapshot.status,
        slots: [{ displayName: snapshot.players[0].displayName }, { displayName: snapshot.players[1].displayName }],
        winnerName: winner?.displayName ?? null,
      }],
    }
  },
  snapshot: readSnapshot,
  subscribe(matchId: string, afterEventId: number, handlers: PublicStreamHandlers) {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | null = null
    let opened = false
    let lastEventId = afterEventId
    const tick = async () => {
      try {
        const next = await readSnapshot(matchId)
        if (stopped) return
        if (!opened) {
          opened = true
          handlers.onOpen()
        }
        if (typeof next.lastEventId === 'number' && next.lastEventId !== lastEventId) {
          lastEventId = next.lastEventId
          handlers.onResync({ type: 'stream.resync_required' })
        }
        timer = setTimeout(() => void tick(), PUBLIC_POLL_INTERVAL_MS)
      } catch {
        if (stopped) return
        stopped = true
        handlers.onError()
      }
    }
    void tick()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  },
}

export async function resolveSpectatorTransport(search: string): Promise<SpectatorTransport> {
  if (!import.meta.env.DEV) return httpTransport
  const params = new URLSearchParams(search)
  if (params.get('scenario') === 'public-map') {
    const { createDevSpectatorTransport } = await import('./devTransport')
    return createDevSpectatorTransport({
      disconnectOnce: params.get('disconnect') === '1',
      resyncOnce: params.get('resync') === '1',
    })
  }
  return httpTransport
}

export function spectatorConnectionLabel(connection: SpectatorConnection): string {
  const labels: Record<SpectatorConnection, string> = {
    loading: 'Загружаем карту',
    connecting: 'Подключаем трансляцию',
    live: 'Эфир обновляется',
    reconnecting: 'Восстанавливаем соединение',
    stale: 'Данные могут отставать',
    resyncing: 'Сверяем состояние матча',
    unavailable: 'Трансляция недоступна',
  }
  return labels[connection]
}
