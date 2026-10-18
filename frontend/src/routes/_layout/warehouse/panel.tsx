// Mahsulotlar ombori — Boshqaruv paneli (dizayndagi «Ombor holati»): narx boshqaruvi.
//
//   * LDSP / LMDF sinflari va sotuv narxi — sinf narxi o'zgarsa shu sinfdagi HAMMA dekor birdan;
//   * dollar kursi — kirim dollarda, kurs o'zgarsa xarid va furnitura sotuvi qayta hisoblanadi;
//   * furnitura ustamasi — umumiy va guruh bo'yicha; sotuv = tannarx + foiz, 100 so'mgacha.
//
// Har maydon fokusdan chiqqanda (yoki Enter) BUTUN sozlama saqlanadi va server hamma narxni qayta
// hisoblaydi (`PUT /catalog/pricing`). Hisob qoidasi — `backend/app/services/warehouse.py`.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import { CatalogService, type WarehousePricingOutput } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { GotoSearch } from "@/components/Warehouse/GotoSearch"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  fmt,
  fmtQty,
  groupKey,
  KROMKA_GROUP,
  kromkaSize,
  num,
  parseNum,
  TIER_GROUPS,
  TIERS,
} from "@/lib/warehouse"
import {
  getCatalogAllQueryOptions,
  getWarehousePricingQueryOptions,
} from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/warehouse/panel")({
  component: PanelPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Ombor holati | MebeliX" }] }),
})

type Pricing = Required<WarehousePricingOutput>

function PanelPage() {
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const queryClient = useQueryClient()
  const pricingQ = useQuery(getWarehousePricingQueryOptions())
  const { data: rows } = useQuery(getCatalogAllQueryOptions())

  const save = useMutation({
    mutationFn: (body: Pricing) =>
      CatalogService.updateWarehousePricing({ body }),
    onSuccess: () => toast.success("Saqlandi — narxlar qayta hisoblandi"),
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["catalog"] }),
  })

  //: Kromka o'lchamlari KATALOGDAN keladi — ro'yxat kodga yozilmagan: yangi o'lcham qo'shilsa
  //: (masalan 42×2) panelda o'zi paydo bo'ladi. Qo'lda narx qo'yilganlari alohida sanaladi.
  const kromka = useMemo(() => {
    const m = new Map<string, { n: number; qolda: number }>()
    let olchamsiz = 0
    for (const r of rows ?? []) {
      if (groupKey(r) !== KROMKA_GROUP) continue
      const o = kromkaSize(r.name)
      if (!o) {
        olchamsiz++
        continue
      }
      const g = m.get(o) ?? { n: 0, qolda: 0 }
      g.n++
      if (r.narx_qolda) g.qolda++
      m.set(o, g)
    }
    return {
      sizes: [...m].sort(([a], [b]) =>
        a.localeCompare(b, "uz", { numeric: true }),
      ),
      olchamsiz,
    }
  }, [rows])

  const counts = useMemo(() => {
    const tier: Record<string, number> = {}
    const fg = new Map<string, { name: string; n: number }>()
    let f = 0
    for (const r of rows ?? []) {
      if (r.tier)
        tier[`${groupKey(r)}:${r.tier}`] =
          (tier[`${groupKey(r)}:${r.tier}`] ?? 0) + 1
      if (r.catalog === "F") {
        f++
        const g = fg.get(groupKey(r)) ?? { name: r.group_name, n: 0 }
        g.n++
        fg.set(groupKey(r), g)
      }
    }
    return { tier, f, fGroups: [...fg].sort(([a], [b]) => a.localeCompare(b)) }
  }, [rows])

  if (pricingQ.isError) return <QueryError onRetry={() => pricingQ.refetch()} />
  if (!pricingQ.data) return <Skeleton className="h-96 w-full" />
  const p: Pricing = {
    usd_rate: pricingQ.data.usd_rate ?? "12800",
    tier_prices: pricingQ.data.tier_prices ?? {},
    markup_all: pricingQ.data.markup_all ?? null,
    markup_groups: pricingQ.data.markup_groups ?? {},
    kromka_prices: pricingQ.data.kromka_prices ?? {},
  }
  const put = (next: Pricing) => canWrite && save.mutate(next)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Ombor holati"
        description="Narx boshqaruvi: dekor sinflari, kromka o'lchamlari, dollar kursi va furnitura ustamasi"
        actions={<GotoSearch />}
      />

      <section className={cn(cardSurface, "space-y-3 p-4")}>
        <h2 className="font-semibold">
          LDSP / LMDF sinflari va sotuv narxi{" "}
          <span className="text-sm font-normal text-muted-foreground">
            Narxni o'zgartirsangiz, shu sinfdagi barcha dekorning sotuv narxi
            birdan yangilanadi · 1 list uchun, so'm
          </span>
        </h2>
        <div className="grid grid-cols-[4rem_repeat(3,minmax(0,1fr))] items-start gap-3">
          <span />
          {TIERS.map(([k, n]) => (
            <span
              key={k}
              className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
            >
              <span className="mr-1.5 rounded bg-primary px-1 text-primary-foreground">
                {k}
              </span>
              {n}
            </span>
          ))}
          {TIER_GROUPS.map(([gk, label, birlik]) => (
            <TierRow
              key={gk}
              label={label}
              birlik={birlik}
              gk={gk}
              p={p}
              counts={counts.tier}
              disabled={!canWrite}
              onSave={put}
            />
          ))}
        </div>
      </section>

      <section className={cn(cardSurface, "space-y-3 p-4")}>
        <h2 className="font-semibold">
          Kromka narxi{" "}
          <span className="text-sm font-normal text-muted-foreground">
            O'LCHAM bo'yicha, 1 metr uchun · narx qo'yilsa shu o'lchamdagi hamma
            kromka birdan yangilanadi · o'lcham kromkaning nomidan olinadi
          </span>
        </h2>
        {kromka.sizes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Katalogda kromka yo'q.
          </p>
        ) : (
          <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
            {kromka.sizes.map(([o, g]) => (
              <div
                key={o}
                className="flex items-center gap-2 border-b py-1.5 text-sm"
              >
                <span className="num w-20 font-semibold">{o} mm</span>
                <span className="text-xs text-muted-foreground">
                  {g.n} ta
                  {g.qolda > 0 && (
                    <span title="Sotuv narxi qo'lda qo'yilgan — guruh narxi ularga tegmaydi">
                      {" "}
                      · {g.qolda} tasi qo'lda
                    </span>
                  )}
                </span>
                <NumInput
                  className="ml-auto w-28 text-right"
                  value={p.kromka_prices[o] ?? null}
                  placeholder="narx"
                  disabled={!canWrite}
                  onSave={(v) => {
                    const next = { ...p.kromka_prices }
                    if (v == null) delete next[o]
                    else next[o] = String(v)
                    put({ ...p, kromka_prices: next })
                  }}
                />
              </div>
            ))}
          </div>
        )}
        <p className="text-sm text-muted-foreground">
          Narxi qo'yilmagan o'lcham furnitura ustamasi bilan hisoblanadi. Sotuv
          narxi QO'LDA kiritilgan kromka (masalan «21×1 metallik») guruh narxiga
          qaytmaydi — uni nomenklaturada narxni tozalab qaytarasiz.
          {kromka.olchamsiz > 0 &&
            ` O'lchamsiz ${kromka.olchamsiz} ta kromka (qog'oz va h.k.) — narxi faqat qo'lda.`}
        </p>
      </section>

      <section
        className={cn(
          cardSurface,
          "flex flex-wrap items-center justify-between gap-3 p-4",
        )}
      >
        <div>
          <h2 className="font-semibold">Dollar kursi</h2>
          <p className="text-sm text-muted-foreground">
            Kirim dollarda yoziladi va shu kurs bilan so'mga o'tadi. Kurs
            o'zgarsa, dollardagi xarid narxi va furnitura sotuv narxlari qayta
            hisoblanadi.
          </p>
          <CbRate
            shopRate={num(p.usd_rate)}
            canWrite={canWrite}
            onApply={(v) => put({ ...p, usd_rate: v })}
          />
        </div>
        <div className="flex items-center gap-2 text-lg font-semibold">
          1 $ =
          <NumInput
            ariaLabel="Dollar kursi, so'm"
            className="w-36 text-right text-lg font-bold"
            value={p.usd_rate}
            disabled={!canWrite}
            required
            onSave={(v) =>
              v != null && v > 0 && put({ ...p, usd_rate: String(v) })
            }
          />
          <span className="text-sm font-normal">so'm</span>
        </div>
      </section>

      <section className={cn(cardSurface, "space-y-3 p-4")}>
        <h2 className="font-semibold">
          Furnitura ustamasi{" "}
          <span className="text-sm font-normal text-muted-foreground">
            Sotuv narxi = tannarx + foiz. Guruh foizi bo'sh bo'lsa, umumiy foiz
            ishlatiladi · 100 so'mgacha yaxlitlanadi
          </span>
        </h2>
        <div className="flex items-center justify-between rounded-md border bg-primary/5 px-4 py-3">
          <b>Barcha furnitura</b>
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            {fmt(counts.f)} pozitsiya
            <NumInput
              className="w-20 text-right"
              value={p.markup_all}
              disabled={!canWrite}
              onSave={(v) =>
                put({ ...p, markup_all: v == null ? null : String(v) })
              }
            />
            %
          </span>
        </div>
        <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {counts.fGroups.map(([gk, g]) => (
            <div
              key={gk}
              className="flex items-center gap-2 border-b py-1.5 text-sm"
            >
              <span className="num w-12 text-xs text-muted-foreground">
                {gk}
              </span>
              <span className="min-w-0 flex-1 truncate font-semibold">
                {g.name}
              </span>
              <span className="text-xs text-muted-foreground">{g.n} ta</span>
              <NumInput
                className="h-8 w-16 text-right"
                value={p.markup_groups[gk] ?? null}
                placeholder={
                  p.markup_all != null ? String(num(p.markup_all)) : "—"
                }
                disabled={!canWrite}
                onSave={(v) => {
                  const g = { ...p.markup_groups }
                  if (v == null) delete g[gk]
                  else g[gk] = String(v)
                  put({ ...p, markup_groups: g })
                }}
              />
              %
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

function TierRow({
  label,
  birlik,
  gk,
  p,
  counts,
  disabled,
  onSave,
}: {
  label: string
  birlik: string
  gk: string
  p: Pricing
  counts: Record<string, number>
  disabled: boolean
  onSave: (p: Pricing) => void
}) {
  return (
    <>
      <span className="pt-2 font-semibold">
        {label}
        <span className="block text-xs font-normal text-muted-foreground">
          {birlik}
        </span>
      </span>
      {TIERS.map(([k]) => (
        <div key={k} className="space-y-1">
          <NumInput
            className="w-full text-right"
            value={p.tier_prices[gk]?.[k] ?? null}
            placeholder="narx kiriting"
            disabled={disabled}
            onSave={(v) => {
              const g = { ...(p.tier_prices[gk] ?? {}) }
              if (v == null) delete g[k]
              else g[k] = String(v)
              onSave({ ...p, tier_prices: { ...p.tier_prices, [gk]: g } })
            }}
          />
          <p className="text-xs text-muted-foreground">
            {counts[`${gk}:${k}`] ?? 0} ta pozitsiya
          </p>
        </div>
      ))}
    </>
  )
}

/** Son maydoni: fokusdan chiqqanda yoki Enter'da saqlaydi; bo'sh — `null`. */
function NumInput({
  value,
  onSave,
  className,
  placeholder,
  disabled,
  required,
  ariaLabel,
}: {
  ariaLabel?: string
  value: string | number | null
  onSave: (v: number | null) => void
  className?: string
  placeholder?: string
  disabled?: boolean
  required?: boolean
}) {
  // Katta son (narx, kurs) guruhlanadi, kichigi (foiz) kasri bilan qoladi
  const shown =
    value == null || value === ""
      ? ""
      : num(value) >= 1000
        ? fmt(value)
        : String(num(value))
  const [v, setV] = useState<string | null>(null)
  return (
    <Input
      className={cn("num", className)}
      aria-label={ariaLabel}
      inputMode="decimal"
      value={v ?? shown}
      placeholder={placeholder ?? "—"}
      disabled={disabled}
      onFocus={() => setV(shown.replace(/\s/g, ""))}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => {
        if (v != null && v !== shown.replace(/\s/g, "")) {
          const n = parseNum(v)
          if (n == null && (required || v.trim() !== ""))
            toast.error("Son kiriting")
          else onSave(n)
        }
        setV(null)
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur()
      }}
    />
  )
}

/** Markaziy bank kursi sexdagi kurs YONIDA. Hisobga tushmaydi — narx sexdagi kurs bilan
 *  hisoblanadi; bu yerda faqat «bankda qancha» va farqi turadi. Bank javob bermasa (yoki
 *  kurs hali olinmagan bo'lsa) umuman chizilmaydi: usiz ham panel to'liq ishlaydi. */
function CbRate({
  shopRate,
  canWrite,
  onApply,
}: {
  shopRate: number
  canWrite: boolean
  onApply: (rate: string) => void
}) {
  const { data } = useQuery({
    queryKey: ["catalog", "cb-rate"],
    queryFn: async () => (await CatalogService.readCbRate()).data ?? null,
    staleTime: 30 * 60_000,
  })
  if (!data) return null
  const bank = num(data.rate)
  // 1 so'mgacha farq — bir xil deb hisoblanadi (bank kasr bilan beradi)
  const mos = Math.abs(bank - shopRate) < 1
  const farq = bank - shopRate
  return (
    <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <span className="text-muted-foreground">Markaziy bank:</span>
      {/* Bank kursni tiyin bilan beradi (12 055.90) — yaxlitlab ko'rsatsak, tugma
          qo'yadigan qiymat ekrandagidan boshqa bo'lib qolardi */}
      <span className="num font-semibold">{fmtQty(data.rate)} so'm</span>
      <span className="num text-muted-foreground">{data.date}</span>
      {mos ? (
        <span className="text-muted-foreground">· kurs mos</span>
      ) : (
        <>
          <span
            className={cn(
              "num font-semibold",
              farq > 0 ? "text-amber-700" : "text-muted-foreground",
            )}
            title="Sexdagi kursdan farqi"
          >
            · {farq > 0 ? "+" : "−"}
            {fmtQty(Math.abs(farq))}
          </span>
          {canWrite && (
            <Button
              variant="outline"
              size="sm"
              className="h-7"
              // So'mgacha yaxlitlanadi: sexdagi kurs ish raqami, tiyin unga shovqin —
              // maydon baribir butun son ko'rsatadi, saqlangani boshqa bo'lib qolmasin
              onClick={() => onApply(String(Math.round(bank)))}
            >
              Bank kursini qo'yish
            </Button>
          )}
        </>
      )}
    </p>
  )
}
