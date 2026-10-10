import { createContext } from 'react'
import type { LoginInput, RegisterInput, User } from '../api/client'

export type AuthStatus = 'loading' | 'anonymous' | 'authenticated' | 'error'

interface AuthContextValue {
  status: AuthStatus
  user: User | null
  error: string | null
  retry: () => Promise<void>
  signIn: (input: LoginInput) => Promise<void>
  signUp: (input: RegisterInput) => Promise<User>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
