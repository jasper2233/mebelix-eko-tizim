import { cn } from "@/lib/utils"

const HOLAT: Record<string, { l: string; c: string }> = {
  qoralama: { l: "qoralama", c: "bg-muted text-foreground" },
  navbatda: { l: "navbatda", c: "bg-amber-100 text-amber-900" },
  yuborildi: { l: "yuborildi", c: "bg-sky-100 text-sky-900" },
  qabul_qilindi: { l: "qabul qilindi", c: "bg-emerald-100 text-emerald-900" },
  rad_etildi: { l: "rad etildi", c: "bg-red-100 text-red-900" },
  kutilmoqda: { l: "javob kutmoqda", c: "bg-amber-100 text-amber-900" },
  xato: { l: "operator xatosi", c: "bg-red-100 text-red-900" },
  bekor: { l: "bekor", c: "bg-muted text-muted-foreground line-through" },
}

/** ESF holati belgisi — Soliq sahifasi va moliya buyurtma kartasi uchun bitta manba */
export function EsfHolat({ h }: { h: string }) {
  const x = HOLAT[h] ?? { l: h, c: "bg-muted" }
  return (
    <span className={cn("rounded px-2 py-0.5 text-xs whitespace-nowrap", x.c)}>
      {x.l}
    </span>
  )
}
