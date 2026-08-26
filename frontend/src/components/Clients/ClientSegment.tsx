import { cn } from "@/lib/utils"

/** ABC (Pareto) segmenti — mijozning aylanmadagi og'irligi.
 *
 * Yulduzcha reyting bu ma'lumotda ishlamaydi: prodda o'lchandi, eng yirik mijoz
 * aylanmaning 81% ini beradi, ya'ni qolgan yigirmatasi bir xil past bahoni
 * olardi va reyting hech narsani ajratmasdi. ABC aynan shunday nomutanosib
 * taqsimot uchun qilingan va omborxona/mijoz tahlilida standart hisoblanadi.
 *
 * Rang bilan emas, OG'IRLIK bilan kodlangan: qizil/yashil tizimda holat degani
 * (kechikdi, bajarildi), shuning uchun bu yerda ular boshqa ma'no berardi.
 */
const SEGMENTS: Record<string, { klass: string; izoh: string }> = {
  A: {
    klass: "bg-primary text-primary-foreground",
    izoh: "Aylanmaning birinchi 80% i",
  },
  B: {
    klass: "bg-secondary text-secondary-foreground",
    izoh: "80–95% oralig'i",
  },
  C: {
    klass: "border border-border text-muted-foreground",
    izoh: "Oxirgi 5%",
  },
}

export function ClientSegment({ segment }: { segment?: string | null }) {
  const s = SEGMENTS[segment ?? "C"] ?? SEGMENTS.C
  return (
    <span
      title={s.izoh}
      className={cn(
        "inline-flex size-7 items-center justify-center rounded-sm font-black tabular-nums",
        s.klass,
      )}
    >
      {segment ?? "C"}
    </span>
  )
}
