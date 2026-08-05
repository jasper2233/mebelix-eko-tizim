import { chipColors, POST_COLORS } from "@/lib/mes"
import { cn } from "@/lib/utils"

/**
 * Bosqich (post) kodi chipi — ARRA, KROMKA, ...
 *
 * Rang formulasi (WCAG AA asosi) `chipColors` da — 12% tint fonda sof post
 * rangi AA dan o'tmasdi (ARRA, STOLYARKA), izohi lib/mes.ts da.
 *
 * Avval employees.tsx va machines.tsx da ikki xil o'lchamda (text-2xs va
 * text-xs) qo'lda takrorlangan edi.
 */
export function PostBadge({
  code,
  className,
}: {
  code: string
  className?: string
}) {
  const color = POST_COLORS[code]
  if (!color) return null
  return (
    <span
      className={cn(
        "inline-block rounded-sm px-1.5 py-0.5 text-xs font-bold",
        className,
      )}
      style={chipColors(color, 12)}
    >
      {code}
    </span>
  )
}
