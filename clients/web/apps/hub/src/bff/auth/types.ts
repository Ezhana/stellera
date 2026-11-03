/** Credentials supplied by the login page; independent from backend wire field names. */
export interface LoginCredentials {
  username: string
  password: string
}

/** Public registration payload; the backend generates the nickname the user may edit later. */
export interface RegisterCredentials {
  username: string
  email: string
  password: string
}
