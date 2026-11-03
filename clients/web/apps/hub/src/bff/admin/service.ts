import type {
  AdminCertificationApplicationListModel,
  AdminCertificationApplicationView,
  AdminRedeemCodeBatch,
  AdminRedeemCodeListModel,
  AdminRedeemCodeStatus,
  AdminRedeemCodeView,
  AdminRoleOption,
  AdminSettingsModel,
  AdminUserListModel,
  AdminUserView,
} from '@/models'

import { BffError, toBffError } from '../errors'
import type { TokenProvider } from '../token-provider'
import type { AdminGateway } from './gateway'
import {
  toAdminCertificationApplicationListModel,
  toAdminCertificationApplicationView,
  toAdminRedeemCodeBatch,
  toAdminRedeemCodeListModel,
  toAdminRedeemCodeView,
  toAdminRoleOption,
  toAdminSettingsModel,
  toAdminUserListModel,
  toAdminUserView,
} from './mapper'
import type {
  AdminCertificationApplicationFilter,
  AdminRedeemCodeFilter,
  AdminUserFilter,
  AdminWalletAdjustmentInput,
  CreateRedeemCodeInput,
  UpdateAdminUserInput,
} from './types'

/**
 * Admin BFF.
 *
 * Owns token lookup, gateway orchestration, DTO → page model mapping and normalization of every
 * transport error into `BffError`. Pages never import the gateway directly.
 */
export class AdminBff {
  constructor(
    private readonly gateway: AdminGateway,
    private readonly tokenProvider: TokenProvider,
  ) {}

  async listUsers(filter?: AdminUserFilter): Promise<AdminUserListModel> {
    const token = this.requireToken()
    try {
      return toAdminUserListModel(await this.gateway.listUsers(token, filter))
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async listRoles(): Promise<AdminRoleOption[]> {
    const token = this.requireToken()
    try {
      const dto = await this.gateway.listRoles(token)
      return dto.items.map(toAdminRoleOption)
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async updateUser(id: string, input: UpdateAdminUserInput): Promise<AdminUserView> {
    const token = this.requireToken()
    try {
      return toAdminUserView(await this.gateway.updateUser(token, id, input))
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  /** Adjust a user's balance and return the refreshed user row (with the new balance). */
  async walletAdjustment(id: string, input: AdminWalletAdjustmentInput): Promise<AdminUserView> {
    const token = this.requireToken()
    try {
      return toAdminUserView(await this.gateway.walletAdjustment(token, id, input))
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async listRedeemCodes(filter?: AdminRedeemCodeFilter): Promise<AdminRedeemCodeListModel> {
    const token = this.requireToken()
    try {
      return toAdminRedeemCodeListModel(await this.gateway.listRedeemCodes(token, filter))
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async createRedeemCodes(input: CreateRedeemCodeInput): Promise<AdminRedeemCodeBatch> {
    const token = this.requireToken()
    try {
      return toAdminRedeemCodeBatch(await this.gateway.createRedeemCodes(token, input))
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async updateRedeemCodeStatus(
    id: string,
    status: Extract<AdminRedeemCodeStatus, 'active' | 'disabled'>,
  ): Promise<AdminRedeemCodeView> {
    const token = this.requireToken()
    try {
      return toAdminRedeemCodeView(await this.gateway.updateRedeemCode(token, id, status))
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async listCertificationApplications(
    filter?: AdminCertificationApplicationFilter,
  ): Promise<AdminCertificationApplicationListModel> {
    const token = this.requireToken()
    try {
      return toAdminCertificationApplicationListModel(
        await this.gateway.listCertificationApplications(token, filter),
      )
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async approveCertificationApplication(
    id: string,
    note?: string | null,
  ): Promise<AdminCertificationApplicationView> {
    const token = this.requireToken()
    try {
      return toAdminCertificationApplicationView(
        await this.gateway.approveCertificationApplication(token, id, note),
      )
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async rejectCertificationApplication(
    id: string,
    note?: string | null,
  ): Promise<AdminCertificationApplicationView> {
    const token = this.requireToken()
    try {
      return toAdminCertificationApplicationView(
        await this.gateway.rejectCertificationApplication(token, id, note),
      )
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async getSettings(): Promise<AdminSettingsModel> {
    const token = this.requireToken()
    try {
      return toAdminSettingsModel(await this.gateway.getSettings(token))
    } catch (error) {
      throw toBffError(error, 'admin')
    }
  }

  async updateSettings(values: Record<string, string>): Promise<AdminSettingsModel> {
    const token = this.requireToken()
    try {
      return toAdminSettingsModel(await this.gateway.updateSettings(token, values))
    } catch (error) {
      throw toBffError(error, 'admin')
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
