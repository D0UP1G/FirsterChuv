import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, type User } from '../api/client'
import { draftStorageKey } from '../workspace/localDrafts'
import { AuthProvider } from './AuthContext'
import { useAuth } from './useAuth'

const participant: User = { id: 'user-1', displayName: 'Игрок', role: 'participant' }

function AuthStateProbe() {
  const { status, user, signOut } = useAuth()
  return (
    <div>
      <span data-testid="status">{status}</span>
      {user && <span data-testid="private-user">{user.displayName}</span>}
      <button type="button" onClick={() => void signOut().catch(() => undefined)}>Выйти из тестовой сессии</button>
    </div>
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.spyOn(api, 'csrf').mockResolvedValue()
    vi.spyOn(api, 'me').mockResolvedValue(participant)
    vi.spyOn(api, 'logout').mockResolvedValue()
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('clears the in-memory user when logout succeeds', async () => {
    render(<AuthProvider><AuthStateProbe /></AuthProvider>)

    expect(await screen.findByTestId('private-user')).toHaveTextContent('Игрок')
    fireEvent.click(screen.getByRole('button', { name: 'Выйти из тестовой сессии' }))

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'))
    expect(screen.queryByTestId('private-user')).not.toBeInTheDocument()
    expect(api.logout).toHaveBeenCalledOnce()
  })

  it('removes the signed-out user local drafts but keeps other users drafts', async () => {
    const mine = draftStorageKey({ userId: participant.id, runId: 'run-1', problemId: 'p-1', languageId: 'python' })
    const theirs = draftStorageKey({ userId: 'user-2', runId: 'run-1', problemId: 'p-1', languageId: 'python' })
    window.localStorage.setItem(mine, 'private source')
    window.localStorage.setItem(theirs, 'other source')
    render(<AuthProvider><AuthStateProbe /></AuthProvider>)

    await screen.findByTestId('private-user')
    fireEvent.click(screen.getByRole('button', { name: 'Выйти из тестовой сессии' }))

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'))
    expect(window.localStorage.getItem(mine)).toBeNull()
    expect(window.localStorage.getItem(theirs)).toBe('other source')
  })

  it('keeps local drafts when the server logout fails', async () => {
    vi.spyOn(api, 'logout').mockRejectedValue(new Error('offline'))
    const mine = draftStorageKey({ userId: participant.id, runId: 'run-1', problemId: 'p-1', languageId: 'python' })
    window.localStorage.setItem(mine, 'private source')
    render(<AuthProvider><AuthStateProbe /></AuthProvider>)

    await screen.findByTestId('private-user')
    fireEvent.click(screen.getByRole('button', { name: 'Выйти из тестовой сессии' }))

    await waitFor(() => expect(api.logout).toHaveBeenCalled())
    expect(window.localStorage.getItem(mine)).toBe('private source')
  })
})
