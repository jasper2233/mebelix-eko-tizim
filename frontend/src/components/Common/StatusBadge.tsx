import { chipColors, ORDER_STATUS_COLORS, ORDER_STATUS_LABELS } from "@/lib/mes"

export function StatusBadge({ status }: { status: string }) {
  const color = ORDER_STATUS_COLORS[status] ?? "var(--status-draft)"
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-2xs font-semibold tracking-wide"
      // Nuqta sof rangda qoladi — u status identifikatori; matn/fon nisbati
      // `chipColors` da (WCAG AA).
      style={chipColors(color, 12)}
    >
      <span
        className="size-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {ORDER_STATUS_LABELS[status] ?? status}
    </span>
  )
}
