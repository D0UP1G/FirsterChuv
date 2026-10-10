import { api, publicMatchEventsUrl } from '../api/client'
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

// Polling stays only as a fallback for browsers without EventSource: re-read the anonymous snapshot and ask
// the page to resync when the event cursor moves.
export const PUBLIC_POLL_INTERVAL_MS = 4000

async function readSnapshot(matchId: string): Promise<PublicMatchSnapshot> {
  return await api.publicMatchSnapshot(matchId) as PublicMatchSnapshot
}

function subscribeByPolling(matchId: string, afterEventId: number, handlers: PublicStreamHandlers): () => void {
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
}

function subscribeBySse(matchId: string, afterEventId: number, handlers: PublicStreamHandlers): () => void {
  const source = new EventSource(publicMatchEventsUrl(matchId, afterEventId))
  const resync = () => handlers.onResync({ type: 'stream.resync_required' })
  source.onopen = () => handlers.onOpen()
  source.addEventListener('score.changed', (event) => {
    try {
      handlers.onEvent(JSON.parse((event as MessageEvent<string>).data) as PublicMatchEvent)
    } catch {
      // A frame that cannot be parsed is never applied; re-read the snapshot instead.
      resync()
    }
  })
  source.addEventListener('stream.resync_required', resync)
  // The server ends each connection after a bounded time and the browser reconnects with Last-Event-ID,
  // so a transient error while CONNECTING is normal; only a closed stream (4xx/5xx) is a failure.
  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) handlers.onError()
  }
  return () => source.close()
}

const httpTransport: SpectatorTransport = {
  mode: 'http',
  async bracket(tournamentId: string) {
    return await api.publicBracket(tournamentId) as PublicBracketSnapshot
  },
  snapshot: readSnapshot,
  subscribe(matchId: string, afterEventId: number, handlers: PublicStreamHandlers) {
    return typeof EventSource === 'undefined'
      ? subscribeByPolling(matchId, afterEventId, handlers)
      : subscribeBySse(matchId, afterEventId, handlers)
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
