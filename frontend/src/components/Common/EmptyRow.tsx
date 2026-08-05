import type { ReactNode } from "react"

import { TableCell, TableRow } from "@/components/ui/table"

/** Jadvalning bo'sh holati qatori — "topilmadi / hali yo'q" xabari uchun.
 * Har reyestrda qo'lda takrorlanadigan TableRow+TableCell naqshi BITTA joyda. */
export function EmptyRow({
  colSpan,
  children,
}: {
  colSpan: number
  children: ReactNode
}) {
  return (
    <TableRow>
      <TableCell
        colSpan={colSpan}
        className="h-24 text-center text-muted-foreground"
      >
        {children}
      </TableCell>
    </TableRow>
  )
}
