import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'

import UiModal from '@/components/ui/UiModal.vue'

const mounted: VueWrapper[] = []

async function settle(): Promise<void> {
  await nextTick()
  await flushPromises()
  await nextTick()
}

function mountModal(props: Record<string, unknown> = {}, slots: Record<string, string> = {}) {
  const wrapper = mount(UiModal, {
    props: { modelValue: true, title: '申请接单', ...props },
    slots,
  })
  mounted.push(wrapper)
  return wrapper
}

function dialog(): HTMLElement | null {
  return document.body.querySelector<HTMLElement>('[role="dialog"]')
}

function overlay(): HTMLElement | null {
  return document.body.querySelector<HTMLElement>('.ui-modal')
}

afterEach(() => {
  for (const wrapper of mounted.splice(0)) wrapper.unmount()
  document.body.innerHTML = ''
  document.body.style.overflow = ''
})

describe('UiModal', () => {
  it('renders nothing while closed and teleports the dialog when opened', async () => {
    const wrapper = mountModal(
      { modelValue: false, description: '提交后等待发布者审批' },
      {
        default: '<p class="modal-body">内容</p>',
        footer: '<button class="modal-foot">确认</button>',
      },
    )

    await settle()
    expect(dialog()).toBeNull()

    await wrapper.setProps({ modelValue: true })
    await settle()

    const el = dialog()
    expect(el).not.toBeNull()
    expect(el?.getAttribute('aria-modal')).toBe('true')
    expect(el?.getAttribute('aria-labelledby')).toBeTruthy()
    expect(document.getElementById(el!.getAttribute('aria-labelledby')!)?.textContent).toBe(
      '申请接单',
    )
    expect(document.body.textContent).toContain('提交后等待发布者审批')
    expect(document.body.querySelector('.modal-body')).not.toBeNull()
    expect(document.body.querySelector('.modal-foot')).not.toBeNull()
  })

  it('emits v-model updates when the close button is clicked and hides on prop change', async () => {
    const wrapper = mountModal()
    await settle()

    document.body.querySelector<HTMLButtonElement>('[aria-label="关闭弹窗"]')!.click()
    await settle()

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])

    await wrapper.setProps({ modelValue: false })
    await settle()
    expect(dialog()).toBeNull()
  })

  it('closes on Escape only when closeOnEscape is enabled', async () => {
    const wrapper = mountModal()
    await settle()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await settle()
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])

    await wrapper.setProps({ modelValue: false })
    await settle()

    const persistent = mountModal({ closeOnEscape: false })
    await settle()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await settle()
    expect(persistent.emitted('update:modelValue')).toBeUndefined()
  })

  it('closes on overlay click only when closeOnOverlay is enabled and ignores panel clicks', async () => {
    const wrapper = mountModal()
    await settle()

    dialog()!.click()
    await settle()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    overlay()!.click()
    await settle()
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])

    await wrapper.setProps({ modelValue: false })
    await settle()

    const persistent = mountModal({ closeOnOverlay: false })
    await settle()
    overlay()!.click()
    await settle()
    expect(persistent.emitted('update:modelValue')).toBeUndefined()
  })

  it('locks body scrolling while open and restores the previous value', async () => {
    document.body.style.overflow = 'scroll'
    const wrapper = mountModal({ modelValue: false })
    await settle()
    expect(document.body.style.overflow).toBe('scroll')

    await wrapper.setProps({ modelValue: true })
    await settle()
    expect(document.body.style.overflow).toBe('hidden')

    await wrapper.setProps({ modelValue: false })
    await settle()
    expect(document.body.style.overflow).toBe('scroll')
  })

  it('moves focus into the dialog and restores it on close', async () => {
    const trigger = document.createElement('button')
    trigger.textContent = '打开弹窗'
    document.body.appendChild(trigger)
    trigger.focus()

    const wrapper = mountModal()
    await settle()

    const el = dialog()
    expect(el?.contains(document.activeElement)).toBe(true)

    await wrapper.setProps({ modelValue: false })
    await settle()
    expect(document.activeElement).toBe(trigger)
  })
})
