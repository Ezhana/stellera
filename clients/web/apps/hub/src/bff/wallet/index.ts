import { authBff } from '@/bff/auth'

import { HttpWalletGateway } from './gateway'
import { WalletBff } from './service'

/** App-wide wallet BFF singleton; pages only consume this instance. */
export const walletBff = new WalletBff(new HttpWalletGateway(), authBff)

export { WalletBff } from './service'
export { HttpWalletGateway } from './gateway'
export type { WalletGateway } from './gateway'
export {
  formatSignedAmount,
  formatTransactionType,
  toRedeemResultView,
  toWalletSummaryView,
  toWalletTransactionListModel,
  toWalletTransactionView,
} from './mapper'
export type { TransactionTypePresentation } from './mapper'
