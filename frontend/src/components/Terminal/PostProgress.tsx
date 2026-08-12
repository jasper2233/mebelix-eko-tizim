// Post ekranining YAGONA uzoqdan o'qiladigan raqami: qancha ish qoldi.
//
// O'lcham tasodifiy emas. Sanoat HMI qoidasi: qulay o'qish masofasi ≈ harf
// balandligi × 150…200. 17" monoblokda piksel qadami ~0.26 mm, ya'ni:
//   text-base (16px) -> harf ~3 mm -> ~0.5 m   (operator terminalga borishi kerak)
//   text-5xl  (48px) -> harf ~9 mm -> ~1.5 m   (yonidan o'tib ketayotib o'qiydi)
// Qolgan hamma narsa (qatorlar, o'lchamlar, kodlar) qo'l uzunligida o'qiladi —
// ularni kattalashtirish shart emas va joy ham yo'q.
//
// Raqam QOLDIQ, "bajarildi" emas: operatorning savoli "yana qancha qoldi?".
// `4/25` dan qoldiqni hisoblab olish — ortiqcha ish, ayniqsa qo'lqopda va
// arra shovqinida. Bajarilgan/jami kichik shriftda yonida turadi (kontekst).

import { cn } from "@/lib/utils"

export function PostProgress({
  done,
  total,
  className,
}: {
  done: number
  total: number
  /** Nima sanalayotgani — kromkada tomonlar, qolganida detallar */
  className?: string
}) {
  const left = Math.max(0, total - done)
  const ready = total > 0 && left === 0
  return (
    <div className={cn("flex items-baseline gap-2.5", className)}>
      {ready ? (
        <span className="text-3xl font-black leading-none text-green-600">
          TAYYOR
        </span>
      ) : (
        <>
          <span className="text-2xs font-bold uppercase tracking-wider text-muted-foreground">
            Qoldiq
          </span>
          <span className="num text-5xl font-black leading-none tabular-nums">
            {left}
          </span>
        </>
      )}
      <span className="num text-sm text-muted-foreground">
        {done}/{total}
      </span>
    </div>
  )
}
