/**
 * 测试环境演示账号。
 *
 * 弱口令与后端种子数据保持一致（见 `services/hub-api/app/scripts/seed.py`），
 * 便于测试人员在登录页一键填入。仅用于开发/测试环境（含 deploy/ 的 staging），
 * 发布到生产前必须移除本区块或改成真实的账号开通指引。
 */
export interface DemoAccount {
  /** 种子数据中的角色中文名。 */
  role: string
  /** 该角色能做什么，帮助测试人员挑选账号。 */
  scope: string
  username: string
  password: string
}

export const DEMO_ACCOUNTS: readonly DemoAccount[] = [
  {
    role: '管理员',
    scope: '全部权限',
    username: 'admin',
    password: 'admin12345',
  },
  {
    role: '企业',
    scope: '发布需求 / 确认交付',
    username: 'enterprise',
    password: 'enterprise12345',
  },
  {
    role: '工程师',
    scope: '认领订单 / 提交日志',
    username: 'engineer',
    password: 'engineer12345',
  },
  {
    role: '运营',
    scope: '后台运营写操作',
    username: 'operator',
    password: 'operator12345',
  },
  {
    role: '访客',
    scope: '只读访问',
    username: 'viewer',
    password: 'viewer12345',
  },
]
