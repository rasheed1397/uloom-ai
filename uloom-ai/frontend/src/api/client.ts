// NFR-004: https by default - the api container serves TLS on 8000 (see
// its docker-entrypoint.sh). The browser will show a one-time trust prompt
// for the self-signed cert; visit https://localhost:8000/health directly
// and accept it once before using the app.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'https://localhost:8000'

const TOKEN_STORAGE_KEY = 'uloom_access_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  }
}

export class ApiError extends Error {
  status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  // Sent as multipart/form-data instead of JSON (document upload).
  formData?: FormData
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData
    // Deliberately no Content-Type here: the browser sets multipart/form-data
    // with the correct boundary itself.
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body,
    // Every response here reflects live, frequently-changing server state
    // (document status, conversation history, admin settings); none of it
    // should ever be served from the browser's HTTP cache.
    cache: 'no-store',
  })

  if (response.status === 204) {
    return undefined as T
  }

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : response.statusText
    throw new ApiError(response.status, detail)
  }

  return payload as T
}
