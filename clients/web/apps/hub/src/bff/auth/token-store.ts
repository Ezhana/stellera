const STORAGE_KEY = 'stellera-hub-auth'

export interface SessionTokens {
  accessToken: string
  refreshToken: string
}

export interface StoredAuth {
  tokens: SessionTokens
  /** True when the session lives in localStorage ("remember me"), false for sessionStorage. */
  remember: boolean
}

export interface TokenStore {
  read(): StoredAuth | null
  save(tokens: SessionTokens, remember: boolean): void
  clear(): void
}

interface StoredPayload {
  accessToken: string
  refreshToken: string
}

/**
 * Browser token persistence owned by the BFF.
 *
 * Pages/stores never touch browser storage or token fields directly; `AuthBff` is the only caller.
 */
export class BrowserTokenStore implements TokenStore {
  read(): StoredAuth | null {
    const persistent = readFrom(getStorage(true))
    if (persistent) {
      return { tokens: persistent, remember: true }
    }

    const tabScoped = readFrom(getStorage(false))
    if (tabScoped) {
      return { tokens: tabScoped, remember: false }
    }

    return null
  }

  save(tokens: SessionTokens, remember: boolean): void {
    const payload: StoredPayload = {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
    }
    const target = getStorage(remember)
    const other = getStorage(!remember)
    try {
      other?.removeItem(STORAGE_KEY)
      target?.setItem(STORAGE_KEY, JSON.stringify(payload))
    } catch {
      // Persisting is best-effort; the in-memory session still works for this tab.
    }
  }

  clear(): void {
    try {
      getStorage(true)?.removeItem(STORAGE_KEY)
      getStorage(false)?.removeItem(STORAGE_KEY)
    } catch {
      // Ignore storage errors on logout.
    }
  }
}

function getStorage(remember: boolean): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return remember ? window.localStorage : window.sessionStorage
  } catch {
    return null
  }
}

function readFrom(storage: Storage | null): SessionTokens | null {
  if (!storage) return null
  try {
    const raw = storage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (!isStoredPayload(parsed)) return null
    return { accessToken: parsed.accessToken, refreshToken: parsed.refreshToken }
  } catch {
    return null
  }
}

function isStoredPayload(value: unknown): value is StoredPayload {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  return (
    typeof candidate.accessToken === 'string' &&
    candidate.accessToken.length > 0 &&
    typeof candidate.refreshToken === 'string' &&
    candidate.refreshToken.length > 0
  )
}
