import { HttpAuthGateway } from './gateway'
import { AuthBff } from './service'
import { BrowserTokenStore } from './token-store'

/** App-wide auth BFF singleton; pages and the auth store never talk to HTTP/storage directly. */
export const authBff = new AuthBff(new HttpAuthGateway(), new BrowserTokenStore())

export { AuthBff } from './service'
export { HttpAuthGateway } from './gateway'
export type { AuthGateway } from './gateway'
export type { LoginCredentials, RegisterCredentials } from './types'
export type { SessionTokens, StoredAuth, TokenStore } from './token-store'
