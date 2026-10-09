import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, type User } from '../api/client'
import { AuthProvider } from './AuthContext'
import { useAuth } from './useAuth'

const participant: User = { id: 'user-1', displayName: 'Игрок', role: 'participant' }

function AuthStateProbe() {
  const { status, user, signOut } = useAuth()
  return (
    <div>
      <span data-testid="status">{status}</span>
      {user && <span data-testid="private-user">{user.displayName}</span>}
      <button type="button" onClick={() => void signOut()}>Выйти из тестовой сессии</button>
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
})
