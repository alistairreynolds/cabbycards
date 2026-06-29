const TOKEN_KEY = "cabbycards.token"

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token === null) {
    localStorage.removeItem(TOKEN_KEY)
    return
  }
  localStorage.setItem(TOKEN_KEY, token)
}

/**
 * Thin wrapper over fetch: prefixes /api (proxied to the backend in dev),
 * attaches the Bearer token, sends/expects JSON, and throws ApiError on non-2xx.
 *
 * See: api.spec.ts
 */
export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set("Accept", "application/json")
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json")
  }
  const token = getToken()
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const response = await fetch(`/api${path}`, { ...options, headers })

  if (!response.ok) {
    throw new ApiError(response.status, await _errorDetail(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

async function _errorDetail(response: Response): Promise<string> {
  // FastAPI puts the message in `detail`; fall back to the status text.
  try {
    const body = await response.json()
    if (typeof body?.detail === "string") {
      return body.detail
    }
  } catch {
    // non-JSON error body — ignore and use the status text
  }
  return response.statusText
}
