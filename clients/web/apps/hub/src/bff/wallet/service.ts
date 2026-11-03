import type {
  RedeemResultView,
  WalletPageModel,
  WalletSummaryView,
  WalletTransactionFilter,
  WalletTransactionListModel,
} from '@/models'

import { BffError, toBffError } from '../errors'
import type { TokenProvider } from '../token-provider'
import type { WalletGateway } from './gateway'
import { toRedeemResultView, toWalletSummaryView, toWalletTransactionListModel } from './mapper'

/** Page keeps the usage tab client-filtered over this many most-recent rows. */
const USAGE_PAGE_SIZE = 50
const RECHARGE_PAGE_SIZE = 20

/**
 * Wallet BFF.
 *
 * Owns token lookup, gateway orchestration, DTO → page model mapping and normalization of every
 * transport error into `BffError`.
 */
export class WalletBff {
  constructor(
    private readonly gateway: WalletGateway,
    private readonly tokenProvider: TokenProvider,
  ) {}

  async getSummary(): Promise<WalletSummaryView> {
    const token = this.requireToken()
    try {
      return toWalletSummaryView(await this.gateway.getSummary(token))
    } catch (error) {
      throw toBffError(error, 'wallet')
    }
  }

  async listTransactions(filter?: WalletTransactionFilter): Promise<WalletTransactionListModel> {
    const token = this.requireToken()
    try {
      return toWalletTransactionListModel(await this.gateway.listTransactions(token, filter))
    } catch (error) {
      throw toBffError(error, 'wallet')
    }
  }

  async redeem(code: string): Promise<RedeemResultView> {
    const token = this.requireToken()
    try {
      return toRedeemResultView(await this.gateway.redeem(token, code))
    } catch (error) {
      throw toBffError(error, 'wallet')
    }
  }

  /** Load the full wallet page in one go: summary, recent usage and recharge history. */
  async loadPage(): Promise<WalletPageModel> {
    const [summary, transactions, recharge] = await Promise.all([
      this.getSummary(),
      this.listTransactions({ pageSize: USAGE_PAGE_SIZE }),
      this.listTransactions({ type: 'recharge', pageSize: RECHARGE_PAGE_SIZE }),
    ])

    return { summary, transactions, rechargeRecords: recharge.transactions }
  }

  private requireToken(): string {
    const token = this.tokenProvider.accessToken()
    if (!token) {
      throw new BffError('session-expired', '登录已过期，请重新登录。')
    }
    return token
  }
}
