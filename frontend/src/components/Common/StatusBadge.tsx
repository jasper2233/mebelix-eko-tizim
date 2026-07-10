import { ORDER_STATUS_COLORS, ORDER_STATUS_LABELS } from "@/lib/mes"

export function StatusBadge({ status }: { status: string }) {
  const color = ORDER_STATUS_COLORS[status] ?? "var(--status-draft)"
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide"
      style={{
        color,
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
