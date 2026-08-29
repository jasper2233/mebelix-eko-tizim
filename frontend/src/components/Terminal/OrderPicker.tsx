// Proyekt tanlagichi: post sahifalari shundan boshlanadi (ARRA xaritasi, CNC
// detallari, kromka, bo'yoq/stolyarka navbati, qadoqlash, TMO).
// `done/total` post semantikasida — backend `/terminal/orders` hisoblaydi.

import { useQuery } from "@tanstack/react-query"

import { TerminalService } from "@/client"
import { SectionTitle } from "@/components/Common/SectionTitle"
import { Skeleton } from "@/components/ui/skeleton"
import {
  deadlineTone,
  formatDate,
  PRIORITY_BADGE_CLASSES,
  PRIORITY_LABELS,
} from "@/lib/mes"

export function OrderPicker({
  onPick,
  title = "Proyektlar — xarita uchun proyektni tanlang",
  showCutmapBadge = true,
}: {
  onPick: (orderId: number) => void
  title?: string
  showCutmapBadge?: boolean
}) {
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
    <div className="h-full overflow-y-auto rounded-xl border bg-card p-4">
      <SectionTitle>{title}</SectionTitle>
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
            const total = o.total ?? 0
            const done = o.done ?? 0
            const pct = total ? Math.round((done / total) * 100) : 0
            const finished = total > 0 && done >= total
            const tone = deadlineTone(o.deadline)
            return (
              <button
                type="button"
                key={o.id}
                onClick={() => onPick(o.id)}
                className={`rounded-xl border-2 p-4 text-left outline-none transition-all hover:border-primary focus-visible:ring-[3px] focus-visible:ring-ring/50 active:scale-[0.98] active:border-primary ${
                  finished ? "border-green-500/60 bg-green-50/50" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-base font-black">{o.number}</div>
                    <div className="truncate text-sm text-muted-foreground">
                      {o.project_name ?? ""}
                    </div>
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
                {/* Material — arrachi arradagi plita bo'yicha partiyalab kesadi */}
                {!!o.materials?.length && (
                  <div className="mt-1 truncate text-sm font-semibold">
                    {o.materials.join(" · ")}
                  </div>
                )}
                <div className="mt-2">
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full rounded-full ${finished ? "bg-green-500" : "bg-primary"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="num mt-1 flex items-end justify-between">
                    {finished ? (
                      <span className="text-xl font-black text-green-600">
                        ✓ 100%
                      </span>
                    ) : (
                      <span className="text-xl font-black text-primary">
                        Qoldiq: {total - done}
                      </span>
                    )}
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
