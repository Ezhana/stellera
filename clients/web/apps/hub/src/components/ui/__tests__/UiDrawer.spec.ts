import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'

import UiDrawer from '@/components/ui/UiDrawer.vue'

const mounted: VueWrapper[] = []

async function settle(): Promise<void> {
  await nextTick()
  await flushPromises()
  await nextTick()
}

function mountDrawer(props: Record<string, unknown> = {}, slots: Record<string, string> = {}) {
  const wrapper = mount(UiDrawer, {
    props: { modelValue: true, title: '编辑用户 · Luna Chen', ...props },
    slots,
  })
  mounted.push(wrapper)
  return wrapper
}

function panel(): HTMLElement | null {
  return document.body.querySelector<HTMLElement>('[role="dialog"]')
}

function overlay(): HTMLElement | null {
  return document.body.querySelector<HTMLElement>('.ui-drawer')
}

afterEach(() => {
  for (const wrapper of mounted.splice(0)) wrapper.unmount()
  document.body.innerHTML = ''
  document.body.style.overflow = ''
})

describe('UiDrawer', () => {
  it('renders nothing while closed and teleports the panel with title, description and footer', async () => {
    const wrapper = mountDrawer(
      { modelValue: false, description: '编辑用户资料与余额', size: 'lg' },
      {
        default: '<p class="drawer-body">内容</p>',
        footer: '<button class="drawer-foot">关闭</button>',
      },
    )

    await settle()
    expect(panel()).toBeNull()

    await wrapper.setProps({ modelValue: true })
    await settle()

    const el = panel()
    expect(el).not.toBeNull()
    expect(el?.getAttribute('aria-modal')).toBe('true')
    expect(el?.getAttribute('aria-labelledby')).toBeTruthy()
    expect(document.getElementById(el!.getAttribute('aria-labelledby')!)?.textContent).toBe(
      '编辑用户 · Luna Chen',
    )
    expect(el?.classList.contains('ui-drawer__panel--lg')).toBe(true)
    expect(document.body.textContent).toContain('编辑用户资料与余额')
    expect(document.body.querySelector('.drawer-body')).not.toBeNull()
    expect(document.body.querySelector('.drawer-foot')).not.toBeNull()
  })

  it('emits v-model updates when the close button is clicked and hides on prop change', async () => {
    const wrapper = mountDrawer()
    await settle()

    document.body.querySelector<HTMLButtonElement>('[aria-label="关闭抽屉"]')!.click()
    await settle()

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])

    await wrapper.setProps({ modelValue: false })
    await settle()
    expect(panel()).toBeNull()
  })

  it('closes on Escape only when closeOnEscape is enabled', async () => {
    const wrapper = mountDrawer()
    await settle()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await settle()
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])

    await wrapper.setProps({ modelValue: false })
    await settle()

    const persistent = mountDrawer({ closeOnEscape: false })
    await settle()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await settle()
    expect(persistent.emitted('update:modelValue')).toBeUndefined()
  })

  it('closes on overlay click only when closeOnOverlay is enabled', async () => {
    const wrapper = mountDrawer()
    await settle()

    panel()!.click()
    await settle()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    overlay()!.click()
    await settle()
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])

    await wrapper.setProps({ modelValue: false })
    await settle()

    const persistent = mountDrawer({ closeOnOverlay: false })
    await settle()
    overlay()!.click()
    await settle()
    expect(persistent.emitted('update:modelValue')).toBeUndefined()
  })

  it('locks body scrolling while open and restores the previous value', async () => {
    document.body.style.overflow = 'scroll'
    const wrapper = mountDrawer({ modelValue: false })
    await settle()
    expect(document.body.style.overflow).toBe('scroll')

    await wrapper.setProps({ modelValue: true })
    await settle()
    expect(document.body.style.overflow).toBe('hidden')

    await wrapper.setProps({ modelValue: false })
    await settle()
    expect(document.body.style.overflow).toBe('scroll')
  })

  it('moves focus into the drawer and restores it on close', async () => {
    const trigger = document.createElement('button')
    trigger.textContent = '打开抽屉'
    document.body.appendChild(trigger)
    trigger.focus()

    const wrapper = mountDrawer()
    await settle()

    const el = panel()
    expect(el?.contains(document.activeElement)).toBe(true)

    await wrapper.setProps({ modelValue: false })
    await settle()
    expect(document.activeElement).toBe(trigger)
  })
})
