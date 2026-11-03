import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

interface DialogOverlayOptions {
  closeOnEscape: () => boolean
  onClose: () => void
}

/**
 * Shared dialog behaviour for `UiModal` and `UiDrawer`: body scroll lock,
 * initial focus, focus restoration on close and the optional ESC handler.
 */
export function useDialogOverlay(
  open: Ref<boolean>,
  panelRef: Ref<HTMLElement | null>,
  { closeOnEscape, onClose }: DialogOverlayOptions,
): void {
  let restoreOverflow = ''
  let scrollLocked = false
  let previouslyFocused: HTMLElement | null = null

  function lockScroll(): void {
    if (scrollLocked) return
    restoreOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    scrollLocked = true
  }

  function unlockScroll(): void {
    if (!scrollLocked) return
    document.body.style.overflow = restoreOverflow
    scrollLocked = false
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Escape' || !closeOnEscape()) return
    event.stopPropagation()
    onClose()
  }

  function restoreFocus(): void {
    const target = previouslyFocused
    previouslyFocused = null
    target?.focus()
  }

  watch(
    open,
    async (isOpen) => {
      if (isOpen) {
        previouslyFocused =
          document.activeElement instanceof HTMLElement ? document.activeElement : null
        lockScroll()
        document.addEventListener('keydown', handleKeydown)
        await nextTick()
        const panel = panelRef.value
        const initial = panel?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR) ?? panel
        initial?.focus()
        return
      }

      unlockScroll()
      document.removeEventListener('keydown', handleKeydown)
      restoreFocus()
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    unlockScroll()
    document.removeEventListener('keydown', handleKeydown)
    restoreFocus()
  })
}
