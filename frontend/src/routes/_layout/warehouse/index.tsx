// Mahsulotlar ombori — Nomenklatura (docs/14 §8, «Qudrat Ombor» dizayni bo'yicha, 2026-10-16).
//
// Butun katalog BIR so'rovda keladi (`GET /catalog/all`, ≈2 700 qator): qidiruv, guruh, «qoldiq < min»,
// material uchun zaxira va sinf filtrlari brauzerda — darhol, sahifa almashmasdan. Ekranda birinchi
// 100 qator, «Yana ko'rsatish» bilan ko'payadi (2 000 qatorli DOM sekinlashtiradi).
// Kategoriya (`?katalog=M|F|X`) va guruh (`?guruh=F-RC`) MANZILDA — yon menyu havolalari shu yerga.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Download, FileUp, Plus, Trash2 } from "lucide-react"
import { type ReactNode, useMemo, useState } from "react"
import { toast } from "sonner"

import { type CatalogRow, CatalogService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
import { SelectField } from "@/components/Common/SelectField"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { GotoSearch } from "@/components/Warehouse/GotoSearch"
import { ImportDialog } from "@/components/Warehouse/ImportDialog"
import { NewItemRow } from "@/components/Warehouse/NewItemRow"
import { SexTabs } from "@/components/Warehouse/SexTabs"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  CATALOG_NAMES,
  type CatalogLetter,
  downloadCsv,
  fmt,
  fmtQty,
  fmtUsd,
  groupKey,
  isLow,
  markupOf,
  num,
  parseNum,
  TIER_NAME,
  TIERS,
  usdOf,
} from "@/lib/warehouse"
import {
  getCatalogAllQueryOptions,
  getWarehousePricingQueryOptions,
} from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/warehouse/")({
  component: NomenklaturaPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Nomenklatura | MebeliX" }] }),
  validateSearch: (
    s: Record<string, unknown>,
  ): { katalog?: string; guruh?: string } => ({
    katalog:
      typeof s.katalog === "string" && /^[MFXS]$/.test(s.katalog)
        ? s.katalog
        : undefined,
    guruh:
      typeof s.guruh === "string" && /^[MFXS]-[A-Z]{2}$/.test(s.guruh)
        ? s.guruh
        : undefined,
  }),
})

const STEP = 100
const TIERABLE = new Set(["M-LD", "M-LM"])

function NomenklaturaPage() {
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const routeNavigate = Route.useNavigate()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { katalog, guruh } = Route.useSearch()
  // Guruh berilsa kategoriya undan (`M-LD` → M)
  const cat = (guruh?.[0] ?? katalog) as CatalogLetter | undefined
  const { data, isLoading, isError, refetch } = useQuery(
    getCatalogAllQueryOptions(),
  )
  const { data: pricing } = useQuery(getWarehousePricingQueryOptions())
  const rate = num(pricing?.usd_rate) || 12800

  const [q, setQ] = useState("")
  const [onlyLow, setOnlyLow] = useState(false)
  const [zaxira, setZaxira] = useState<"all" | "yes" | "no">("all")
  const [tierF, setTierF] = useState("all")
  const [limit, setLimit] = useState(STEP)
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const [newOpen, setNewOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [confirm, setConfirm] = useState<{
    title: string
    description: ReactNode
    run: () => void
    destructive?: boolean
  } | null>(null)

  const all = data ?? []
  const byCat = useMemo(() => {
    const c = { M: 0, F: 0, X: 0, S: 0 }
    for (const r of all) c[r.catalog as CatalogLetter]++
    return c
  }, [all])
  const inCat = useMemo(
    () => (cat ? all.filter((r) => r.catalog === cat) : all),
    [all, cat],
  )
  const groups = useMemo(() => {
    const m = new Map<string, { name: string; n: number }>()
    for (const r of inCat) {
      const g = m.get(groupKey(r)) ?? { name: r.group_name, n: 0 }
      g.n++
      m.set(groupKey(r), g)
    }
    return [...m].sort(([a], [b]) => a.localeCompare(b))
  }, [inCat])

  const rows = useMemo(() => {
    let out = guruh ? inCat.filter((r) => groupKey(r) === guruh) : inCat
    if (onlyLow) out = out.filter(isLow)
    if (cat === "M" && zaxira !== "all")
      out = out.filter((r) => r.tracked === (zaxira === "yes"))
    if (cat === "M" && tierF !== "all")
      out = out.filter(
        (r) =>
          TIERABLE.has(groupKey(r)) &&
          (tierF === "none" ? !r.tier : r.tier === tierF),
      )
    const t = q.trim().toLowerCase()
    if (t)
      out = out.filter(
        (r) =>
          r.code.toLowerCase().includes(t) ||
          r.name.toLowerCase().includes(t) ||
          (r.description ?? "").toLowerCase().includes(t) ||
          (r.decor_name ?? "").toLowerCase().includes(t) ||
          (r.article ?? "").toLowerCase().includes(t),
      )
    return out
  }, [inCat, guruh, onlyLow, zaxira, tierF, cat, q])
  const visible = rows.slice(0, limit)
  const lowCount = useMemo(() => all.filter(isLow).length, [all])
  const tierable = rows.filter((r) => TIERABLE.has(groupKey(r)))
  const sel = all.filter((r) => checked.has(r.id))

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["catalog"] })
  const bulk = useMutation({
    mutationFn: (body: {
      ids: number[]
      tier?: "S" | "M" | "P" | ""
      tracked?: boolean
    }) => CatalogService.bulkUpdateCatalogItems({ body }),
    onSuccess: (r) =>
      toast.success(`${r.data.codes.length} ta pozitsiya yangilandi`),
    onError: handleError,
    onSettled: invalidate,
  })
  const remove = useMutation({
    mutationFn: (ids: number[]) =>
      CatalogService.deleteCatalogItems({ body: { ids } }),
    onSuccess: (r) => {
      toast.success(`${r.data.codes.length} ta mahsulot o'chirildi`)
      setChecked(new Set())
    },
    onError: handleError,
    onSettled: invalidate,
  })
  const markup = useMutation({
    mutationFn: (v: { id: number; pct: number | null }) =>
      CatalogService.updateCatalogItem({
        path: { item_id: v.id },
        body: { markup_pct: v.pct },
      }),
    onError: handleError,
    onSettled: invalidate,
  })

  const resetPaging = () => setLimit(STEP)
  const toggle = (id: number) =>
    setChecked((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  const askDelete = (items: CatalogRow[]) => {
    const withQty = items.filter((r) => num(r.quantity) > 0).length
    setConfirm({
      title:
        items.length === 1
          ? `«${items[0].name}» o'chirilsinmi?`
          : `${items.length} ta mahsulot o'chirilsinmi?`,
      description: `${withQty ? `Diqqat: ${withQty} tasida omborda qoldiq bor. ` : ""}Kodi band qoladi va qayta berilmaydi.`,
      destructive: true,
      run: () => remove.mutate(items.map((r) => r.id)),
    })
  }
  const setTier = (items: CatalogRow[], t: "S" | "M" | "P" | "") =>
    setConfirm({
      title: `${items.length} ta dekorga: ${t ? TIER_NAME[t] : "sinfsiz"}`,
      description: t
        ? "Sotuv narxi shu sinfning list narxiga o'zgaradi (Boshqaruv paneli)."
        : "Sinf olib tashlanadi, sotuv narxi o'zgarmaydi.",
      run: () => bulk.mutate({ ids: items.map((r) => r.id), tier: t }),
    })

  const exportCsv = () =>
    downloadCsv(`nomenklatura${cat ? `-${cat}` : ""}.csv`, [
      [
        "Kod",
        "Tur",
        "Guruh kodi",
        "Guruh",
        "Nom",
        "Tavsif",
        "Birlik",
        "Qoldiq",
        "Min",
        "Joy",
        "Xarid (so'm)",
        "Xarid ($)",
        "Sotuv (so'm)",
        "Sinf",
        "Ustama %",
        "ABC",
      ],
      ...rows.map((r) => [
        r.code,
        CATALOG_NAMES[r.catalog as CatalogLetter],
        groupKey(r),
        r.group_name,
        r.name,
        r.description,
        r.unit,
        r.catalog === "X" ? "" : num(r.quantity),
        r.catalog === "X" ? "" : r.min_quantity,
        r.location,
        r.purchase_price,
        usdOf(r, rate),
        r.sale_price,
        r.tier ? TIER_NAME[r.tier] : "",
        r.catalog === "F" ? markupOf(r, pricing) : "",
        r.abc,
      ]),
    ])

  const xizmat = cat === "X"

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Nomenklatura"
        description={
          isLoading
            ? "Katalog yuklanmoqda…"
            : `${fmt(all.length)} pozitsiya · material ${fmt(byCat.M)} · furnitura ${fmt(byCat.F)} · xizmat ${fmt(byCat.X)}${byCat.S ? ` · sex ${fmt(byCat.S)}` : ""}${lowCount ? ` · kam qolgan ${lowCount}` : ""}`
        }
        actions={<GotoSearch />}
      />
      {cat === "S" && <SexTabs active="list" />}

      {cat === "M" && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Ko'rsatish
          </span>
          <SelectField
            className="h-9 w-56"
            value={zaxira}
            onChange={(v) => {
              setZaxira(v as typeof zaxira)
              resetPaging()
            }}
            options={[
              { value: "all", label: `Zaxira: hammasi (${fmt(inCat.length)})` },
              {
                value: "yes",
                label: `Zaxirada (${fmt(inCat.filter((r) => r.tracked).length)})`,
              },
              { value: "no", label: "Zaxirada emas" },
            ]}
          />
          <SelectField
            className="h-9 w-44"
            value={tierF}
            onChange={(v) => {
              setTierF(v)
              resetPaging()
            }}
            options={[
              { value: "all", label: "Sinf: hammasi" },
              ...TIERS.map(([k, n]) => ({ value: k, label: n })),
              { value: "none", label: "Sinfsiz" },
            ]}
          />
          {canWrite && tierable.length > 0 && (
            <div className="ml-auto flex flex-wrap items-center gap-1.5">
              <span className="text-muted-foreground">
                Ko'rinayotgan {fmt(tierable.length)} ta dekorga:
              </span>
              {TIERS.map(([k, n]) => (
                <Button
                  key={k}
                  size="sm"
                  onClick={() => setTier(tierable, k)}
                  disabled={bulk.isPending}
                >
                  {n}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className={cn(cardSurface, "overflow-hidden")}>
        <div className="flex flex-wrap items-center gap-2 border-b p-3">
          <SearchInput
            className="min-w-56 flex-1"
            value={q}
            onChange={(v) => {
              setQ(v)
              resetPaging()
            }}
            placeholder="Kod, nom, dekor yoki zavod artikuli"
          />
          <SelectField
            className="h-9 w-64"
            value={guruh ?? ""}
            onChange={(v) => {
              routeNavigate({
                search: v ? { guruh: v } : cat ? { katalog: cat } : {},
              })
              resetPaging()
            }}
            emptyLabel={`Barcha guruhlar (${fmt(inCat.length)})`}
            options={groups.map(([k, g]) => ({
              value: k,
              label: `${k} · ${g.name}`,
              hint: String(g.n),
            }))}
          />
          {!xizmat && (
            <Button
              size="sm"
              variant={onlyLow ? "default" : "outline"}
              onClick={() => {
                setOnlyLow(!onlyLow)
                resetPaging()
              }}
            >
              Qoldiq &lt; min
            </Button>
          )}
          <span className="ml-auto text-sm text-muted-foreground tabular-nums">
            {fmt(rows.length)} / {fmt(all.length)} qator
          </span>
          {canWrite && (
            <>
              <Button
                size="sm"
                variant="outline"
                className="text-destructive"
                disabled={!sel.length || remove.isPending}
                onClick={() => askDelete(sel)}
              >
                <Trash2 /> O'chirish
              </Button>
              <Button
                size="sm"
                onClick={() => setNewOpen(true)}
                disabled={!cat || newOpen}
                title={cat ? undefined : "Avval kategoriyani tanlang"}
              >
                <Plus /> Yangi mahsulot
              </Button>
            </>
          )}
          <Button size="sm" variant="outline" onClick={exportCsv}>
            <Download /> Excel'ga chiqarish
          </Button>
          {canWrite && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setImportOpen(true)}
            >
              <FileUp /> Excel'dan yuklash
            </Button>
          )}
        </div>

        {canWrite && sel.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 border-b bg-muted/40 px-3 py-2 text-sm">
            <b>{sel.length} ta tanlandi</b>
            {sel.some((r) => TIERABLE.has(groupKey(r))) && (
              <>
                <span className="ml-2 text-muted-foreground">Sinf:</span>
                {[...TIERS, ["", "Sinfsiz"] as const].map(([k, n]) => (
                  <Button
                    key={k || "none"}
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setTier(
                        sel.filter((r) => TIERABLE.has(groupKey(r))),
                        k as "S" | "M" | "P" | "",
                      )
                    }
                  >
                    {n}
                  </Button>
                ))}
              </>
            )}
            {sel.some((r) => r.catalog === "M") && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="ml-2"
                  onClick={() =>
                    bulk.mutate({
                      ids: sel
                        .filter((r) => r.catalog === "M")
                        .map((r) => r.id),
                      tracked: true,
                    })
                  }
                >
                  Zaxiraga olish
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    bulk.mutate({
                      ids: sel
                        .filter((r) => r.catalog === "M")
                        .map((r) => r.id),
                      tracked: false,
                    })
                  }
                >
                  Zaxiradan chiqarish
                </Button>
              </>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto"
              onClick={() => setChecked(new Set())}
            >
              Tanlovni tozalash
            </Button>
          </div>
        )}

        {newOpen && cat && data && (
          <NewItemRow
            catalog={cat}
            rows={data}
            defaultGroup={guruh}
            onClose={() => setNewOpen(false)}
          />
        )}

        {isError ? (
          <div className="p-4">
            <QueryError onRetry={() => refetch()} />
          </div>
        ) : isLoading ? (
          <div className="space-y-2 p-4">
            {["a", "b", "c", "d", "e", "f"].map((k) => (
              <Skeleton key={k} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50 text-xs uppercase">
                {canWrite && (
                  <TableHead className="w-8">
                    <Checkbox
                      aria-label="Ko'rinayotganlarni tanlash"
                      checked={
                        visible.length > 0 &&
                        visible.every((r) => checked.has(r.id))
                      }
                      onCheckedChange={(v) =>
                        setChecked((s) => {
                          const n = new Set(s)
                          for (const r of visible)
                            if (v) n.add(r.id)
                            else n.delete(r.id)
                          return n
                        })
                      }
                    />
                  </TableHead>
                )}
                <TableHead className="w-32">Kod</TableHead>
                <TableHead>Nom</TableHead>
                <TableHead className="w-16">Birlik</TableHead>
                {xizmat ? (
                  <>
                    <TableHead className="text-right">Xarajat</TableHead>
                    <TableHead className="text-right">Sotuv</TableHead>
                  </>
                ) : (
                  <>
                    <TableHead className="text-right">Qoldiq</TableHead>
                    <TableHead className="text-right">Xarid</TableHead>
                    <TableHead className="text-right">Xarid $</TableHead>
                    <TableHead className="text-right">Min</TableHead>
                    {cat === "F" && (
                      <TableHead className="w-24 text-right">
                        Ustama %
                      </TableHead>
                    )}
                    {cat === "M" && (
                      <TableHead className="w-20">Sinf</TableHead>
                    )}
                    <TableHead className="text-right">Sotuv</TableHead>
                    <TableHead className="text-right">Sotuv $</TableHead>
                    <TableHead className="w-10 text-center">ABC</TableHead>
                  </>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.length ? (
                visible.map((r) => {
                  const low = isLow(r)
                  const open = () =>
                    navigate({
                      to: "/warehouse/item/$code",
                      params: { code: r.code },
                    })
                  const usd = usdOf(r, rate)
                  return (
                    <TableRow
                      key={r.id}
                      className={cn(
                        "cursor-pointer",
                        low &&
                          "border-l-2 border-l-destructive bg-destructive/5 hover:bg-destructive/10",
                      )}
                      onClick={open}
                    >
                      {canWrite && (
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            aria-label={`${r.code} ni tanlash`}
                            checked={checked.has(r.id)}
                            onCheckedChange={() => toggle(r.id)}
                          />
                        </TableCell>
                      )}
                      <TableCell className="num text-xs text-muted-foreground">
                        {r.code}
                      </TableCell>
                      <TableCell>
                        <div className="font-semibold">{r.name}</div>
                        {r.description && (
                          <div className="text-xs text-muted-foreground">
                            {r.description}
                            {r.tracked && " · zaxirada"}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {r.unit ?? "—"}
                      </TableCell>
                      {xizmat ? (
                        <>
                          <TableCell className="num text-right text-muted-foreground">
                            {r.purchase_price != null
                              ? fmt(r.purchase_price)
                              : "—"}
                          </TableCell>
                          <TableCell className="num text-right font-semibold">
                            {r.sale_price != null ? fmt(r.sale_price) : "—"}
                          </TableCell>
                        </>
                      ) : (
                        <>
                          <TableCell
                            className={cn(
                              "num text-right font-semibold",
                              low && "text-destructive",
                            )}
                          >
                            {fmtQty(r.quantity)}
                          </TableCell>
                          <TableCell className="num text-right text-muted-foreground">
                            {r.purchase_price != null
                              ? fmt(r.purchase_price)
                              : "—"}
                          </TableCell>
                          <TableCell className="num text-right font-semibold">
                            {usd != null ? fmtUsd(usd) : "—"}
                          </TableCell>
                          <TableCell className="num text-right text-muted-foreground">
                            {r.min_quantity != null
                              ? fmtQty(r.min_quantity)
                              : "—"}
                          </TableCell>
                          {cat === "F" && (
                            <TableCell onClick={(e) => e.stopPropagation()}>
                              <MarkupInput
                                row={r}
                                placeholder={markupOf(
                                  { ...r, markup_pct: null },
                                  pricing,
                                )}
                                disabled={!canWrite}
                                onSave={(pct) =>
                                  markup.mutate({ id: r.id, pct })
                                }
                              />
                            </TableCell>
                          )}
                          {cat === "M" && (
                            <TableCell>
                              {r.tier ? (
                                <span className="rounded bg-primary px-1.5 py-0.5 text-xs font-bold text-primary-foreground">
                                  {TIER_NAME[r.tier]}
                                </span>
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </TableCell>
                          )}
                          <TableCell className="num text-right">
                            {r.sale_price != null ? fmt(r.sale_price) : "—"}
                          </TableCell>
                          <TableCell className="num text-right font-semibold">
                            {r.sale_price != null
                              ? fmtUsd(num(r.sale_price) / rate)
                              : "—"}
                          </TableCell>
                          <TableCell className="text-center font-semibold">
                            {r.abc ?? "—"}
                          </TableCell>
                        </>
                      )}
                    </TableRow>
                  )
                })
              ) : (
                <EmptyRow colSpan={13}>
                  Hech narsa topilmadi — qidiruvni yoki filtrni o'zgartiring
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        )}
        {rows.length > limit && (
          <div className="border-t p-3 text-center">
            <Button variant="outline" onClick={() => setLimit(limit + STEP)}>
              Yana {Math.min(STEP, rows.length - limit)} ta ko'rsatish ·{" "}
              {fmt(rows.length - limit)} qoldi
            </Button>
          </div>
        )}
      </div>

      {data && (
        <ImportDialog
          open={importOpen}
          onOpenChange={setImportOpen}
          rows={data}
        />
      )}
      <ConfirmDialog
        open={confirm != null}
        onOpenChange={(v) => !v && setConfirm(null)}
        title={confirm?.title ?? ""}
        description={confirm?.description}
        destructive={confirm?.destructive}
        confirmText={confirm?.destructive ? "O'chirish" : "Qo'llash"}
        loading={bulk.isPending || remove.isPending}
        onConfirm={() => {
          confirm?.run()
          setConfirm(null)
        }}
      />
    </div>
  )
}

/** Furnitura qatoridagi ustama — bo'sh qoldirilsa guruhniki (placeholder'da ko'rinadi). */
function MarkupInput({
  row,
  placeholder,
  disabled,
  onSave,
}: {
  row: CatalogRow
  placeholder: number | null
  disabled: boolean
  onSave: (pct: number | null) => void
}) {
  const saved = row.markup_pct != null ? String(num(row.markup_pct)) : ""
  const [v, setV] = useState(saved)
  const commit = () => {
    if (v === saved) return
    const p = parseNum(v)
    onSave(v.trim() === "" ? null : p)
  }
  return (
    <Input
      className="num h-7 w-20 text-right"
      inputMode="decimal"
      value={v}
      disabled={disabled}
      placeholder={placeholder != null ? String(placeholder) : "—"}
      aria-label={`${row.code} ustamasi`}
      onChange={(e) => setV(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur()
      }}
    />
  )
}
