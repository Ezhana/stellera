import type { ZodType } from 'zod'

import type { WalletTransactionFilter } from '@/models'
import { request } from '@/lib/http'

import { BffError } from '../errors'
import {
  redeemResultDtoSchema,
  walletSummaryDtoSchema,
  walletTransactionListDtoSchema,
  type RedeemResultDto,
  type WalletSummaryDto,
  type WalletTransactionListDto,
} from './dto'

const DEFAULT_PAGE_SIZE = 20

function parseDto<T>(schema: ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value)
  if (!result.success) {
    throw new BffError('malformed-response', '服务返回的钱包数据格式异常。', {
      originalError: result.error,
    })
  }
  return result.data
}

/**
 * Port for the wallet backend.
 *
 * Implemented today by `HttpWalletGateway` (direct `/api/v1/wallet/*` calls). A future server-side
 * BFF can implement the same interface without touching the service or the pages.
 */
export interface WalletGateway {
  getSummary(token: string): Promise<WalletSummaryDto>
  listTransactions(
    token: string,
    filter?: WalletTransactionFilter,
  ): Promise<WalletTransactionListDto>
  redeem(token: string, code: string): Promise<RedeemResultDto>
}

export class HttpWalletGateway implements WalletGateway {
  async getSummary(token: string): Promise<WalletSummaryDto> {
    const raw = await request<unknown>('/wallet', { token })
    return parseDto(walletSummaryDtoSchema, raw)
  }

  async listTransactions(
    token: string,
    filter?: WalletTransactionFilter,
  ): Promise<WalletTransactionListDto> {
    const query = new URLSearchParams()
    if (filter?.type && filter.type !== 'all') query.set('type', filter.type)
    query.set('page', String(filter?.page ?? 1))
    query.set('page_size', String(filter?.pageSize ?? DEFAULT_PAGE_SIZE))

    const raw = await request<unknown>(`/wallet/transactions?${query.toString()}`, { token })
    return parseDto(walletTransactionListDtoSchema, raw)
  }

  async redeem(token: string, code: string): Promise<RedeemResultDto> {
    const raw = await request<unknown>('/wallet/redeem', {
      method: 'POST',
      token,
      body: { code },
    })
    return parseDto(redeemResultDtoSchema, raw)
  }
}
