/**
 * Narrow port every feature BFF uses to read the current access token.
 *
 * Implemented by `AuthBff`; tokens never reach pages or stores.
 */
export interface TokenProvider {
  accessToken(): string | null
}
