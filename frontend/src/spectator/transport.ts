import { ApiError } from '../api/client'
import type { PublicBracketSnapshot, PublicMatchEvent, PublicMatchSnapshot, PublicResyncNotice, SpectatorConnection } from './types'

export interface PublicStreamHandlers {
  onOpen: () => void
  onEvent: (event: PublicMatchEvent) => void
  onResync: (notice: PublicResyncNotice) => void
  onError: () => void
}

export interface SpectatorTransport {
  readonly mode: 'http' | 'development-scenario'
  bracket(tournamentId: string): Promise<PublicBracketSnapshot>
  snapshot(matchId: string): Promise<PublicMatchSnapshot>
  subscribe(matchId: string, afterEventId: number, handlers: PublicStreamHandlers): () => void
}

const unavailable = (): ApiError => new ApiError(
  'Публичный endpoint ещё не подключён. Зрительская карта недоступна на этой версии сервера.',
  503,
  'public_access_unavailable',
)

const httpTransport: SpectatorTransport = {
  mode: 'http',
  async bracket() { throw unavailable() },
  async snapshot() { throw unavailable() },
  subscribe(_matchId: string, _afterEventId: number, handlers: PublicStreamHandlers) {
    handlers.onError()
    return () => undefined
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
