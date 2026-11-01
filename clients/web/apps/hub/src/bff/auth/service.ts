import type { SessionView } from '@/models'

import { toBffError } from '../errors'
import type { UserDto } from './dto'
import type { AuthGateway } from './gateway'
import { toViewerProfile } from './mapper'
import type { LoginCredentials } from './types'
import type { SessionTokens, StoredAuth, TokenStore } from './token-store'

/**
 * Auth BFF.
 *
 * Owns:
 * - the gateway contract (transport can be swapped for a server-side BFF later);
 * - token persistence (browser storage stays here, never in pages/stores);
 * - refresh orchestration and response mapping into `SessionView`;
 * - normalization of transport errors into `BffError`.
 */
export class AuthBff {
  constructor(
    private readonly gateway: AuthGateway,
    private readonly tokenStore: TokenStore,
  ) {}

  /**
   * Current access token for other frontend BFF services (e.g. the orders gateway).
   *
   * Tokens still never reach pages or stores; this is the narrow port other BFFs use instead of
   * reading browser storage directly. Returns `null` when there is no persisted session.
   */
  accessToken(): string | null {
    return this.tokenStore.read()?.tokens.accessToken ?? null
  }

  async login(credentials: LoginCredentials, remember: boolean): Promise<SessionView> {
    try {
      const dto = await this.gateway.login(credentials)
      const tokens: SessionTokens = {
        accessToken: dto.access_token,
        refreshToken: dto.refresh_token,
      }
      this.tokenStore.save(tokens, remember)
      return this.toSession(dto.user, remember)
    } catch (error) {
      throw toBffError(error, 'login')
    }
  }

  /** Restore a persisted session, refreshing the access token exactly once when needed. */
  async restore(): Promise<SessionView | null> {
    const stored = this.tokenStore.read()
    if (!stored) return null

    try {
      const user = await this.gateway.me(stored.tokens.accessToken)
      return this.toSession(user, stored.remember)
    } catch (error) {
      const bffError = toBffError(error, 'session')
      if (bffError.code !== 'session-expired') {
        this.tokenStore.clear()
        return null
      }
    }

    return this.refresh(stored)
  }

  async logout(): Promise<void> {
    const stored = this.tokenStore.read()
    try {
      if (stored) {
        await this.gateway.logout(stored.tokens.accessToken, stored.tokens.refreshToken)
      }
    } catch {
      // Best-effort revoke; local cleanup must always succeed.
    } finally {
      this.tokenStore.clear()
    }
  }

  private async refresh(stored: StoredAuth): Promise<SessionView | null> {
    try {
      const refreshed = await this.gateway.refresh(stored.tokens.refreshToken)
      const tokens: SessionTokens = {
        accessToken: refreshed.access_token,
        refreshToken: refreshed.refresh_token,
      }
      this.tokenStore.save(tokens, stored.remember)
      const user = await this.gateway.me(tokens.accessToken)
      return this.toSession(user, stored.remember)
    } catch {
      this.tokenStore.clear()
      return null
    }
  }

  private toSession(user: UserDto, remember: boolean): SessionView {
    return {
      viewer: toViewerProfile(user),
      remember,
      authenticatedAt: new Date().toISOString(),
    }
  }
}
