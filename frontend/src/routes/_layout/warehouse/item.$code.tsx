// Mahsulotlar ombori — Tovar kartochkasi (dizayndagi «Tovar kartochkasi»).
//
// Qoldiq, xarid va sotuv narxi (qoldiq qiymati bilan), chegara, ustama, kod tuzilmasi, tez amallar
// (kirimga / sotuv listiga qo'shish), FIFO partiyalar (keyingi chiqim narxi) va harakat tarixi
// (docs/14 §8–9). Qo'lda qoldiq tuzatish ham harakat bo'lib yoziladi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowLeft, Pencil, Trash2 } from "lucide-react"
import { type ReactNode, useState } from "react"
import { toast } from "sonner"

import {
  type CatalogItemUpdate,
  type CatalogRow,
  CatalogService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { QueryError } from "@/components/Common/QueryError"
import { SelectField } from "@/components/Common/SelectField"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { BirlikPanel, isTracked } from "@/components/Warehouse/BirlikPanel"
import { GotoSearch } from "@/components/Warehouse/GotoSearch"
import { ItemHistory } from "@/components/Warehouse/ItemHistory"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  CATALOG_NAMES,
  type CatalogLetter,
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

export const Route = createFileRoute("/_layout/warehouse/item/$code")({
  component: ItemCard,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: ({ params }) => ({ meta: [{ title: `${params.code} | MebeliX` }] }),
})

function ItemCard() {
  const { code } = Route.useParams()
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery(
    getCatalogAllQueryOptions(),
  )
  const { data: pricing } = useQuery(getWarehousePricingQueryOptions())
  const [editing, setEditing] = useState(false)
  const [askDelete, setAskDelete] = useState(false)
  const rate = num(pricing?.usd_rate) || 12800

  const remove = useMutation({
    mutationFn: (id: number) =>
      CatalogService.deleteCatalogItems({ body: { ids: [id] } }),
    onSuccess: () => {
      toast.success(`${code} o'chirildi`)
      navigate({ to: "/warehouse", search: { katalog: code[0] } })
    },
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["catalog"] }),
  })

  if (isError) return <QueryError onRetry={() => refetch()} />
  if (isLoading || !data) return <Skeleton className="h-72 w-full" />
  const r = data.find((x) => x.code === code)
  const back = (
    <Link
      to="/warehouse"
      search={{ katalog: code[0] }}
      className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
    >
      <ArrowLeft className="size-4" /> Nomenklatura
    </Link>
  )
  if (!r)
    return (
      <div className="space-y-3">
        {back}
        <p className="text-muted-foreground">
          {code} — bunday pozitsiya yo'q yoki o'chirilgan.
        </p>
      </div>
    )

  const cat = r.catalog as CatalogLetter
  const xizmat = cat === "X"
  const usd = usdOf(r, rate)
  const mk = markupOf(r, pricing)
  const low = isLow(r)
  const [k, g, m, v] = r.code.split("-")

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Tovar kartochkasi</h1>
          <p className="text-sm text-muted-foreground">
            Qoldiq, narx va tez amallar
          </p>
        </div>
        <GotoSearch />
      </div>
      {back}

      <section className={cn(cardSurface, "space-y-4 p-5")}>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-bold">{r.name}</h2>
          {r.abc && (
            <span className="rounded border px-1.5 text-xs font-semibold">
              ABC: {r.abc}
            </span>
          )}
          {r.tier && (
            <span className="rounded bg-primary px-1.5 text-xs font-bold text-primary-foreground">
              {TIER_NAME[r.tier]}
            </span>
          )}
          {r.tracked && (
            <span className="rounded border px-1.5 text-xs">zaxirada</span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {[r.code, CATALOG_NAMES[cat], r.group_name, r.description, r.unit]
            .filter(Boolean)
            .join(" · ")}
        </p>

        <div className="grid gap-3 sm:grid-cols-3">
          {!xizmat && (
            <Stat
              label="Qoldiq"
              value={`${fmtQty(r.quantity)} ${r.unit ?? ""}`}
              danger={low}
              sub={
                low ? `chegara ${fmtQty(r.min_quantity)} dan kam` : undefined
              }
            />
          )}
          <Stat
            label={xizmat ? "Xarajat" : "Xarid narxi"}
            value={r.purchase_price != null ? fmt(r.purchase_price) : "—"}
            sub={
              r.purchase_price != null
                ? `so'm / ${r.unit ?? "dona"}${usd != null ? ` · ${fmtUsd(usd)}` : ""}`
                : undefined
            }
          />
          <Stat
            label="Sotuv narxi"
            value={r.sale_price != null ? fmt(r.sale_price) : "—"}
            sub={
              !xizmat && num(r.quantity) > 0
                ? `qoldiq qiymati ${fmt(num(r.quantity) * num(r.purchase_price ?? r.sale_price))} so'm`
                : undefined
            }
          />
        </div>

        <dl className="grid gap-3 text-sm sm:grid-cols-4">
          {!xizmat && (
            <Fact label="Min zaxira">
              {r.min_quantity != null
                ? `${fmtQty(r.min_quantity)} ${r.unit ?? ""}`
                : "—"}
            </Fact>
          )}
          {!xizmat && <Fact label="Joy">{r.location ?? "—"}</Fact>}
          {cat === "F" && (
            <Fact label="Ustama">
              {mk != null ? `${mk}%` : "—"}
              {r.markup_pct == null && mk != null && (
                <span className="text-muted-foreground"> (guruhniki)</span>
              )}
            </Fact>
          )}
          <Fact label="Kod tuzilmasi">
            <span className="num">
              {k} – {g} – {m} – {v}
            </span>
          </Fact>
        </dl>

        {canWrite && (
          <div className="flex flex-wrap gap-2 border-t pt-4">
            {!xizmat && (
              <Button asChild>
                <Link
                  to="/warehouse/doc"
                  search={{ turi: "kirim", add: r.code }}
                >
                  Kirimga qo'shish
                </Link>
              </Button>
            )}
            <Button variant="outline" asChild>
              <Link
                to="/warehouse/doc"
                search={{ turi: "chiqim", add: r.code }}
              >
                Sotuv listiga qo'shish
              </Link>
            </Button>
            <Button variant="outline" onClick={() => setEditing(!editing)}>
              <Pencil /> Tahrirlash
            </Button>
            <Button
              variant="outline"
              className="ml-auto text-destructive"
              onClick={() => setAskDelete(true)}
            >
              <Trash2 /> O'chirish
            </Button>
          </div>
        )}
        {editing && <EditForm row={r} onDone={() => setEditing(false)} />}
      </section>

      {isTracked(r) && <BirlikPanel item={r} canWrite={canWrite} />}
      {!xizmat && <ItemHistory itemId={r.id} unit={r.unit} />}

      <ConfirmDialog
        open={askDelete}
        onOpenChange={setAskDelete}
        title={`«${r.name}» o'chirilsinmi?`}
        description={`${num(r.quantity) > 0 ? `Diqqat: omborda ${fmtQty(r.quantity)} ${r.unit ?? ""} qoldiq bor. ` : ""}Kodi band qoladi va qayta berilmaydi.`}
        destructive
        confirmText="O'chirish"
        loading={remove.isPending}
        onConfirm={() => remove.mutate(r.id)}
      />
    </div>
  )
}

function Stat({
  label,
  value,
  sub,
  danger,
}: {
  label: string
  value: string
  sub?: string
  danger?: boolean
}) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {label}
      </div>
      <div
        className={cn("num text-2xl font-bold", danger && "text-destructive")}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {label}
      </dt>
      <dd className="font-semibold">{children}</dd>
    </div>
  )
}

/** Forma maydoni. Modul darajasida: render ichida e'lon qilinsa har harfda qayta yaratilib,
 *  input fokusini yo'qotardi. */
function F({
  id,
  label,
  children,
  className,
}: {
  id: string
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("space-y-1", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

/** Tahrirlash: nom, tavsif, birlik, chegara, joy, narxlar, ustama, sinf, zaxira — va qoldiq.
 *  Qoldiq o'zgarsa server uni «Qo'lda tuzatish» harakati qilib yozadi (FIFO partiya bilan). */
function EditForm({ row, onDone }: { row: CatalogRow; onDone: () => void }) {
  const queryClient = useQueryClient()
  const cat = row.catalog as CatalogLetter
  const tierable = groupKey(row) === "M-LD" || groupKey(row) === "M-LM"
  const s = (v: string | null | undefined) => (v == null ? "" : String(num(v)))
  const [f, setF] = useState({
    name: row.name,
    description: row.description ?? "",
    unit: row.unit ?? "",
    quantity: s(row.quantity),
    min: s(row.min_quantity),
    location: row.location ?? "",
    purchase: s(row.purchase_price),
    usd: s(row.purchase_usd),
    sale: s(row.sale_price),
    markup: s(row.markup_pct),
    tier: row.tier ?? "",
    tracked: row.tracked,
  })
  const save = useMutation({
    mutationFn: () => {
      const body: CatalogItemUpdate = {
        name: f.name.trim(),
        description: f.description.trim() || null,
        location: f.location.trim() || null,
        sale_price: parseNum(f.sale),
      }
      if (f.unit.trim()) body.unit = f.unit.trim()
      if (cat !== "X") {
        body.quantity = parseNum(f.quantity) ?? 0
        body.min_quantity = parseNum(f.min)
      }
      // Dollar narxi berilsa so'mdagisi undan hisoblanadi; aks holda so'mdagisi qo'lda
      if (f.usd.trim()) body.purchase_usd = parseNum(f.usd)
      else body.purchase_price = parseNum(f.purchase)
      if (cat === "F") body.markup_pct = parseNum(f.markup)
      if (tierable) body.tier = (f.tier || null) as CatalogItemUpdate["tier"]
      if (cat === "M") body.tracked = f.tracked
      return CatalogService.updateCatalogItem({
        path: { item_id: row.id },
        body,
      })
    },
    onSuccess: () => {
      toast.success("Saqlandi")
      onDone()
    },
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["catalog"] }),
  })
  const field =
    (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setF({ ...f, [k]: e.target.value })
  return (
    <form
      className="grid gap-3 rounded-md border bg-muted/30 p-4 sm:grid-cols-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (!f.name.trim()) toast.error("Nom bo'sh bo'lmasin")
        else save.mutate()
      }}
    >
      <F id="e-name" label="Nom" className="sm:col-span-3">
        <Input id="e-name" value={f.name} onChange={field("name")} />
      </F>
      <F id="e-unit" label="Birlik">
        <Input id="e-unit" value={f.unit} onChange={field("unit")} />
      </F>
      <F id="e-desc" label="Tavsif" className="sm:col-span-4">
        <Input
          id="e-desc"
          value={f.description}
          onChange={field("description")}
        />
      </F>
      {cat !== "X" && (
        <>
          <F id="e-qty" label="Qoldiq (tuzatish)">
            <Input
              id="e-qty"
              inputMode="decimal"
              value={f.quantity}
              onChange={field("quantity")}
            />
          </F>
          <F id="e-min" label="Min zaxira">
            <Input
              id="e-min"
              inputMode="decimal"
              value={f.min}
              onChange={field("min")}
            />
          </F>
          <F id="e-loc" label="Joy" className="sm:col-span-2">
            <Input id="e-loc" value={f.location} onChange={field("location")} />
          </F>
        </>
      )}
      <F id="e-pur" label={cat === "X" ? "Xarajat, so'm" : "Xarid, so'm"}>
        <Input
          id="e-pur"
          inputMode="decimal"
          value={f.purchase}
          onChange={field("purchase")}
          disabled={!!f.usd.trim()}
        />
      </F>
      {cat !== "X" && (
        <F id="e-usd" label="Xarid, $">
          <Input
            id="e-usd"
            inputMode="decimal"
            value={f.usd}
            onChange={field("usd")}
            placeholder="bo'sh — so'mda"
          />
        </F>
      )}
      <F id="e-sale" label="Sotuv, so'm">
        <Input
          id="e-sale"
          inputMode="decimal"
          value={f.sale}
          onChange={field("sale")}
          placeholder={cat === "F" ? "ustamadan" : undefined}
        />
      </F>
      {cat === "F" && (
        <F id="e-mk" label="Ustama, %">
          <Input
            id="e-mk"
            inputMode="decimal"
            value={f.markup}
            onChange={field("markup")}
            placeholder="bo'sh — guruhniki"
          />
        </F>
      )}
      {tierable && (
        <F id="e-tier" label="Sinf">
          <SelectField
            value={f.tier}
            onChange={(v) => setF({ ...f, tier: v })}
            emptyLabel="Sinfsiz"
            options={TIERS.map(([k, n]) => ({ value: k, label: n }))}
          />
        </F>
      )}
      {cat === "M" && (
        <div className="flex items-center gap-2 self-end pb-2 text-sm">
          <Checkbox
            id="e-tracked"
            checked={f.tracked}
            onCheckedChange={(v) => setF({ ...f, tracked: v === true })}
          />
          <Label htmlFor="e-tracked">
            Zaxiraga olingan (kam qoldiq ogohlantirishi)
          </Label>
        </div>
      )}
      <div className="flex gap-2 sm:col-span-4">
        <Button type="submit" disabled={save.isPending}>
          Saqlash
        </Button>
        <Button type="button" variant="outline" onClick={onDone}>
          Bekor qilish
        </Button>
      </div>
    </form>
  )
}
