// Signature element: the production pipeline rendered as connected stage
// cells. Cell count is data-driven — one per `stages` entry, not a fixed chain.

import { mixTint, POST_COLORS } from "@/lib/mes"

type StageCell = {
  code: string
  done: number
  total: number
}

export function StagePipeline({
  stages,
  showLabels = false,
}: {
  stages: StageCell[]
  /** Katak ostida post kodi: jadval ustunisiz (buyurtma sahifasida) rangning
   *  o'zi bosqichni aytmaydi. */
  showLabels?: boolean
}) {
  if (!stages.length)
    return <span className="text-xs text-muted-foreground">—</span>
  // Yorliqli rejimda katakchalar tor ekranda keyingi qatorga o'tadi: yorliq katakni
  // kengaytiradi va 360 px telefonda 6 bosqich (354 px) ichki kenglikdan (312 px)
  // oshib, sahifani yonga surardi. Yashirilmaydi — hamma bosqich ko'rinsin.
  // Telefonda ulovchi chiziqcha o'rniga oraliq: aks holda o'ralgan qator «—» bilan
  // boshlanardi.
  return (
    <div
      className={`flex ${showLabels ? "flex-wrap items-start gap-y-1 max-sm:gap-x-1.5" : "items-center"}`}
    >
      {stages.map((s, i) => {
        const color = POST_COLORS[s.code] ?? "var(--status-draft)"
        const pct =
          s.total > 0 ? Math.min(100, Math.round((s.done / s.total) * 100)) : 0
        const complete = s.total > 0 && s.done >= s.total
        return (
          <div
            key={s.code}
            className={`flex ${showLabels ? "items-start" : "items-center"}`}
          >
            {i > 0 && (
              <div
                className={`mt-3 h-px w-1.5 bg-border ${showLabels ? "max-sm:hidden" : ""}`}
              />
            )}
            <div>
              <div
                className="relative h-6 w-12 overflow-hidden rounded-sm"
                style={{ backgroundColor: mixTint(color, 14) }}
                title={`${s.code}: ${s.done}/${s.total} (${pct}%)`}
              >
                <div
                  className="absolute inset-y-0 left-0 transition-all duration-500"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: mixTint(color, 38),
                  }}
                />
                {/* Raqam post rangida emas, --foreground da: post rangi o'z tinti
                  ustida atigi 2.89-3.12:1 berardi. Bosqich identifikatsiyasini
                  katak foni va to'ldirgich rangi allaqachon tashiydi. */}
                <span className="num relative flex h-full items-center justify-center text-2xs font-bold text-foreground">
                  {complete ? "✓" : `${s.done}/${s.total}`}
                </span>
              </div>
              {showLabels && (
                <div className="mt-0.5 text-center text-2xs font-medium uppercase tracking-wider text-muted-foreground">
                  {s.code}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
