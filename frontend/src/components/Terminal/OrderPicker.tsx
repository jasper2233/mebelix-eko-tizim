// Proyekt tanlagichi: post sahifalari shundan boshlanadi (ARRA xaritasi, CNC
// detallari, kromka, bo'yoq/stolyarka navbati, qadoqlash, TMO).
// `done/total` post semantikasida — backend `/terminal/orders` hisoblaydi.

import { useQuery } from "@tanstack/react-query"

import { TerminalService } from "@/client"
import { SectionTitle } from "@/components/Common/SectionTitle"
import { useDragScroll } from "@/components/Terminal/useDragScroll"
import { Skeleton } from "@/components/ui/skeleton"
import {
  deadlineTone,
  formatDate,
  PRIORITY_BADGE_CLASSES,
  PRIORITY_LABELS,
} from "@/lib/mes"

/** Kartadagi ish hajmi qatori. Faqat bittasi to'ladi — qaysi biri, postga bog'liq. */
function hajm(o: {
  band_m?: number | null
  band_kinds?: number
  holes?: number | null
  materials?: string[] | null
}): string {
  if (o.band_m != null) {
    const xil = (o.band_kinds ?? 0) > 1 ? ` · ${o.band_kinds} xil` : ""
    return `${Math.round(o.band_m)} m kromka${xil}`
  }
  if (o.holes != null) return `${o.holes} teshik`
  return o.materials?.join(" · ") ?? ""
}

export function OrderPicker({
  onPick,
  showCutmapBadge = true,
}: {
  onPick: (orderId: number) => void
  showCutmapBadge?: boolean
}) {
  // Monoblokda barmoq bilan surib aylantirish — scrollbar qo'lqopda tortilmaydi
  const listScroll = useDragScroll()
  const {
    data: orders,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["terminal", "orders"],
    queryFn: async () => (await TerminalService.readTerminalOrders()).data,
    refetchInterval: 30_000,
  })
  return (
    <div
      className="h-full overflow-y-auto rounded-xl border bg-card p-4"
      ref={listScroll.ref}
      {...listScroll.props}
    >
      <SectionTitle>Buyurtmalar</SectionTitle>
      {isError && (
        <div className="mb-3 rounded-lg border-2 border-red-500 bg-red-50 px-4 py-3 text-base font-bold text-red-700">
          Yuklashda xato — qayta urinilmoqda...
        </div>
      )}
      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-44 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {orders?.map((o) => {
            // Tugagan buyurtma bu ro'yxatda YO'Q: backend uni `/terminal/orders`
            // da tashlab ketadi (done >= total -> continue), ya'ni bu yerda
            // doim qoldiq bo'ladi.
            const total = o.total
            const done = o.done
            const pct = total ? Math.round((done / total) * 100) : 0
            const tone = deadlineTone(o.deadline)
            return (
              <button
                type="button"
                key={o.id}
                onClick={() => onPick(o.id)}
                className="rounded-xl border-2 p-4 text-left outline-none transition-all hover:border-primary focus-visible:ring-[3px] focus-visible:ring-ring/50 active:scale-[0.98] active:border-primary"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    {/* Loyiha nomi katta — PostHeader bilan bir: ishchi
                        buyurtmani nomidan taniydi, raqam chek prefiksi */}
                    <div className="truncate text-base font-black">
                      {o.project_name || o.number}
                    </div>
                    {o.project_name && (
                      <div className="num text-sm text-muted-foreground">
                        {o.number}
                      </div>
                    )}
                  </div>
                  {o.priority && (
                    <span
                      className={`shrink-0 rounded-sm px-2 py-0.5 text-sm font-black ${
                        PRIORITY_BADGE_CLASSES[o.priority] ??
                        "bg-muted text-muted-foreground"
                      }`}
                    >
                      {PRIORITY_LABELS[o.priority] ?? o.priority}
                    </span>
                  )}
                </div>
                {/* Bitta qator — SHU postning ish hajmi. Arrada plita nomi
                    (partiyalab kesadi), kromkada necha metr lenta kerakligi,
                    CNC'da teshik soni. Post-ga tegishlisini SERVER tanlaydi:
                    `/terminal/orders` post kontekstida javob beradi, ya'ni
                    kartada begona postning raqami umuman paydo bo'lmaydi.
                    Kromka TAQSIMOTI bu yerda emas — uchta material nomi kartaga
                    sig'maydi va `truncate` aynan muhim qismini kesadi; u
                    buyurtma ochilganda ro'yxat ustida turadi. */}
                {hajm(o) && (
                  <div className="mt-1 truncate text-sm font-semibold">
                    {hajm(o)}
                  </div>
                )}
                <div className="mt-2">
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="num mt-1 flex items-end justify-between">
                    <span className="text-xl font-black text-primary">
                      Qoldiq: {total - done}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {done}/{total} detal
                      {o.sheets_total ? ` · ${o.sheets_total} list` : ""}
                    </span>
                  </div>
                </div>
                <div
                  className={`num mt-1.5 text-base font-bold ${
                    tone === "overdue"
                      ? "text-red-600"
                      : tone === "today"
                        ? "text-amber-700"
                        : ""
                  }`}
                >
                  {formatDate(o.deadline)}
                  {tone === "overdue" && " · KECHIKKAN"}
                  {tone === "today" && " · BUGUN"}
                </div>
                {showCutmapBadge && o.has_cutmap === false && (
                  <span className="mt-1.5 inline-block rounded-sm bg-muted px-2 py-0.5 text-xs font-bold text-muted-foreground">
                    XARITA YO'Q
                  </span>
                )}
              </button>
            )
          })}
          {!isError && !orders?.length && (
            <p className="text-sm text-muted-foreground">
              Aktiv buyurtmalar yo'q
            </p>
          )}
        </div>
      )}
    </div>
  )
}
