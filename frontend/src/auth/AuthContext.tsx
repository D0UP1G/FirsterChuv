import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ApiError, api, type LoginInput, type RegisterInput, type User } from '../api/client'
import { AuthContext } from './context'
import type { AuthStatus } from './context'

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось выполнить запрос. Попробуйте ещё раз.'
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<User | null>(null)
  const [error, setError] = useState<string | null>(null)
  const operationSequence = useRef(0)

  const retry = useCallback(async (showLoading = true) => {
    const operationId = ++operationSequence.current
    if (showLoading) {
      setStatus('loading')
      setError(null)
    }
    const [, userResult] = await Promise.allSettled([api.csrf(), api.me()])
    if (operationId !== operationSequence.current) return
    if (userResult.status === 'fulfilled') {
      setUser(userResult.value)
      setStatus('authenticated')
      return
    }
    setUser(null)
    const reason = userResult.reason
    if (reason instanceof ApiError && reason.status === 401) {
      setStatus('anonymous')
      return
    }
    setError(messageFor(reason))
    setStatus('error')
  }, [])

  useEffect(() => {
    const operationId = ++operationSequence.current
    let active = true
    void Promise.allSettled([api.csrf(), api.me()]).then(([, userResult]) => {
      if (!active || operationId !== operationSequence.current) return
      if (userResult.status === 'fulfilled') {
        setUser(userResult.value)
        setStatus('authenticated')
      } else if (userResult.reason instanceof ApiError && userResult.reason.status === 401) {
        setUser(null)
        setStatus('anonymous')
      } else {
        setUser(null)
        setError(messageFor(userResult.reason))
        setStatus('error')
      }
    })
    return () => {
      active = false
      operationSequence.current += 1
    }
  }, [])

  const signIn = useCallback(async (input: LoginInput) => {
    const operationId = ++operationSequence.current
    try {
      const nextUser = await api.login(input)
      if (operationId !== operationSequence.current) return
      setUser(nextUser)
      setError(null)
      setStatus('authenticated')
    } catch (reason) {
      if (operationId === operationSequence.current) {
        setUser(null)
        setStatus('anonymous')
      }
      throw reason
    }
  }, [])

  const signUp = useCallback((input: RegisterInput) => api.register(input), [])

  const signOut = useCallback(async () => {
    const operationId = ++operationSequence.current
    await api.logout()
    if (operationId !== operationSequence.current) return
    setUser(null)
    setError(null)
    setStatus('anonymous')
  }, [])

  const value = useMemo(() => ({ status, user, error, retry, signIn, signUp, signOut }), [status, user, error, retry, signIn, signUp, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
