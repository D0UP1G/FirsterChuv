import type { Tournament } from '../api/client'

export const statusLabel: Record<Tournament['status'], string> = {
  draft: 'Черновик',
  scheduled: 'Запланирован',
  running: 'Идёт',
  completed: 'Завершён',
  archived: 'Архивирован',
}
