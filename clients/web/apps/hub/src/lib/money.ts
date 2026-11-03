/** Shared money/date formatting for page models; all amounts travel as integer cents. */

/** `¥86,000` / `¥123.45` — grouped yuan with tabular-friendly output (no locale surprises). */
export function formatCents(cents: number): string {
  const safe = Number.isFinite(cents) ? Math.round(cents) : 0
  const sign = safe < 0 ? '-' : ''
  const absolute = Math.abs(safe)
  const yuan = Math.floor(absolute / 100)
  const fen = absolute % 100
  const grouped = String(yuan).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const fraction = fen === 0 ? '' : `.${String(fen).padStart(2, '0')}`
  return `${sign}¥${grouped}${fraction}`
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

/**
 * `11-01 14:20` (other day) or `今天 14:20` (same local day).
 *
 * Uses the browser's local timezone; `now` is injectable so tests stay deterministic.
 */
export function formatDateTimeLabel(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  const time = `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  if (sameDay) return `今天 ${time}`

  return `${pad2(date.getMonth() + 1)}-${pad2(date.getDate())} ${time}`
}
