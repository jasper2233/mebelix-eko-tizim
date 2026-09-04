// Nusxa chipi — post navbati (BOYOQ/STOLYARKA/TMO) va qadoqlash ro'yxatida BIR XIL:
// №n + holat. Kulrang «–» — navbatda/tayyor, yashil ✓ — bajarildi. Ikki ekran
// bir xil belgini har xil chizmasin deb bitta joyda.

import { cn } from "@/lib/utils"

/** Nusxa raqami — chekdagi ID dumi (`…_01_001_10` → 10); dumsiz yagona nusxa → 1 */
export const instanceNo = (qr: string): number => {
  const m = /_(\d+)$/.exec(qr)
  return m ? Number(m[1]) : 1
}

export function InstanceChip({
  qr,
  done,
  many,
  className,
}: {
  qr: string
  done: boolean
  /** Detalning bir nechta nusxasi bor — raqam ko'rsatiladi */
  many: boolean
  className?: string
}) {
  return (
    <span
      title={qr}
      className={cn(
        "num rounded-md px-2.5 py-1 text-lg font-black",
        done ? "bg-green-600 text-white" : "bg-muted text-muted-foreground",
        className,
      )}
    >
      {many && (
        <span className="mr-1 text-xs font-bold opacity-70">
          №{instanceNo(qr)}
        </span>
      )}
      {done ? "✓" : "–"}
    </span>
  )
}
