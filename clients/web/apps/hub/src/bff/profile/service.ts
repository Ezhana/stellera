import type {
  CertificationApplicationListModel,
  CertificationApplicationView,
  PublicProfileView,
  UserProfileView,
} from '@/models'

import { BffError, toBffError } from '../errors'
import type { TokenProvider } from '../token-provider'
import type { ProfileGateway } from './gateway'
import {
  joinSkills,
  splitSkills,
  toCertificationApplicationListModel,
  toCertificationApplicationView,
  toPublicProfileView,
  toUserProfileView,
} from './mapper'
import type { CertificationApplicationInput, UpdateMyProfileInput } from './types'

/**
 * Profile BFF.
 *
 * Owns token lookup, gateway orchestration, DTO → page model mapping and normalization of every
 * transport error into `BffError`. Pages never import the gateway directly.
 */
export class ProfileBff {
  constructor(
    private readonly gateway: ProfileGateway,
    private readonly tokenProvider: TokenProvider,
  ) {}

  async getMyProfile(): Promise<UserProfileView> {
    const token = this.requireToken()
    try {
      return toUserProfileView(await this.gateway.getMyProfile(token))
    } catch (error) {
      throw toBffError(error, 'profile')
    }
  }

  async updateMyProfile(input: UpdateMyProfileInput): Promise<UserProfileView> {
    const token = this.requireToken()
    try {
      return toUserProfileView(await this.gateway.updateMyProfile(token, input))
    } catch (error) {
      throw toBffError(error, 'profile')
    }
  }

  async getPublicProfile(userId: string): Promise<PublicProfileView> {
    const token = this.requireToken()
    try {
      return toPublicProfileView(await this.gateway.getPublicProfile(token, userId))
    } catch (error) {
      throw toBffError(error, 'profile')
    }
  }

  async listMyCertificationApplications(): Promise<CertificationApplicationListModel> {
    const token = this.requireToken()
    try {
      return toCertificationApplicationListModel(
        await this.gateway.listMyCertificationApplications(token),
      )
    } catch (error) {
      throw toBffError(error, 'profile')
    }
  }

  /** Submit one certification application; skill tags are normalized before the wire call. */
  async applyCertification(
    input: CertificationApplicationInput,
  ): Promise<CertificationApplicationView> {
    const token = this.requireToken()
    try {
      const normalized: CertificationApplicationInput = {
        ...input,
        skills: input.skills === undefined ? undefined : joinSkills(splitSkills(input.skills)),
        description: input.description?.trim() ? input.description.trim() : undefined,
      }
      return toCertificationApplicationView(
        await this.gateway.applyCertification(token, normalized),
      )
    } catch (error) {
      throw toBffError(error, 'profile')
    }
  }

  private requireToken(): string {
    const token = this.tokenProvider.accessToken()
    if (!token) {
      throw new BffError('session-expired', '登录已过期，请重新登录。')
    }
    return token
  }
}
