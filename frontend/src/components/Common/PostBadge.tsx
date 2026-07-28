import { POST_COLORS } from "@/lib/mes"
import { cn } from "@/lib/utils"

/**
 * Bosqich (post) kodi chipi — ARRA, KROMKA, ...
 *
 * Matn post rangining to'qroq variantida: sof post rangi 12% tint fonda atigi
 * 4.25-4.35:1 berardi (ARRA, PAZ, STOLYARKA WCAG AA dan o'tmasdi), chunki matn
 * ham, fon ham bir xil tondan olingan. `78%, black` bilan nisbat 6.18-7.01:1
 * ga chiqadi va chipning yengil ko'rinishi saqlanadi.
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
      style={{
        color: `color-mix(in srgb, ${color} 78%, black)`,
        backgroundColor: `color-mix(in srgb, ${color} 12%, white)`,
      }}
    >
      {code}
    </span>
  )
}
