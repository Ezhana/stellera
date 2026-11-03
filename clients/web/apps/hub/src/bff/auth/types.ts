/** Credentials supplied by the login page; independent from backend wire field names. */
export interface LoginCredentials {
  username: string
  password: string
}

/** Public registration payload; the page validates the same constraints before submitting. */
export interface RegisterCredentials {
  username: string
  email: string
  fullName: string
  password: string
}
