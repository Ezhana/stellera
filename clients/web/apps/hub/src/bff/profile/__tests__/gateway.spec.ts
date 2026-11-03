import { beforeEach, describe, expect, it, vi } from 'vitest'

import { request } from '@/lib/http'

import { BffError } from '../../errors'
import { HttpProfileGateway } from '../gateway'
import {
  buildCertificationApplicationDto,
  buildCertificationApplicationListDto,
  buildPublicProfileDto,
  buildUserProfileDto,
} from './fixtures'

vi.mock('@/lib/http', () => ({ request: vi.fn() }))

describe('HttpProfileGateway', () => {
  const gateway = new HttpProfileGateway()
  const mockedRequest = vi.mocked(request)

  beforeEach(() => {
    mockedRequest.mockReset()
  })

  it('loads my profile from /profile', async () => {
    mockedRequest.mockResolvedValueOnce(buildUserProfileDto())

    const profile = await gateway.getMyProfile('token-1')

    expect(mockedRequest).toHaveBeenCalledWith('/profile', { token: 'token-1' })
    expect(profile.nickname).toBe('会员（演示）')
    expect(profile.cooperation.records).toHaveLength(1)
  })

  it('patches only the provided profile fields as snake_case', async () => {
    mockedRequest.mockResolvedValueOnce(buildUserProfileDto())

    await gateway.updateMyProfile('token-1', {
      nickname: '新昵称',
      bio: '介绍',
      contactPhone: '13800000000',
      contactWechat: 'wx',
    })

    expect(mockedRequest).toHaveBeenCalledWith('/profile', {
      method: 'PATCH',
      token: 'token-1',
      body: {
        nickname: '新昵称',
        bio: '介绍',
        contact_phone: '13800000000',
        contact_wechat: 'wx',
      },
    })
  })

  it('loads a public profile by encoded id', async () => {
    mockedRequest.mockResolvedValueOnce(buildPublicProfileDto())

    const profile = await gateway.getPublicProfile('token-1', 'a/b')

    expect(mockedRequest).toHaveBeenCalledWith('/profiles/a%2Fb', { token: 'token-1' })
    expect(profile.nickname).toBe('工程师阿远')
  })

  it('lists my certification applications', async () => {
    mockedRequest.mockResolvedValueOnce(buildCertificationApplicationListDto())

    const list = await gateway.listMyCertificationApplications('token-1')

    expect(mockedRequest).toHaveBeenCalledWith('/profile/certification-applications', {
      token: 'token-1',
    })
    expect(list.items).toHaveLength(1)
  })

  it('posts a certification application with the snake_case body', async () => {
    mockedRequest.mockResolvedValueOnce(buildCertificationApplicationDto())

    const application = await gateway.applyCertification('token-1', {
      type: 'enterprise',
      companyName: '远山科技',
      creditCode: '91310000MA1FL0000X',
      contactName: '张三',
      contactPhone: '13800000000',
      description: '资质说明',
    })

    expect(mockedRequest).toHaveBeenCalledWith('/profile/certification-applications', {
      method: 'POST',
      token: 'token-1',
      body: {
        type: 'enterprise',
        real_name: undefined,
        id_number: undefined,
        contact_phone: '13800000000',
        company_name: '远山科技',
        credit_code: '91310000MA1FL0000X',
        contact_name: '张三',
        skills: undefined,
        work_years: undefined,
        project_experience: undefined,
        description: '资质说明',
      },
    })
    expect(application.type).toBe('realname')
  })

  it('throws malformed-response when the payload does not match the schema', async () => {
    mockedRequest.mockResolvedValue({ id: 2 })

    await expect(gateway.getMyProfile('token-1')).rejects.toMatchObject({
      name: 'BffError',
      code: 'malformed-response',
    })
    await expect(gateway.getMyProfile('token-1')).rejects.toBeInstanceOf(BffError)
  })
})
