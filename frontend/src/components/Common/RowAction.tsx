import type { LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/** Jadval qatoridagi amal tugmasi — reyestrlarda BITTA o'lcham va rang.
 *
 * Ilgari har reyestr o'zicha yozardi: `size="sm"` (matnli tugma balandligi),
 * `size="icon"` + `size-8`, yoki override'siz `size="icon"` (size-9) — ya'ni
 * bir xil ish uch xil kattalikda ko'rinardi. O'chirish ham birida DOIM qizil,
 * boshqasida faqat hoverda edi.
 *
 * `danger` — buzuvchi amal: odatiy holatda kulrang, hoverda qizil. Doim qizil
 * turgani qatorni shovqinli qilardi va ko'z boshqa amallarni ilg'amasdi.
 */
export function RowAction({
  icon: Icon,
  title,
  onClick,
  danger = false,
}: {
  icon: LucideIcon
  /** Tooltip va ekran o'quvchi uchun — ikonka yolg'iz turadi. */
  title: string
  onClick: () => void
  danger?: boolean
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn(
        "size-8 text-muted-foreground",
        danger && "hover:text-destructive",
      )}
      title={title}
      aria-label={title}
      onClick={onClick}
    >
      <Icon />
    </Button>
  )
}
