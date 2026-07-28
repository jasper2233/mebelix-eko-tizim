import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/**
 * Sahifa ichidagi bo'lim sarlavhasi — karta guruhi yoki jadval ustida turadi.
 *
 * Ierarxiya: `PageHeader` (h1) > `SectionTitle` (h2) > panel sarlavhalari (h3).
 * Avval bir xil daraja to'rt xil yozilgan edi (`text-sm uppercase muted`,
 * `text-base font-semibold`, `text-lg font-semibold` va yalang'och
 * `font-semibold`), shuning uchun bir sahifadagi ikki bo'lim turli og'irlikda
 * ko'rinardi.
 */
export function SectionTitle({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <h2
      className={cn(
        "mb-2 text-sm font-bold uppercase tracking-wider text-muted-foreground",
        className,
      )}
    >
      {children}
    </h2>
  )
}
