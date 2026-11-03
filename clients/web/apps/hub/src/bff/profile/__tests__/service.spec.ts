import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/http'

import type { TokenProvider } from '../../token-provider'
import type { ProfileGateway } from '../gateway'
import { ProfileBff } from '../service'
import {
  buildCertificationApplicationDto,
  buildCertificationApplicationListDto,
  buildPublicProfileDto,
  buildUserProfileDto,
} from './fixtures'

function createGateway(): ProfileGateway {
  return {
    getMyProfile: vi.fn(async () => buildUserProfileDto()),
    updateMyProfile: vi.fn(async () => buildUserProfileDto({ nickname: '新昵称' })),
    getPublicProfile: vi.fn(async () => buildPublicProfileDto()),
    listMyCertificationApplications: vi.fn(async () =>
      buildCertificationApplicationListDto([
        buildCertificationApplicationDto(),
        buildCertificationApplicationDto({ id: 12, type: 'enterprise', status: 'rejected' }),
      ]),
    ),
    applyCertification: vi.fn(async () => buildCertificationApplicationDto({ status: 'pending' })),
  }
}

describe('ProfileBff', () => {
  let gateway: ProfileGateway
  let tokenProvider: TokenProvider
  let bff: ProfileBff

  beforeEach(() => {
    gateway = createGateway()
    tokenProvider = { accessToken: vi.fn(() => 'token-1') }
    bff = new ProfileBff(gateway, tokenProvider)
  })

  it('maps my profile with the current token', async () => {
    const profile = await bff.getMyProfile()

    expect(gateway.getMyProfile).toHaveBeenCalledWith('token-1')
    expect(profile.nickname).toBe('会员（演示）')
    expect(profile.certifications).toEqual(['realname'])
  })

  it('updates my profile and maps the refreshed model', async () => {
    const profile = await bff.updateMyProfile({ nickname: ' 新昵称 ' })

    expect(gateway.updateMyProfile).toHaveBeenCalledWith('token-1', { nickname: ' 新昵称 ' })
    expect(profile.nickname).toBe('新昵称')
  })

  it('loads a public profile by user id', async () => {
    const profile = await bff.getPublicProfile('5')

    expect(gateway.getPublicProfile).toHaveBeenCalledWith('token-1', '5')
    expect(profile.cooperation.records).toHaveLength(1)
  })

  it('lists my certification applications', async () => {
    const model = await bff.listMyCertificationApplications()

    expect(gateway.listMyCertificationApplications).toHaveBeenCalledWith('token-1')
    expect(model.applications).toHaveLength(2)
    expect(model.applications[1]?.statusLabel).toBe('已驳回')
  })

  it('normalizes skill tags before submitting an application', async () => {
    await bff.applyCertification({
      type: 'engineer',
      skills: ' Python, 数据标注 ',
      workYears: 5,
      projectExperience: '医疗影像',
      contactPhone: '13800000000',
    })

    expect(gateway.applyCertification).toHaveBeenCalledWith('token-1', {
      type: 'engineer',
      skills: 'Python,数据标注',
      workYears: 5,
      projectExperience: '医疗影像',
      contactPhone: '13800000000',
      description: undefined,
    })
  })

  it('trims the description and keeps blank descriptions null', async () => {
    await bff.applyCertification({ type: 'realname', description: '  备注  ' })
    await bff.applyCertification({ type: 'realname', description: '   ' })

    expect(gateway.applyCertification).toHaveBeenNthCalledWith(
      1,
      'token-1',
      expect.objectContaining({ description: '备注', skills: undefined }),
    )
    expect(gateway.applyCertification).toHaveBeenNthCalledWith(
      2,
      'token-1',
      expect.objectContaining({ description: undefined }),
    )
  })

  it('fails with session-expired and never touches the gateway without a token', async () => {
    tokenProvider = { accessToken: vi.fn(() => null) }
    bff = new ProfileBff(gateway, tokenProvider)

    await expect(bff.getMyProfile()).rejects.toMatchObject({
      name: 'BffError',
      code: 'session-expired',
    })
    await expect(bff.updateMyProfile({ nickname: 'x' })).rejects.toMatchObject({
      code: 'session-expired',
    })
    await expect(bff.applyCertification({ type: 'realname' })).rejects.toMatchObject({
      code: 'session-expired',
    })
    expect(gateway.getMyProfile).not.toHaveBeenCalled()
    expect(gateway.updateMyProfile).not.toHaveBeenCalled()
    expect(gateway.applyCertification).not.toHaveBeenCalled()
  })

  it('normalizes forbidden, conflict and network transport errors', async () => {
    vi.mocked(gateway.getMyProfile).mockRejectedValueOnce(new ApiError(403, 'forbidden'))
    vi.mocked(gateway.updateMyProfile).mockRejectedValueOnce(
      new ApiError(409, '邮箱已被使用', '邮箱已被使用'),
    )
    vi.mocked(gateway.getPublicProfile).mockRejectedValueOnce(new ApiError(0, 'network'))

    await expect(bff.getMyProfile()).rejects.toMatchObject({ code: 'forbidden' })
    await expect(bff.updateMyProfile({ email: 'x@example.com' })).rejects.toMatchObject({
      code: 'conflict',
      message: '邮箱已被使用',
    })
    await expect(bff.getPublicProfile('5')).rejects.toMatchObject({ code: 'network' })
  })
})
