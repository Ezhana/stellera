<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import UiIcon from '@/components/ui/UiIcon.vue'
import ConsoleLayout from '@/layouts/ConsoleLayout.vue'
import type { IconName } from '@/models'
import { useAuthStore } from '@/stores/auth'

interface IntroSlide {
  key: string
  tone: 'deploy' | 'escrow' | 'trail'
  eyebrow: string
  title: string
  lead: string
  points: string[]
}

const slides: readonly IntroSlide[] = [
  {
    key: 'deploy',
    tone: 'deploy',
    eyebrow: 'FORWARD DEPLOYED ENGINEER',
    title: '让 AI 真正落到业务现场',
    lead: '企业发布真实需求，认证 FDE 工程师接单驻场交付。平台托管资金、全程留痕，直到验收完成。',
    points: [
      '企业发布需求，明确行业、周期与预算',
      '工程师接单，按日提交工作日志',
      '平台验收结算，交付可追溯',
    ],
  },
  {
    key: 'escrow',
    tone: 'escrow',
    eyebrow: 'THIRD-PARTY ESCROW',
    title: '资金先托管，交付才结算',
    lead: '平台作为独立的第三方收取企业资金并托管，只有验收通过后才结算给工程师——双方都不必承担对方的违约风险。',
    points: [
      '企业资金进入平台托管账户',
      '里程碑与验收结果决定释放节奏',
      '异常订单可取消并退回资金',
    ],
  },
  {
    key: 'trail',
    tone: 'trail',
    eyebrow: 'AUDITABLE DELIVERY',
    title: '每一次交付，都有痕迹',
    lead: '工程师按日提交工作日志、里程碑与交付物，沉淀在订单里。平台可介入协调，争议有据可依。',
    points: ['工作日志与工时全程留痕', '交付进度实时同步到订单大厅', '验收口径明确，结果可复核'],
  },
]

interface FlowStep {
  title: string
  description: string
  icon: IconName
}

const steps: readonly FlowStep[] = [
  {
    title: '企业发布需求',
    description:
      '明确任务、行业、交付周期与预算，资金进入平台托管账户；需求实时进入订单大厅，等待工程师接单。',
    icon: 'building',
  },
  {
    title: '工程师接单交付',
    description:
      '认证 FDE 工程师接单，按日提交工作日志、里程碑与交付物；交付过程与工时全部沉淀在订单中。',
    icon: 'wrench',
  },
  {
    title: '平台验收结算',
    description:
      '平台按验收口径确认交付结果并释放托管资金；异常订单可取消并退回资金，双方权益都有保障。',
    icon: 'shield',
  },
]

interface Guarantee {
  icon: IconName
  title: string
  description: string
}

const guarantees: readonly Guarantee[] = [
  {
    icon: 'coins',
    title: '第三方资金托管',
    description:
      '企业资金先进入平台托管，验收通过后才结算给工程师。用机制替代信任，双方不必承担对方的违约风险。',
  },
  {
    icon: 'logs',
    title: '过程可追溯',
    description:
      '日志、工时、里程碑与交付物沉淀在订单中。平台可介入协调，争议有据可依，交付质量可复核。',
  },
  {
    icon: 'target',
    title: '交付有标准',
    description: '以交付周期与验收口径约束履约，订单状态实时同步。异常订单可取消并退回托管资金。',
  },
]

const roles: readonly { icon: IconName; title: string; description: string }[] = [
  { icon: 'building', title: '企业', description: '发布需求、托管资金、验收交付结果' },
  { icon: 'shield', title: '平台', description: '托管资金、监督过程、协调交付争议' },
  { icon: 'wrench', title: 'FDE 工程师', description: '接单交付、提交日志、获取结算' },
]

const auth = useAuthStore()
const viewer = computed(() => auth.viewer)

const activeIndex = ref(0)
const paused = ref(false)
const slide = computed(() => slides[activeIndex.value] ?? slides[0]!)

let timer: ReturnType<typeof setInterval> | undefined

function stopAutoPlay(): void {
  if (timer !== undefined) {
    clearInterval(timer)
    timer = undefined
  }
}

function startAutoPlay(): void {
  stopAutoPlay()
  if (paused.value || prefersReducedMotion()) return
  timer = setInterval(() => go(activeIndex.value + 1), 7000)
}

function go(index: number): void {
  const total = slides.length
  activeIndex.value = ((index % total) + total) % total
}

function next(): void {
  go(activeIndex.value + 1)
}

function previous(): void {
  go(activeIndex.value - 1)
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

onMounted(startAutoPlay)
onUnmounted(stopAutoPlay)

watch(paused, (value) => {
  if (value) stopAutoPlay()
  else startAutoPlay()
})
</script>

<template>
  <ConsoleLayout v-if="viewer" :viewer="viewer">
    <div class="intro">
      <section
        class="intro-hero"
        :class="`intro-hero--${slide.tone}`"
        aria-roledescription="carousel"
        aria-label="平台简介"
        tabindex="0"
        @mouseenter="paused = true"
        @mouseleave="paused = false"
        @focusin="paused = true"
        @focusout="paused = false"
        @keydown.left.prevent="previous"
        @keydown.right.prevent="next"
      >
        <div class="intro-hero__grid" aria-hidden="true" />
        <div class="intro-hero__glow" aria-hidden="true" />

        <div class="intro-hero__frame">
          <div
            class="intro-hero__copy"
            role="group"
            aria-roledescription="slide"
            :aria-label="`${activeIndex + 1} / ${slides.length}`"
          >
            <Transition name="intro-slide" mode="out-in">
              <div :key="slide.key" class="intro-hero__slide">
                <p class="hub-eyebrow">{{ slide.eyebrow }}</p>
                <h1 class="intro-hero__title">{{ slide.title }}</h1>
                <p class="intro-hero__lead">{{ slide.lead }}</p>

                <div class="intro-hero__actions">
                  <RouterLink :to="{ name: 'fde-hall' }" class="intro-hero__cta">
                    进入订单大厅
                    <UiIcon name="arrow-right" :size="18" />
                  </RouterLink>
                  <span class="intro-hero__action-note">实时订单 · 平台托管</span>
                </div>
              </div>
            </Transition>
          </div>

          <aside class="intro-hero__panel" aria-label="平台机制">
            <p class="intro-hero__panel-eyebrow">MECHANISM / 平台机制</p>
            <ul class="intro-hero__points">
              <li v-for="(point, index) in slide.points" :key="point">
                <span class="intro-hero__point-index" aria-hidden="true">
                  {{ String(index + 1).padStart(2, '0') }}
                </span>
                <span>{{ point }}</span>
              </li>
            </ul>
            <p class="intro-hero__panel-note">资金托管 · 过程留痕 · 验收结算</p>
          </aside>
        </div>

        <div class="intro-hero__controls">
          <div class="intro-hero__arrows">
            <button type="button" class="intro-hero__arrow" aria-label="上一张" @click="previous">
              <UiIcon name="arrow-left" :size="18" />
            </button>
            <button type="button" class="intro-hero__arrow" aria-label="下一张" @click="next">
              <UiIcon name="arrow-right" :size="18" />
            </button>
          </div>

          <div class="intro-hero__dots" role="tablist" aria-label="选择轮播内容">
            <button
              v-for="(item, index) in slides"
              :key="item.key"
              type="button"
              role="tab"
              class="intro-hero__dot"
              :class="{ 'is-active': index === activeIndex }"
              :aria-selected="index === activeIndex"
              :aria-label="`第 ${index + 1} 张：${item.title}`"
              @click="go(index)"
            />
          </div>

          <p class="intro-hero__counter">
            <span>{{ String(activeIndex + 1).padStart(2, '0') }}</span>
            <span aria-hidden="true"> / </span>
            <span class="intro-hero__counter-total">{{
              String(slides.length).padStart(2, '0')
            }}</span>
          </p>
        </div>

        <div
          v-if="!paused && !prefersReducedMotion()"
          :key="activeIndex"
          class="intro-hero__progress"
          aria-hidden="true"
        />
      </section>

      <section class="intro-narrative" aria-labelledby="intro-narrative-title">
        <div class="intro-narrative__copy">
          <p class="hub-eyebrow">WHY FDE</p>
          <h2 id="intro-narrative-title" class="intro-narrative__title">
            AI 落地的最后一公里，需要站在现场的人
          </h2>
          <p class="intro-narrative__paragraph">
            模型能力正在快速商品化，真正决定 AI
            项目成败的，是业务现场的理解、数据打通、流程改造与持续运营。 FDE（Forward Deployed
            Engineer，前沿部署工程师）把工程能力带到客户现场，用可验证的交付结果替代空泛的方案。
          </p>
          <p class="intro-narrative__paragraph">
            STELLERA
            把这一过程放进可托管、可留痕的订单里：企业不必先信任一个陌生人，工程师也不必担心回款。
            平台用机制保证每一次交付——从需求发布，到接单、日志、验收与结算。
          </p>
          <blockquote class="intro-narrative__quote">以交付结果为准，而不是以方案为准。</blockquote>
        </div>

        <ul class="intro-narrative__roles" aria-label="平台三方角色">
          <li v-for="role in roles" :key="role.title" class="intro-role">
            <span class="intro-role__icon">
              <UiIcon :name="role.icon" :size="20" />
            </span>
            <div class="intro-role__copy">
              <p class="intro-role__title">{{ role.title }}</p>
              <p class="intro-role__description">{{ role.description }}</p>
            </div>
          </li>
        </ul>
      </section>

      <section class="intro-steps" aria-labelledby="intro-steps-title">
        <header class="intro-section-head">
          <div>
            <p class="hub-eyebrow">DELIVERY FLOW</p>
            <h2 id="intro-steps-title" class="intro-section-title">一条订单，完成一次可信交付</h2>
          </div>
          <p class="intro-section-note">企业发布 → 工程师接单 → 平台保障交付</p>
        </header>

        <ol class="intro-steps__list">
          <li v-for="(step, index) in steps" :key="step.title" class="intro-step">
            <div class="intro-step__head">
              <span class="intro-step__index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="intro-step__icon">
                <UiIcon :name="step.icon" :size="22" />
              </span>
            </div>
            <h3 class="intro-step__title">{{ step.title }}</h3>
            <p class="intro-step__description">{{ step.description }}</p>
          </li>
        </ol>
      </section>

      <section class="intro-guarantees" aria-labelledby="intro-guarantees-title">
        <header class="intro-section-head">
          <div>
            <p class="hub-eyebrow">PLATFORM GUARANTEE</p>
            <h2 id="intro-guarantees-title" class="intro-section-title">
              平台作为第三方，保障每一笔交易
            </h2>
          </div>
        </header>

        <div class="intro-guarantees__grid">
          <article v-for="item in guarantees" :key="item.title" class="intro-guarantee">
            <span class="intro-guarantee__icon">
              <UiIcon :name="item.icon" :size="22" />
            </span>
            <h3 class="intro-guarantee__title">{{ item.title }}</h3>
            <p class="intro-guarantee__description">{{ item.description }}</p>
          </article>
        </div>
      </section>

      <section class="intro-cta" aria-labelledby="intro-cta-title">
        <div class="intro-cta__copy">
          <p class="hub-eyebrow">LIVE ORDER HALL</p>
          <h2 id="intro-cta-title" class="intro-cta__title">从一条真实需求开始</h2>
          <p class="intro-cta__description">
            订单大厅实时展示任务、行业、交付周期、价格与状态。找到正在招募的 FDE
            交付机会，或发布你的下一条需求。
          </p>
        </div>
        <RouterLink :to="{ name: 'fde-hall' }" class="intro-cta__link">
          浏览实时订单
          <UiIcon name="arrow-right" :size="18" />
        </RouterLink>
      </section>
    </div>
  </ConsoleLayout>

  <div v-else class="intro-loading">正在加载平台简介…</div>
</template>

<style scoped>
.intro {
  display: flex;
  flex-direction: column;
  gap: clamp(3rem, 5vw, 4.5rem);
  max-width: var(--hub-content-max);
  margin: 0 auto;
}

/* ---------- Hero carousel ---------- */
.intro-hero {
  --intro-glow-x: 78%;
  --intro-glow-y: 18%;

  position: relative;
  display: flex;
  flex-direction: column;
  gap: clamp(1.5rem, 3vw, 2.5rem);
  min-height: 30rem;
  padding: clamp(1.75rem, 4vw, 3.5rem);
  overflow: hidden;
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-panel);
  box-shadow: var(--obsidian-panel-highlight);
}

.intro-hero--escrow {
  --intro-glow-x: 18%;
  --intro-glow-y: 82%;
}

.intro-hero--trail {
  --intro-glow-x: 82%;
  --intro-glow-y: 78%;
}

.intro-hero__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(
      color-mix(in srgb, var(--color-fg) 4%, transparent) var(--border-width-default),
      transparent var(--border-width-default)
    ),
    linear-gradient(
      90deg,
      color-mix(in srgb, var(--color-fg) 4%, transparent) var(--border-width-default),
      transparent var(--border-width-default)
    );
  background-size: 72px 72px;
  mask-image: linear-gradient(to bottom, transparent, black 18%, black 82%, transparent);
  pointer-events: none;
}

.intro-hero__glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at var(--intro-glow-x) var(--intro-glow-y),
    color-mix(in srgb, var(--color-accent) 22%, transparent),
    transparent 58%
  );
  opacity: 0.9;
  pointer-events: none;
  transition: background var(--motion-duration-normal) var(--motion-easing-standard);
}

.intro-hero__frame {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 0.9fr);
  align-items: start;
  gap: clamp(2rem, 4vw, 3.5rem);
}

.intro-hero__copy {
  min-height: 17rem;
}

.intro-hero__slide {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-5);
}

.intro-hero__title {
  max-width: 18ch;
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: clamp(2.35rem, 1.7rem + 2.6vw, 3.7rem);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.035em;
  line-height: 1.08;
  text-wrap: balance;
}

.intro-hero__lead {
  max-width: 54ch;
  color: var(--color-fg-muted);
  font-size: var(--font-size-body-lg);
  line-height: 1.75;
}

.intro-hero__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--primitive-space-4);
  margin-top: var(--primitive-space-2);
}

/* The screen's single gold focal point. */
.intro-hero__cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--primitive-space-2);
  min-height: 46px;
  padding: 0 var(--primitive-space-6);
  color: var(--color-on-accent);
  background: var(--obsidian-gold-gradient);
  border: var(--border-width-default) solid transparent;
  border-radius: var(--radius-control);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-strong);
  letter-spacing: 0.01em;
  text-decoration: none;
  box-shadow: var(--obsidian-panel-highlight), var(--shadow-sm);
  transition:
    filter var(--motion-duration-fast) var(--motion-easing-standard),
    transform var(--motion-duration-fast) var(--motion-easing-standard);
}

.intro-hero__cta:hover {
  filter: brightness(1.06);
  text-decoration: none;
  transform: translateY(-1px);
}

.intro-hero__action-note {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  letter-spacing: 0.02em;
}

.intro-hero__panel {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
  padding: var(--primitive-space-6);
  background: color-mix(in srgb, var(--color-bg) 62%, transparent);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  backdrop-filter: blur(2px);
}

.intro-hero__panel-eyebrow {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  font-weight: var(--font-weight-strong);
  letter-spacing: var(--font-letter-spacing-label);
}

.intro-hero__points {
  display: flex;
  flex-direction: column;
}

.intro-hero__points li {
  display: flex;
  align-items: baseline;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-3) 0;
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.55;
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.intro-hero__points li:first-child {
  border-top: 0;
  padding-top: 0;
}

.intro-hero__point-index {
  flex: none;
  color: var(--color-accent);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-small);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
}

.intro-hero__panel-note {
  margin-top: auto;
  padding-top: var(--primitive-space-3);
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  letter-spacing: 0.04em;
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.intro-hero__controls {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-4);
  padding-top: var(--primitive-space-4);
  border-top: var(--border-width-default) solid var(--color-border-subtle);
}

.intro-hero__arrows {
  display: flex;
  gap: var(--primitive-space-2);
}

.intro-hero__arrow {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  color: var(--color-fg-muted);
  background: transparent;
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-control);
  transition:
    color var(--motion-duration-fast) var(--motion-easing-standard),
    border-color var(--motion-duration-fast) var(--motion-easing-standard);
}

.intro-hero__arrow:hover {
  color: var(--color-accent-hover);
  border-color: var(--color-accent-border);
}

.intro-hero__dots {
  display: flex;
  align-items: center;
  gap: var(--primitive-space-2);
}

.intro-hero__dot {
  width: 26px;
  height: 3px;
  padding: 0;
  background-color: var(--color-border);
  border: 0;
  border-radius: var(--radius-pill);
  transition:
    width var(--motion-duration-normal) var(--motion-easing-standard),
    background-color var(--motion-duration-normal) var(--motion-easing-standard);
}

.intro-hero__dot:hover {
  background-color: var(--color-fg-muted);
}

.intro-hero__dot.is-active {
  width: 44px;
  background-color: var(--color-accent);
}

.intro-hero__counter {
  color: var(--obsidian-tertiary-text);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-small);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.08em;
}

.intro-hero__counter span:first-child {
  color: var(--color-accent-hover);
}

.intro-hero__counter-total {
  opacity: 0.6;
}

.intro-hero__progress {
  position: absolute;
  inset: auto 0 0;
  height: 2px;
  background: var(--color-accent);
  transform-origin: left center;
  animation: intro-progress 7s linear forwards;
}

@keyframes intro-progress {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

.intro-slide-enter-active,
.intro-slide-leave-active {
  transition:
    opacity var(--motion-duration-normal) var(--motion-easing-standard),
    transform var(--motion-duration-normal) var(--motion-easing-standard);
}

.intro-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.intro-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ---------- Narrative ---------- */
.intro-narrative {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 0.7fr);
  align-items: start;
  gap: clamp(2rem, 4vw, 4rem);
  padding-top: clamp(1rem, 2vw, 2rem);
}

.intro-narrative__copy {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-4);
}

.intro-narrative__title {
  max-width: 24ch;
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: clamp(1.7rem, 1.35rem + 1.3vw, 2.45rem);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.025em;
  line-height: 1.2;
  text-wrap: balance;
}

.intro-narrative__paragraph {
  max-width: 62ch;
  color: var(--color-fg-muted);
  font-size: var(--font-size-body);
  line-height: 1.85;
}

.intro-narrative__quote {
  margin: var(--primitive-space-2) 0 0;
  padding: var(--primitive-space-1) 0 var(--primitive-space-1) var(--primitive-space-5);
  color: var(--obsidian-gold-text);
  border-left: 2px solid var(--color-accent);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h4);
  font-style: italic;
  line-height: 1.5;
}

.intro-narrative__roles {
  display: flex;
  flex-direction: column;
  border-top: var(--border-width-default) solid var(--color-border);
}

.intro-role {
  display: flex;
  align-items: flex-start;
  gap: var(--primitive-space-4);
  padding: var(--primitive-space-4) 0;
  border-bottom: var(--border-width-default) solid var(--color-border-subtle);
}

.intro-role__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex: none;
  color: var(--color-accent);
  background-color: var(--color-accent-subtle);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-control);
}

.intro-role__title {
  color: var(--color-fg-strong);
  font-size: var(--font-size-small);
  font-weight: var(--font-weight-strong);
}

.intro-role__description {
  margin-top: 2px;
  color: var(--color-fg-muted);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}

/* ---------- Shared section head ---------- */
.intro-section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--primitive-space-3);
  margin-bottom: var(--primitive-space-6);
}

.intro-section-title {
  margin-top: var(--primitive-space-2);
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: clamp(1.5rem, 1.25rem + 1vw, 2.1rem);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
  text-wrap: balance;
}

.intro-section-note {
  color: var(--obsidian-tertiary-text);
  font-size: var(--font-size-caption);
  letter-spacing: 0.02em;
}

/* ---------- Steps ---------- */
.intro-steps__list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.intro-step {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-6);
  background-color: var(--color-surface);
  border: var(--border-width-default) solid var(--color-border);
  border-radius: var(--radius-surface);
  box-shadow: var(--obsidian-panel-highlight);
}

.intro-step__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.intro-step__index {
  color: var(--color-accent);
  font-family: var(--font-family-heading);
  font-size: var(--font-size-h3);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  line-height: 1;
}

.intro-step__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  color: var(--color-fg-muted);
  background: var(--obsidian-surface-glass);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-control);
}

.intro-step__title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
  letter-spacing: -0.01em;
}

.intro-step__description {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.75;
}

/* ---------- Guarantees ---------- */
.intro-guarantees__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--primitive-space-4);
}

.intro-guarantee {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-3);
  padding: var(--primitive-space-6);
  background-color: var(--color-bg-subtle);
  border: var(--border-width-default) solid var(--color-border-subtle);
  border-radius: var(--radius-surface);
}

.intro-guarantee__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  color: var(--color-accent);
  background-color: var(--color-accent-subtle);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-pill);
}

.intro-guarantee__title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-sans);
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-strong);
}

.intro-guarantee__description {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.75;
}

/* ---------- CTA ---------- */
.intro-cta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--primitive-space-6);
  padding: clamp(1.75rem, 3.5vw, 3rem);
  background-color: var(--color-surface-elevated);
  border: var(--border-width-default) solid var(--color-accent-border);
  border-radius: var(--radius-panel);
  box-shadow: var(--obsidian-panel-highlight), var(--shadow-lg);
}

.intro-cta__copy {
  display: flex;
  flex-direction: column;
  gap: var(--primitive-space-2);
  max-width: 52ch;
}

.intro-cta__title {
  color: var(--color-fg-strong);
  font-family: var(--font-family-heading);
  font-size: clamp(1.6rem, 1.3rem + 1.1vw, 2.2rem);
  font-weight: var(--font-weight-medium);
  letter-spacing: -0.02em;
}

.intro-cta__description {
  color: var(--color-fg-muted);
  font-size: var(--font-size-small);
  line-height: 1.75;
}

.intro-cta__link {
  display: inline-flex;
  align-items: center;
  gap: var(--primitive-space-2);
  color: var(--color-accent-hover);
  font-size: var(--font-size-body);
  font-weight: var(--font-weight-strong);
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.intro-cta__link:hover {
  color: var(--color-accent);
}

.intro-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  color: var(--color-fg-muted);
}

@media (max-width: 1024px) {
  .intro-hero__frame {
    grid-template-columns: minmax(0, 1fr);
  }

  .intro-hero__copy {
    min-height: 0;
  }

  .intro-hero__panel {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    align-items: start;
    gap: var(--primitive-space-4);
  }

  .intro-hero__panel-eyebrow,
  .intro-hero__panel-note {
    grid-column: 1 / -1;
  }

  .intro-narrative {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 820px) {
  .intro-steps__list,
  .intro-guarantees__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .intro-hero__panel {
    grid-template-columns: minmax(0, 1fr);
  }

  .intro-hero__controls {
    flex-wrap: wrap;
  }
}

@media (max-width: 560px) {
  .intro-hero {
    padding: var(--primitive-space-5);
  }

  .intro-hero__title {
    font-size: clamp(2rem, 1.6rem + 2vw, 2.6rem);
  }
}
</style>
