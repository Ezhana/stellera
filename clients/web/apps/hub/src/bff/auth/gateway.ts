import type { ZodType } from 'zod'

import { request } from '@/lib/http'
import { BffError } from '../errors'
import {
  loginResponseDtoSchema,
  tokenPairDtoSchema,
  userDtoSchema,
  type LoginResponseDto,
  type TokenPairDto,
  type UserDto,
} from './dto'
import type { LoginCredentials } from './types'

function parseDto<T>(schema: ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value)
  if (!result.success) {
    throw new BffError('malformed-response', '服务返回的数据格式异常。', {
      originalError: result.error,
    })
  }
  return result.data
}

/**
 * Port for the auth backend.
 *
 * Today it is implemented by `HttpAuthGateway` (direct `/api/v1/auth/*` calls). A future
 * server-side BFF can implement the same interface without touching the services, store or pages.
 */
export interface AuthGateway {
  login(credentials: LoginCredentials): Promise<LoginResponseDto>
  refresh(refreshToken: string): Promise<TokenPairDto>
  me(accessToken: string): Promise<UserDto>
  logout(accessToken: string, refreshToken: string): Promise<void>
}

export class HttpAuthGateway implements AuthGateway {
  async login(credentials: LoginCredentials): Promise<LoginResponseDto> {
    const raw = await request<unknown>('/auth/login', {
      method: 'POST',
      body: credentials,
    })
    return parseDto(loginResponseDtoSchema, raw)
  }

  async refresh(refreshToken: string): Promise<TokenPairDto> {
    const raw = await request<unknown>('/auth/refresh', {
      method: 'POST',
      body: { refresh_token: refreshToken },
    })
    return parseDto(tokenPairDtoSchema, raw)
  }

  async me(accessToken: string): Promise<UserDto> {
    const raw = await request<unknown>('/auth/me', { token: accessToken })
    return parseDto(userDtoSchema, raw)
  }

  async logout(accessToken: string, refreshToken: string): Promise<void> {
    await request<void>('/auth/logout', {
      method: 'POST',
      body: { refresh_token: refreshToken },
      token: accessToken,
    })
  }
}
