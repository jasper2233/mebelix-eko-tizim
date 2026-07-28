import { ORDER_STATUS_COLORS, ORDER_STATUS_LABELS } from "@/lib/mes"

export function StatusBadge({ status }: { status: string }) {
  const color = ORDER_STATUS_COLORS[status] ?? "var(--status-draft)"
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-2xs font-semibold tracking-wide"
      style={{
        // Matn to'qroq variantda: sof status rangi o'z 12% tinti ustida
        // 4.09-4.27:1 berardi (draft, review, completed AA dan o'tmasdi).
        // Nuqta esa sof rangda qoladi — u status identifikatori.
        color: `color-mix(in srgb, ${color} 78%, black)`,
        backgroundColor: `color-mix(in srgb, ${color} 12%, white)`,
      }}
    >
      <span
        className="size-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {ORDER_STATUS_LABELS[status] ?? status}
    </span>
  )
}
