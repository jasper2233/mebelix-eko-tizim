// Signature element: the 6-stage production pipeline (TZ 4.4) rendered as connected
// stage cells — the same visual grammar on dashboard, order rows, matrix and TABLO.

import { POST_COLORS } from "@/lib/mes"
import { cn } from "@/lib/utils"

export type StageCell = {
  code: string
  done: number
  total: number
}

export function StagePipeline({
  stages,
  compact = false,
}: {
  stages: StageCell[]
  compact?: boolean
}) {
  if (!stages.length)
    return <span className="text-xs text-muted-foreground">—</span>
  return (
    <div className="flex items-center">
      {stages.map((s, i) => {
        const color = POST_COLORS[s.code] ?? "var(--status-draft)"
        const pct =
          s.total > 0 ? Math.min(100, Math.round((s.done / s.total) * 100)) : 0
        const complete = s.total > 0 && s.done >= s.total
        return (
          <div key={s.code} className="flex items-center">
            {i > 0 && <div className="h-px w-1.5 bg-border" />}
            <div
              className={cn(
                "relative overflow-hidden rounded",
                compact ? "h-5 w-9" : "h-6 w-12",
              )}
              style={{
                backgroundColor: `color-mix(in srgb, ${color} 14%, white)`,
              }}
              title={`${s.code}: ${s.done}/${s.total} (${pct}%)`}
            >
              <div
                className="absolute inset-y-0 left-0 transition-all duration-500"
                style={{
                  width: `${pct}%`,
                  backgroundColor: `color-mix(in srgb, ${color} 38%, white)`,
                }}
              />
              <span
                className="num relative flex h-full items-center justify-center text-[9px] font-bold"
                style={{ color }}
              >
                {complete
                  ? "✓"
                  : compact
                    ? s.code.slice(0, 2)
                    : `${s.done}/${s.total}`}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
