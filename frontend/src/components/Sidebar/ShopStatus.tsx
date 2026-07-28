import { useQuery } from "@tanstack/react-query"

import { POST_COLORS } from "@/lib/mes"
import { getTabloMatrixQueryOptions } from "@/queries/mes"

type Stage = { done: number; total: number }

/**
 * Sidebar pastidagi "sex hozir" bloki — 6 bosqich zanjiri bo'yicha jonli progress.
 *
 * Nega shu yerda: navigatsiya ro'yxati tugagach panelning ~40% i bo'sh qolardi,
 * MES qobig'i esa fabrikaning holati haqida hech narsa aytmasdi. Ma'lumot yangi
 * so'rov talab qilmaydi — `["tablo","matrix"]` kaliti boshqaruv paneli bilan
 * bo'lishiladi, TanStack uni dedupe qiladi.
 *
 * Yig'ilgan (icon) rejimda butunlay yashirinadi: 48px enda o'qib bo'lmaydi.
 */
export function ShopStatus() {
  const { data } = useQuery(getTabloMatrixQueryOptions())
  // Yuklanmaguncha hech narsa: bo'sh quti chaqnab o'tmasin
  if (!data) return null

  const posts = [...((data.posts ?? []) as Array<{ code: string }>)]
  const totals = posts.map((p) => {
    let done = 0
    let total = 0
    for (const o of data.orders) {
      const st = (o.stages as Record<string, Stage>)[p.code]
      if (!st) continue
      done += st.done
      total += st.total
    }
    return { code: p.code, done, total }
  })

  const working = totals.filter((t) => t.total > 0)

  // Sex bo'sh ekani ham ma'lumot — bo'shliq qoldirgandan ko'ra aytib qo'ygan
  // ma'qul (aks holda panel yana tugallanmagandek ko'rinadi).
  if (!working.length) {
    return (
      <div className="mt-auto px-2 pb-2 group-data-[collapsible=icon]:hidden">
        <div className="rounded-lg bg-sidebar-accent/40 px-3 py-2.5">
          <span className="text-[10px] font-bold uppercase tracking-widest text-sidebar-foreground/60">
            Sex hozir
          </span>
          <p className="mt-1 text-xs text-sidebar-foreground/50">
            Ishlab chiqarishda buyurtma yo'q
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-auto px-2 pb-2 group-data-[collapsible=icon]:hidden">
      <div className="rounded-lg bg-sidebar-accent/40 p-3">
        <div className="mb-2.5 flex items-baseline justify-between">
          <span className="text-[10px] font-bold uppercase tracking-widest text-sidebar-foreground/60">
            Sex hozir
          </span>
          <span className="num text-[10px] text-sidebar-foreground/50">
            {data.orders.length} buyurtma
          </span>
        </div>
        <div className="space-y-1.5">
          {working.map((t) => {
            const pct = Math.round((t.done / t.total) * 100)
            return (
              <div key={t.code} className="flex items-center gap-2">
                <span className="w-[62px] shrink-0 truncate text-[10px] font-semibold text-sidebar-foreground/80">
                  {t.code}
                </span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sidebar-foreground/10">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: POST_COLORS[t.code],
                    }}
                  />
                </div>
                <span className="num w-8 shrink-0 text-right text-[10px] tabular-nums text-sidebar-foreground/70">
                  {pct}%
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
