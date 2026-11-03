import { describe, expect, it } from 'vitest'

import {
  formatApplicationStatus,
  formatApplicationType,
  joinSkills,
  splitSkills,
  toCertificationApplicationListModel,
  toCertificationApplicationView,
  toCooperationStatsView,
  toPublicProfileView,
  toUserProfileView,
} from '../mapper'
import {
  buildCertificationApplicationDto,
  buildCertificationApplicationListDto,
  buildCooperationDto,
  buildProfilePartyDto,
  buildPublicProfileDto,
  buildUserProfileDto,
} from './fixtures'

describe('profile mapper formatting', () => {
  it('labels application types and statuses with frontend copy', () => {
    expect(formatApplicationType('realname')).toEqual({ label: '实名认证', tone: 'info' })
    expect(formatApplicationType('enterprise')).toEqual({ label: '企业认证', tone: 'accent' })
    expect(formatApplicationType('engineer')).toEqual({ label: '工程师认证', tone: 'success' })
    expect(formatApplicationType('mystery')).toEqual({ label: 'mystery', tone: 'default' })

    expect(formatApplicationStatus('pending')).toEqual({ label: '待审核', tone: 'warning' })
    expect(formatApplicationStatus('approved')).toEqual({ label: '已通过', tone: 'success' })
    expect(formatApplicationStatus('rejected')).toEqual({ label: '已驳回', tone: 'error' })
  })

  it('splits and joins skill tags', () => {
    expect(splitSkills('Python, 数据标注、SQL; 报表')).toEqual([
      'Python',
      '数据标注',
      'SQL',
      '报表',
    ])
    expect(splitSkills('   ')).toEqual([])
    expect(joinSkills(['Python', 'SQL'])).toBe('Python,SQL')
  })
})

describe('profile mapper DTO → page model', () => {
  it('maps my profile with certifications, role labels and cooperation stats', () => {
    const profile = toUserProfileView(
      buildUserProfileDto({
        certifications: ['realname', 'enterprise'],
        roles: ['member', 'realname', 'enterprise'],
        skills: 'Python,数据标注',
      }),
    )

    expect(profile).toMatchObject({
      id: '2',
      username: 'member',
      nickname: '会员（演示）',
      email: 'member@example.com',
      realName: '张三',
      bio: '专注医疗数据标注与质检。',
      skills: ['Python', '数据标注'],
      city: '上海',
      contactPhone: '13800000000',
      contactWechat: 'stellera-member',
      certifications: ['realname', 'enterprise'],
      createdAtLabel: expect.any(String),
    })
    expect(profile.roles.map((role) => role.key)).toEqual(['member', 'realname', 'enterprise'])
    expect(profile.cooperation).toMatchObject({
      completedCount: 2,
      partnerCount: 1,
      totalAmountCents: 8_700_000,
      totalAmountLabel: '¥87,000',
    })
    expect(profile.cooperation.records[0]).toMatchObject({
      orderId: '42',
      code: 'FDE-20261101-0001',
      title: '医疗影像数据标注与质检',
      priceLabel: '¥86,000',
      role: 'publisher',
      roleLabel: '发布方',
      counterpart: { id: '5', displayName: '工程师阿远' },
    })
  })

  it('degrades missing profile strings and unknown certifications safely', () => {
    const profile = toUserProfileView(
      buildUserProfileDto({
        nickname: '',
        email: null,
        real_name: null,
        skills: '',
        certifications: ['vip', 'realname'],
        created_at: '',
      }),
    )

    expect(profile.nickname).toBe('member')
    expect(profile.email).toBeNull()
    expect(profile.realName).toBeNull()
    expect(profile.skills).toEqual([])
    expect(profile.certifications).toEqual(['realname'])
    expect(profile.createdAtLabel).toBe('—')
  })

  it('maps a public profile without sensitive fields', () => {
    const profile = toPublicProfileView(buildPublicProfileDto())

    expect(profile).toEqual({
      id: '5',
      nickname: '工程师阿远',
      bio: '曾交付多个医疗影像项目。',
      skills: ['Python', '数据标注'],
      city: '杭州',
      certifications: ['realname', 'engineer'],
      memberSinceLabel: expect.any(String),
      cooperation: expect.objectContaining({ completedCount: 2 }),
    })
    expect('email' in profile).toBe(false)
    expect('realName' in profile).toBe(false)
    expect('contactPhone' in profile).toBe(false)
  })

  it('maps cooperation stats with role labels and formatted money', () => {
    const stats = toCooperationStatsView(
      buildCooperationDto({
        completed_count: 3,
        partner_count: 2,
        total_amount_cents: 12_345,
        records: [
          {
            order_id: 9,
            code: 'FDE-9',
            title: '算法交付',
            price_cents: 12_345,
            completed_at: '2026-11-01T00:00:00.000Z',
            role: 'engineer',
            counterpart: buildProfilePartyDto({ display_name: '远山银行' }),
          },
        ],
      }),
    )

    expect(stats).toMatchObject({
      completedCount: 3,
      partnerCount: 2,
      totalAmountLabel: '¥123.45',
    })
    expect(stats.records[0]).toMatchObject({
      role: 'engineer',
      roleLabel: '接单工程师',
      priceLabel: '¥123.45',
      counterpart: { displayName: '远山银行' },
    })
  })

  it('maps a certification application with its reviewer', () => {
    const view = toCertificationApplicationView(
      buildCertificationApplicationDto({
        status: 'approved',
        review_note: '材料齐全',
        reviewer: { id: 7, display_name: '审核员', certifications: ['realname'] },
        reviewed_at: '2026-11-03T00:00:00.000Z',
      }),
    )

    expect(view).toMatchObject({
      id: '11',
      type: 'realname',
      typeLabel: '实名认证',
      status: 'approved',
      statusLabel: '已通过',
      statusTone: 'success',
      realName: '张三',
      reviewNote: '材料齐全',
      reviewer: { id: '7', displayName: '审核员', certifications: ['realname'] },
      reviewedAtLabel: expect.any(String),
      createdAtLabel: expect.any(String),
    })
  })

  it('maps the application list', () => {
    const model = toCertificationApplicationListModel(
      buildCertificationApplicationListDto([
        buildCertificationApplicationDto(),
        buildCertificationApplicationDto({ id: 12, type: 'engineer' }),
      ]),
    )

    expect(model.applications).toHaveLength(2)
    expect(model.applications[1]?.typeLabel).toBe('工程师认证')
  })
})
