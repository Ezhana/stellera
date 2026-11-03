<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { z } from 'zod'

import { BffError } from '@/bff/errors'
import { profileBff } from '@/bff/profile'
import PageHeader from '@/components/console/PageHeader.vue'
import CertificationMark from '@/components/identity/CertificationMark.vue'
import UiAlert from '@/components/ui/UiAlert.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiChip from '@/components/ui/UiChip.vue'
import UiIcon from '@/components/ui/UiIcon.vue'
import UiInput from '@/components/ui/UiInput.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import {
  CERTIFICATION_APPLICATION_TYPES,
  type CertificationApplicationType,
  type CertificationApplicationTypeMeta,
  type CertificationApplicationView,
  type UserProfileView,
} from '@/models'
import { useAuthStore } from '@/stores/auth'

type ProfileTab = 'profile' | 'certification' | 'cooperation'

const auth = useAuthStore()
const viewer = computed(() => auth.viewer)

const activeTab = ref<ProfileTab>('profile')
const profile = ref<UserProfileView | null>(null)
const applications = ref<CertificationApplicationView[]>([])
const loading = ref(true)
const errorMessage = ref('')
const successMessage = ref('')

const nickname = ref('')
const email = ref('')
const bio = ref('')
const skills = ref('')
const city = ref('')
const contactPhone = ref('')
const contactWechat = ref('')
const savingProfile = ref(false)
const profileError = ref('')
const profileFieldErrors = reactive<{
  nickname?: string
  email?: string
  bio?: string
  city?: string
  contactPhone?: string
  contactWechat?: string
}>({})

const applicationType = ref<CertificationApplicationType | null>(null)
const applicationFields = reactive({
  realName: '',
  idNumber: '',
  contactPhone: '',
  companyName: '',
  creditCode: '',
  contactName: '',
  skills: '',
  workYears: '',
  projectExperience: '',
  description: '',
})
const submittingApplication = ref(false)
const applicationError = ref('')
const applicationFieldErrors = reactive<Record<string, string | undefined>>({})

const profileSchema = z.object({
  nickname: z.string().trim().min(1, '请输入昵称').max(64, '昵称长度不能超过 64 个字符'),
  email: z
    .string()
    .trim()
    .min(1, '请输入邮箱')
    .max(320, '邮箱长度不能超过 320 个字符')
    .email('请输入有效的邮箱地址'),
  bio: z.string().trim().max(1000, '介绍不能超过 1000 个字符'),
  skills: z.string().trim().max(255, '技能标签不能超过 255 个字符'),
  city: z.string().trim().max(64, '城市长度不能超过 64 个字符'),
  contactPhone: z.string().trim().max(32, '联系电话不能超过 32 个字符'),
  contactWechat: z.string().trim().max(64, '微信号不能超过 64 个字符'),
})

const realnameSchema = z.object({
  realName: z.string().trim().min(1, '请输入真实姓名').max(64, '真实姓名不能超过 64 个字符'),
  idNumber: z.string().trim().min(1, '请输入身份证号').max(32, '身份证号不能超过 32 个字符'),
  contactPhone: z.string().trim().min(1, '请输入联系电话').max(32, '联系电话不能超过 32 个字符'),
  description: z.string().trim().max(2000, '备注不能超过 2000 个字符'),
})

const enterpriseSchema = z.object({
  companyName: z.string().trim().min(1, '请输入公司名称').max(128, '公司名称不能超过 128 个字符'),
  creditCode: z
    .string()
    .trim()
    .min(1, '请输入统一社会信用代码')
    .max(64, '统一社会信用代码不能超过 64 个字符'),
  contactName: z.string().trim().min(1, '请输入联系人').max(64, '联系人不能超过 64 个字符'),
  contactPhone: z.string().trim().min(1, '请输入联系电话').max(32, '联系电话不能超过 32 个字符'),
  description: z.string().trim().max(2000, '资质说明不能超过 2000 个字符'),
})

const engineerSchema = z.object({
  skills: z.string().trim().min(1, '请填写技能').max(255, '技能不能超过 255 个字符'),
  workYears: z
    .string()
    .trim()
    .min(1, '请输入工作年限')
    .refine((value) => /^\d+$/.test(value), '工作年限需为整数')
    .transform((value) => Number(value))
    .refine((value) => value >= 0 && value <= 60, '工作年限需在 0–60 年之间'),
  projectExperience: z
    .string()
    .trim()
    .min(1, '请填写项目经历')
    .max(2000, '项目经历不能超过 2000 个字符'),
  contactPhone: z.string().trim().min(1, '请输入联系电话').max(32, '联系电话不能超过 32 个字符'),
  description: z.string().trim().max(2000, '备注不能超过 2000 个字符'),
})

const certificationTypes = computed(() => profile.value?.certifications ?? [])
const hasRealname = computed(() => certificationTypes.value.includes('realname'))

/** Types the viewer may still apply for: realname first, then enterprise/engineer. */
const availableTypes = computed<CertificationApplicationTypeMeta[]>(() => {
  const pendingTypes = new Set(
    applications.value.filter((item) => item.status === 'pending').map((item) => item.type),
  )
  return CERTIFICATION_APPLICATION_TYPES.filter((meta) => {
    if (pendingTypes.has(meta.key)) return false
    if (meta.key === 'realname') return !hasRealname.value
    return hasRealname.value && !certificationTypes.value.includes(meta.key)
  })
})

const activeTypeMeta = computed(
  () => CERTIFICATION_APPLICATION_TYPES.find((meta) => meta.key === applicationType.value) ?? null,
)

function toErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof BffError)) return fallback

  switch (error.code) {
    case 'session-expired':
      return '登录已过期，请重新登录。'
    case 'forbidden':
      return '当前账号没有权限执行该操作。'
    case 'not-found':
      return '请求的资料不存在或已被移除。'
    case 'conflict':
    case 'invalid-input':
      return error.message || '提交的内容不符合要求，请检查后重试。'
    case 'network':
      return '无法连接到服务，请检查网络后重试。'
    case 'server':
      return '服务暂时不可用，请稍后再试。'
    case 'malformed-response':
      return '服务返回的数据格式异常，请联系管理员。'
    default:
      return error.message || fallback
  }
}

function syncForm(model: UserProfileView): void {
  nickname.value = model.nickname
  email.value = model.email ?? ''
  bio.value = model.bio
  skills.value = model.skills.join(', ')
  city.value = model.city
  contactPhone.value = model.contactPhone
  contactWechat.value = model.contactWechat
}

async function loadProfile(): Promise<void> {
  try {
    profile.value = await profileBff.getMyProfile()
    syncForm(profile.value)
  } catch (error) {
    errorMessage.value = toErrorMessage(error, '个人信息加载失败，请稍后重试。')
  }
}

async function loadApplications(): Promise<void> {
  try {
    const model = await profileBff.listMyCertificationApplications()
    applications.value = model.applications
  } catch {
    applications.value = []
  }
}

async function loadAll(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  errorMessage.value = ''
  await Promise.all([loadProfile(), loadApplications()])
  loading.value = false
}

async function saveProfile(): Promise<void> {
  if (savingProfile.value) return
  profileError.value = ''
  successMessage.value = ''
  for (const key of Object.keys(profileFieldErrors)) {
    profileFieldErrors[key as keyof typeof profileFieldErrors] = undefined
  }

  const result = profileSchema.safeParse({
    nickname: nickname.value,
    email: email.value,
    bio: bio.value,
    skills: skills.value,
    city: city.value,
    contactPhone: contactPhone.value,
    contactWechat: contactWechat.value,
  })
  if (!result.success) {
    for (const issue of result.error.issues) {
      const field = issue.path[0]
      if (typeof field !== 'string') continue
      const target = profileFieldErrors as Record<string, string | undefined>
      if (!target[field]) target[field] = issue.message
    }
    return
  }

  savingProfile.value = true
  try {
    profile.value = await profileBff.updateMyProfile({
      nickname: result.data.nickname,
      email: result.data.email,
      bio: result.data.bio,
      skills: result.data.skills,
      city: result.data.city,
      contactPhone: result.data.contactPhone,
      contactWechat: result.data.contactWechat,
    })
    syncForm(profile.value)
    successMessage.value = '个人信息已保存。'
  } catch (error) {
    profileError.value = toErrorMessage(error, '个人信息保存失败，请稍后重试。')
  } finally {
    savingProfile.value = false
  }
}

function openApplication(type: CertificationApplicationType): void {
  applicationType.value = type
  applicationError.value = ''
  for (const key of Object.keys(applicationFields)) {
    applicationFields[key as keyof typeof applicationFields] = ''
  }
  for (const key of Object.keys(applicationFieldErrors)) applicationFieldErrors[key] = undefined
}

function closeApplication(): void {
  applicationType.value = null
  applicationError.value = ''
}

function collectApplicationFields(): Record<string, string> {
  return {
    realName: applicationFields.realName,
    idNumber: applicationFields.idNumber,
    contactPhone: applicationFields.contactPhone,
    companyName: applicationFields.companyName,
    creditCode: applicationFields.creditCode,
    contactName: applicationFields.contactName,
    skills: applicationFields.skills,
    workYears: applicationFields.workYears,
    projectExperience: applicationFields.projectExperience,
    description: applicationFields.description,
  }
}

function validateApplication(type: CertificationApplicationType): boolean {
  for (const key of Object.keys(applicationFieldErrors)) applicationFieldErrors[key] = undefined
  const values = collectApplicationFields()
  const schema =
    type === 'realname' ? realnameSchema : type === 'enterprise' ? enterpriseSchema : engineerSchema
  const result = schema.safeParse(values)
  if (result.success) return true

  for (const issue of result.error.issues) {
    const field = issue.path[0]
    if (typeof field !== 'string') continue
    if (!applicationFieldErrors[field]) applicationFieldErrors[field] = issue.message
  }
  return false
}

async function submitApplication(): Promise<void> {
  if (!applicationType.value || submittingApplication.value) return
  const type = applicationType.value
  applicationError.value = ''
  successMessage.value = ''
  if (!validateApplication(type)) return

  submittingApplication.value = true
  try {
    await profileBff.applyCertification({
      type,
      realName: applicationFields.realName.trim() || undefined,
      idNumber: applicationFields.idNumber.trim() || undefined,
      contactPhone: applicationFields.contactPhone.trim() || undefined,
      companyName: applicationFields.companyName.trim() || undefined,
      creditCode: applicationFields.creditCode.trim() || undefined,
      contactName: applicationFields.contactName.trim() || undefined,
      skills: type === 'engineer' ? applicationFields.skills.trim() : undefined,
      workYears:
        type === 'engineer' && applicationFields.workYears.trim()
          ? Number(applicationFields.workYears.trim())
          : undefined,
      projectExperience:
        type === 'engineer' ? applicationFields.projectExperience.trim() || undefined : undefined,
      description: applicationFields.description.trim() || undefined,
    })
    successMessage.value = '认证申请已提交，等待平台审核。'
    closeApplication()
    await Promise.all([loadProfile(), loadApplications()])
  } catch (error) {
    applicationError.value = toErrorMessage(error, '认证申请提交失败，请稍后重试。')
  } finally {
    submittingApplication.value = false
  }
}

function changeTab(tab: ProfileTab): void {
  activeTab.value = tab
  successMessage.value = ''
  profileError.value = ''
  applicationError.value = ''
}

onMounted(() => {
  void loadAll()
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="profile-page">
      <PageHeader
        eyebrow="MY PROFILE"
        title="个人信息"
        description="维护昵称、介绍与合作信息，申请实名 / 企业 / 工程师认证。"
      >
        <template #actions>
          <RouterLink
            v-if="profile"
            class="profile-page__link-button"
            :to="{ name: 'public-profile', params: { id: profile.id } }"
          >
            查看公开主页
            <UiIcon name="arrow-right" :size="16" />
          </RouterLink>
          <UiButton variant="secondary" size="sm" :loading="loading" @click="loadAll(false)">
            <UiIcon name="refresh" :size="16" />
            刷新
          </UiButton>
        </template>
      </PageHeader>

      <UiAlert
        v-if="successMessage"
        variant="success"
        title="操作成功"
        dismissible
        @close="successMessage = ''"
      >
        {{ successMessage }}
      </UiAlert>

      <div v-if="loading" class="profile-state" role="status" aria-live="polite">
        正在加载个人信息…
      </div>

      <div v-else-if="errorMessage" class="profile-state profile-state--error">
        <UiAlert variant="error" title="个人信息加载失败">{{ errorMessage }}</UiAlert>
        <UiButton variant="secondary" size="sm" @click="loadAll()">重试</UiButton>
      </div>

      <template v-else-if="profile">
        <UiCard padding="lg" class="profile-hero">
          <div class="profile-hero__identity">
            <span class="profile-hero__avatar" aria-hidden="true">{{ viewer.initials }}</span>
            <div class="profile-hero__copy">
              <div class="profile-hero__name-row">
                <h2 class="profile-hero__name">{{ profile.nickname }}</h2>
                <CertificationMark :certifications="profile.certifications" />
              </div>
              <p class="profile-hero__meta">
                @{{ profile.username }}
                <span v-if="profile.city">· {{ profile.city }}</span>
                <span v-if="profile.realName">· 实名：{{ profile.realName }}</span>
              </p>
              <p v-if="profile.bio" class="profile-hero__bio">{{ profile.bio }}</p>
            </div>
          </div>
          <div v-if="profile.skills.length" class="profile-hero__skills">
            <UiChip v-for="skill in profile.skills" :key="skill">{{ skill }}</UiChip>
          </div>
        </UiCard>

        <div class="profile-tabs" role="tablist" aria-label="个人信息视图">
          <button
            v-for="tab in [
              { key: 'profile', label: '资料' },
              { key: 'certification', label: '认证' },
              { key: 'cooperation', label: '合作记录' },
            ] as const"
            :key="tab.key"
            type="button"
            role="tab"
            class="profile-tabs__button"
            :class="{ 'is-active': activeTab === tab.key }"
            :aria-selected="activeTab === tab.key ? 'true' : 'false'"
            :data-tab="tab.key"
            @click="changeTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </div>

        <UiCard v-if="activeTab === 'profile'" padding="lg" class="profile-section">
          <header class="profile-section__head">
            <h2 class="profile-section__title">资料</h2>
            <p class="profile-section__hint">昵称会展示在订单、申请与公开主页上。</p>
          </header>

          <UiAlert
            v-if="profileError"
            variant="error"
            title="保存失败"
            dismissible
            @close="profileError = ''"
          >
            {{ profileError }}
          </UiAlert>

          <form class="profile-form" novalidate @submit.prevent="saveProfile">
            <UiInput
              v-model="nickname"
              label="昵称"
              name="profile-nickname"
              :maxlength="64"
              :error="profileFieldErrors.nickname"
              :disabled="savingProfile"
            />
            <UiInput
              v-model="email"
              label="邮箱"
              name="profile-email"
              type="email"
              :maxlength="320"
              :error="profileFieldErrors.email"
              :disabled="savingProfile"
            />
            <UiInput
              v-model="city"
              label="城市"
              name="profile-city"
              :maxlength="64"
              placeholder="例如：上海"
              :error="profileFieldErrors.city"
              :disabled="savingProfile"
            />
            <UiInput
              v-model="contactPhone"
              label="联系电话"
              name="profile-phone"
              :maxlength="32"
              :error="profileFieldErrors.contactPhone"
              :disabled="savingProfile"
            />
            <UiInput
              v-model="contactWechat"
              label="微信"
              name="profile-wechat"
              :maxlength="64"
              :error="profileFieldErrors.contactWechat"
              :disabled="savingProfile"
            />
            <UiInput
              v-model="skills"
              class="profile-form__wide"
              label="技能标签"
              name="profile-skills"
              placeholder="用逗号分隔，例如：Python, 数据标注"
              :maxlength="255"
              help="用逗号分隔多个技能，保存后展示为标签。"
              :disabled="savingProfile"
            />

            <div class="profile-form__field profile-form__wide">
              <label class="profile-form__label" for="profile-bio">介绍</label>
              <textarea
                id="profile-bio"
                v-model="bio"
                class="profile-form__textarea"
                rows="4"
                name="profile-bio"
                :maxlength="1000"
                :disabled="savingProfile"
                placeholder="介绍一下你的行业背景与交付经验…"
              />
              <p v-if="profileFieldErrors.bio" class="profile-form__error" role="alert">
                {{ profileFieldErrors.bio }}
              </p>
              <p v-else class="profile-form__help">已输入 {{ bio.length }} / 1000 字</p>
            </div>

            <div class="profile-form__actions profile-form__wide">
              <UiButton type="submit" :loading="savingProfile">保存资料</UiButton>
            </div>
          </form>
        </UiCard>

        <template v-else-if="activeTab === 'certification'">
          <UiCard padding="lg" class="profile-section">
            <header class="profile-section__head">
              <h2 class="profile-section__title">当前认证</h2>
              <p class="profile-section__hint">
                实名认证是基础认证；企业认证与工程师认证需要先完成实名认证。
              </p>
            </header>
            <div v-if="profile.certifications.length" class="profile-cert-list">
              <CertificationMark :certifications="profile.certifications" />
            </div>
            <p v-else class="profile-section__empty">尚未获得任何认证。</p>

            <div v-if="availableTypes.length" class="profile-cert-types">
              <UiButton
                v-for="meta in availableTypes"
                :key="meta.key"
                variant="secondary"
                size="sm"
                :data-apply-type="meta.key"
                @click="openApplication(meta.key)"
              >
                申请{{ meta.label }}
              </UiButton>
            </div>
            <p v-else class="profile-section__empty">
              暂无可申请的类型：实名认证完成后可申请企业或工程师认证。
            </p>
          </UiCard>

          <UiCard v-if="activeTypeMeta" padding="lg" class="profile-section">
            <header class="profile-section__head">
              <h2 class="profile-section__title">申请{{ activeTypeMeta.label }}</h2>
            </header>

            <UiAlert
              v-if="applicationError"
              variant="error"
              title="提交失败"
              dismissible
              @close="applicationError = ''"
            >
              {{ applicationError }}
            </UiAlert>

            <form class="profile-form" novalidate @submit.prevent="submitApplication">
              <template v-if="applicationType === 'realname'">
                <UiInput
                  v-model="applicationFields.realName"
                  label="真实姓名"
                  name="application-real-name"
                  :maxlength="128"
                  :error="applicationFieldErrors.realName"
                  :disabled="submittingApplication"
                />
                <UiInput
                  v-model="applicationFields.idNumber"
                  label="身份证号"
                  name="application-id-number"
                  :maxlength="64"
                  :error="applicationFieldErrors.idNumber"
                  :disabled="submittingApplication"
                />
                <UiInput
                  v-model="applicationFields.contactPhone"
                  label="联系电话"
                  name="application-phone"
                  :maxlength="32"
                  :error="applicationFieldErrors.contactPhone"
                  :disabled="submittingApplication"
                />
              </template>

              <template v-else-if="applicationType === 'enterprise'">
                <UiInput
                  v-model="applicationFields.companyName"
                  label="公司名称"
                  name="application-company"
                  :maxlength="128"
                  :error="applicationFieldErrors.companyName"
                  :disabled="submittingApplication"
                />
                <UiInput
                  v-model="applicationFields.creditCode"
                  label="统一社会信用代码"
                  name="application-credit-code"
                  :maxlength="64"
                  :error="applicationFieldErrors.creditCode"
                  :disabled="submittingApplication"
                />
                <UiInput
                  v-model="applicationFields.contactName"
                  label="联系人"
                  name="application-contact-name"
                  :maxlength="64"
                  :error="applicationFieldErrors.contactName"
                  :disabled="submittingApplication"
                />
                <UiInput
                  v-model="applicationFields.contactPhone"
                  label="联系电话"
                  name="application-phone"
                  :maxlength="32"
                  :error="applicationFieldErrors.contactPhone"
                  :disabled="submittingApplication"
                />
              </template>

              <template v-else-if="applicationType === 'engineer'">
                <UiInput
                  v-model="applicationFields.skills"
                  label="技能"
                  name="application-skills"
                  placeholder="用逗号分隔，例如：Python, 数据标注"
                  :maxlength="255"
                  :error="applicationFieldErrors.skills"
                  :disabled="submittingApplication"
                />
                <UiInput
                  v-model="applicationFields.workYears"
                  label="工作年限"
                  name="application-work-years"
                  inputmode="numeric"
                  placeholder="0–60"
                  :error="applicationFieldErrors.workYears"
                  :disabled="submittingApplication"
                />
                <UiInput
                  v-model="applicationFields.contactPhone"
                  label="联系电话"
                  name="application-phone"
                  :maxlength="32"
                  :error="applicationFieldErrors.contactPhone"
                  :disabled="submittingApplication"
                />
              </template>

              <div class="profile-form__field profile-form__wide">
                <label class="profile-form__label" for="application-description">
                  {{ applicationType === 'realname' ? '备注' : '项目 / 资质说明' }}
                </label>
                <textarea
                  id="application-description"
                  v-model="applicationFields.description"
                  class="profile-form__textarea"
                  rows="3"
                  name="application-description"
                  :maxlength="2000"
                  :disabled="submittingApplication"
                  placeholder="补充说明，便于审核…"
                />
                <p
                  v-if="applicationFieldErrors.description"
                  class="profile-form__error"
                  role="alert"
                >
                  {{ applicationFieldErrors.description }}
                </p>
                <p v-else class="profile-form__help">
                  已输入 {{ applicationFields.description.length }} / 2000 字
                </p>
              </div>

              <div
                v-if="applicationType === 'engineer'"
                class="profile-form__field profile-form__wide"
              >
                <label class="profile-form__label" for="application-project">项目经历</label>
                <textarea
                  id="application-project"
                  v-model="applicationFields.projectExperience"
                  class="profile-form__textarea"
                  rows="3"
                  name="application-project"
                  :maxlength="2000"
                  :disabled="submittingApplication"
                  placeholder="描述代表性项目与交付结果…"
                />
                <p
                  v-if="applicationFieldErrors.projectExperience"
                  class="profile-form__error"
                  role="alert"
                >
                  {{ applicationFieldErrors.projectExperience }}
                </p>
              </div>

              <div class="profile-form__actions profile-form__wide">
                <UiButton type="submit" :loading="submittingApplication">提交申请</UiButton>
                <UiButton
                  variant="ghost"
                  :disabled="submittingApplication"
                  @click="closeApplication"
                >
                  取消
                </UiButton>
              </div>
            </form>
          </UiCard>

          <UiCard padding="lg" class="profile-section">
            <header class="profile-section__head">
              <h2 class="profile-section__title">我的认证申请</h2>
            </header>
            <p v-if="applications.length === 0" class="profile-section__empty">暂无认证申请。</p>
            <ul v-else class="application-list">
              <li v-for="item in applications" :key="item.id" class="application-item">
                <div class="application-item__head">
                  <span class="application-item__title">{{ item.typeLabel }}</span>
                  <UiChip :variant="item.statusTone">{{ item.statusLabel }}</UiChip>
                  <span class="application-item__time">提交于 {{ item.createdAtLabel }}</span>
                </div>
                <dl class="application-item__facts">
                  <div v-if="item.reviewer" class="application-item__fact">
                    <dt>审批人</dt>
                    <dd>
                      <span>{{ item.reviewer.displayName }}</span>
                      <CertificationMark :certifications="item.reviewer.certifications" />
                    </dd>
                  </div>
                  <div v-if="item.reviewedAtLabel" class="application-item__fact">
                    <dt>审批时间</dt>
                    <dd>{{ item.reviewedAtLabel }}</dd>
                  </div>
                  <div class="application-item__fact">
                    <dt>联系方式</dt>
                    <dd>{{ item.contactPhone || '—' }}</dd>
                  </div>
                </dl>
                <p v-if="item.reviewNote" class="application-item__note">
                  驳回理由：{{ item.reviewNote }}
                </p>
                <div v-if="item.status === 'rejected'" class="application-item__actions">
                  <UiButton
                    variant="secondary"
                    size="sm"
                    :data-reapply-type="item.type"
                    @click="openApplication(item.type)"
                  >
                    重新申请
                  </UiButton>
                </div>
              </li>
            </ul>
          </UiCard>
        </template>

        <UiCard v-else-if="activeTab === 'cooperation'" padding="lg" class="profile-section">
          <header class="profile-section__head">
            <h2 class="profile-section__title">合作记录</h2>
            <p class="profile-section__hint">已完成的合作订单与累计金额。</p>
          </header>

          <div class="cooperation-stats">
            <div class="cooperation-stat">
              <p class="cooperation-stat__value">{{ profile.cooperation.completedCount }}</p>
              <p class="cooperation-stat__label">完成单数</p>
            </div>
            <div class="cooperation-stat">
              <p class="cooperation-stat__value">{{ profile.cooperation.partnerCount }}</p>
              <p class="cooperation-stat__label">合作方</p>
            </div>
            <div class="cooperation-stat">
              <p class="cooperation-stat__value cooperation-stat__value--money">
                {{ profile.cooperation.totalAmountLabel }}
              </p>
              <p class="cooperation-stat__label">累计金额</p>
            </div>
          </div>

          <p v-if="profile.cooperation.records.length === 0" class="profile-section__empty">
            还没有已完成的合作订单。
          </p>
          <ul v-else class="cooperation-list">
            <li v-for="record in profile.cooperation.records" :key="record.orderId">
              <RouterLink
                class="cooperation-record"
                :to="{ name: 'fde-order-detail', params: { id: record.orderId } }"
              >
                <div class="cooperation-record__main">
                  <p class="cooperation-record__title">{{ record.title }}</p>
                  <p class="cooperation-record__meta">
                    {{ record.code }} · {{ record.roleLabel }} · 完成于
                    {{ record.completedAtLabel }}
                  </p>
                </div>
                <div class="cooperation-record__side">
                  <span class="cooperation-record__counterpart">
                    {{ record.counterpart?.displayName ?? '对方用户' }}
                  </span>
                  <CertificationMark :certifications="record.counterpart?.certifications ?? []" />
                  <span class="cooperation-record__amount">{{ record.priceLabel }}</span>
                </div>
              </RouterLink>
            </li>
          </ul>
        </UiCard>
      </template>
    </div>
  </ConsoleLayout>
</template>

<style scoped>
.profile-page {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-6);
  max-width: var(--hub-content-max);
}

.profile-page__link-button {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
  min-height: 44px;
  padding: 0 var(--primitive-space-5);
  color: var(--color-fg);
  background: var(--obsidian-surface-glass);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}

.profile-page__link-button:hover {
  border-color: var(--color-accent);
  text-decoration: none;
}

.profile-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-10) var(--primitive-space-6);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.profile-state--error {
  flex-direction: column;
  align-items: flex-start;
}

.profile-hero {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.profile-hero__identity {
  display: flex;
  align-items: flex-start;
  gap: var(--primitive-space-4);
}

.profile-hero__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  flex: none;
  color: var(--color-accent);
  background-color: var(--color-accent-subtle);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-pill);
  font-size: var(--font-size-body);
}

.profile-hero__copy {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-1);
  min-width: 0;
}

.profile-hero__name-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.profile-hero__name {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-medium);
}

.profile-hero__meta {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.profile-hero__bio {
  max-width: 62ch;
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.7;
}

.profile-hero__skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
}

.profile-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-1);
  padding: var(--primitive-space-1);
  align-self: flex-start;
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.profile-tabs__button {
  min-height: 34px;
  padding: 0 var(--primitive-space-4);
  color: var(--color-fg-muted);
  background: transparent;
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-small);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-medium);
  line-height: 1;
  white-space: nowrap;
}

.profile-tabs__button.is-active {
  color: var(--obsidian-gold-text);
  background-color: var(--color-accent-subtle);
  border-color: var(--color-accent-border);
}

.profile-section {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.profile-section__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--primitive-space-1) var(--primitive-space-3);
}

.profile-section__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.profile-section__hint,
.profile-section__empty {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.6;
}

.profile-cert-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
}

.profile-cert-types {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2);
}

.profile-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.profile-form__wide {
  grid-column: 1 / -1;
}

.profile-form__field {
  display: flex;
  flex-direction: column;
}

.profile-form__label {
  margin-bottom: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}

.profile-form__textarea {
  min-height: 96px;
  padding: var(--primitive-space-3) var(--primitive-space-4);
  color: var(--color-fg);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--obsidian-border-strong);
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  line-height: 1.6;
  resize: vertical;
}

.profile-form__textarea:focus-visible {
  border-color: var(--color-accent);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.profile-form__error {
  margin-top: var(--primitive-space-1);
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.profile-form__help {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.profile-form__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-3);
}

.application-list {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
}

.application-item {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
  padding: var(--primitive-space-4);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.application-item__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.application-item__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
}

.application-item__time {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.application-item__facts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--primitive-space-2) var(--primitive-space-6);
}

.application-item__fact {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
}

.application-item__fact dt {
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.application-item__fact dd {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-1);
  color: var(--color-fg);
  font-size: var(--font-size-small);
}

.application-item__note {
  color: var(--color-danger);
  font-size: var(--font-size-caption);
}

.application-item__actions {
  display: flex;
  gap: var(--primitive-space-2);
}

.cooperation-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.cooperation-stat {
  padding: var(--primitive-space-4);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.cooperation-stat__value {
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h2);
  font-variant-numeric: tabular-nums;
  font-weight: var(--font-weight-medium);
  line-height: 1.1;
}

.cooperation-stat__value--money {
  color: var(--obsidian-gold-text);
  font-size: var(--font-size-h3);
}

.cooperation-stat__label {
  margin-top: var(--primitive-space-1);
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.cooperation-list {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
}

.cooperation-record {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-3) var(--primitive-space-4);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.cooperation-record:hover {
  border-color: var(--color-accent-border);
  text-decoration: none;
}

.cooperation-record__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-medium);
}

.cooperation-record__meta {
  margin-top: 2px;
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
}

.cooperation-record__side {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-2);
}

.cooperation-record__counterpart {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
}

.cooperation-record__amount {
  color: var(--obsidian-gold-text);
  font-family: var(--font-family-heading);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 760px) {
  .profile-form,
  .cooperation-stats {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
