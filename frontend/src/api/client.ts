export type UserRole = 'participant' | 'admin'

export interface User {
  id: string
  displayName: string
  role: UserRole
}

export interface RegisterInput {
  email: string
  password: string
  displayName: string
}

export interface LoginInput {
  email: string
  password: string
}

interface ApiErrorBody {
  error?: {
    code?: string
    message?: string
    fields?: unknown
  }
  requestId?: string | null
  request_id?: string | null
}

export class ApiError extends Error {
  readonly status: number | null
  readonly code: string | null
  readonly fields: unknown
  readonly requestId: string | null

  constructor(
    message: string,
    status: number | null,
    code: string | null = null,
    fields: unknown = null,
    requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fields = fields
    this.requestId = requestId
  }
}

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '')
let csrfToken: string | null = null
let csrfPromise: Promise<string> | null = null

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

async function readBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('json')) return undefined
  try {
    return await response.json() as unknown
  } catch {
    return undefined
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers,
      credentials: 'include',
      cache: 'no-store',
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Не удалось связаться с сервером. Проверьте соединение и попробуйте ещё раз.', null, 'network_error')
  }

  const body = await readBody(response)
  if (!response.ok) {
    const envelope = isRecord(body) && isRecord(body.error) ? body as ApiErrorBody : undefined
    const detail = envelope?.error
    throw new ApiError(
      typeof detail?.message === 'string' ? detail.message : 'Запрос не выполнен. Попробуйте ещё раз.',
      response.status,
      typeof detail?.code === 'string' ? detail.code : 'request_error',
      detail?.fields ?? null,
      typeof envelope?.requestId === 'string'
        ? envelope.requestId
        : typeof envelope?.request_id === 'string'
          ? envelope.request_id
          : null,
    )
  }
  return body as T
}

async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken
  if (csrfPromise) return csrfPromise

  const pending = request<{ csrfToken?: unknown }>('/auth/csrf').then((response) => {
    if (typeof response.csrfToken !== 'string' || response.csrfToken.length === 0) {
      throw new ApiError('Сервер не выдал токен защиты запроса.', 502, 'invalid_csrf_response')
    }
    csrfToken = response.csrfToken
    return csrfToken
  }).finally(() => {
    if (csrfPromise === pending) csrfPromise = null
  })
  csrfPromise = pending
  return pending
}

async function mutate<T>(path: string, payload?: unknown): Promise<T> {
  const token = await ensureCsrfToken()
  return request<T>(path, {
    method: 'POST',
    headers: { 'X-CSRFToken': token },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  })
}

export const api = {
  async csrf(): Promise<void> {
    await ensureCsrfToken()
  },

  me(): Promise<User> {
    return request<User>('/me')
  },

  register(input: RegisterInput): Promise<User> {
    return mutate<User>('/auth/register', input)
  },

  async login(input: LoginInput): Promise<User> {
    const result = await mutate<User & { csrfToken?: unknown }>('/auth/login', input)
    if (typeof result.csrfToken !== 'string' || result.csrfToken.length === 0) {
      csrfToken = null
      throw new ApiError('Вход выполнен, но сервер не обновил токен защиты запроса.', 502, 'invalid_login_response')
    }
    csrfToken = result.csrfToken
    return { id: result.id, displayName: result.displayName, role: result.role }
  },

  async logout(): Promise<void> {
    await mutate<void>('/auth/logout')
    csrfToken = null
  },
}

export function resetCsrfToken(): void {
  csrfToken = null
  csrfPromise = null
}
