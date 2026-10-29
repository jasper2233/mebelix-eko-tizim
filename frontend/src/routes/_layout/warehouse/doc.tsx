// Mahsulotlar ombori — Sotuv (chiqim) va Kirim hujjati (docs/14 §9, «Qudrat Ombor» dizayni).
//
// Klaviatura oqimi dizayndagidek: nom → (taklif, ↑↓) Enter → soni → Enter → keyingi qator; F9 — tasdiqlash,
// Ctrl+S — qoralama, Ctrl+Enter — yangi qator, Esc — takliflarni yopish. F2 / F4 — yangi sotuv / kirim
// (`routes/_layout.tsx`, har ombor sahifasida).
//
// Qoralama tasdiqlanmaguncha qoldiq o'zgarmaydi. Saqlangan qoralama «Hujjatlar» dan ochiladi
// (`?id=`); tasdiqlangan hujjat — faqat ko'rish (qulflangan). Hali saqlanmagan ish brauzerda turadi
// (sahifa yangilansa yo'qolmasin) — har tur uchun alohida.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createFileRoute,
  Link,
  Navigate,
  useNavigate,
} from "@tanstack/react-router"
import { FileUp, Plus, Printer, X } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import {
  type CatalogRow,
  type DocIn,
  type DocRead,
  StockService,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { Textarea } from "@/components/ui/textarea"
import { isTracked } from "@/components/Warehouse/BirlikPanel"
import { GotoSearch } from "@/components/Warehouse/GotoSearch"
import { SexTabs } from "@/components/Warehouse/SexTabs"
import { Shartnoma, type ShartnomaRow } from "@/components/Warehouse/Shartnoma"
import { StornoButton } from "@/components/Warehouse/StornoButton"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  CATALOG_NAMES,
  type CatalogLetter,
  fmt,
  fmtQty,
  groupKey,
  num,
  parseNum,
  SEX_FROM_F,
  usdOf,
} from "@/lib/warehouse"
import {
  getCatalogAllQueryOptions,
  getWarehousePricingQueryOptions,
} from "@/queries/mes"
import { handleError } from "@/utils"

type Kind = "kirim" | "chiqim" | "sex"

export const Route = createFileRoute("/_layout/warehouse/doc")({
  component: DocPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Hujjat | MebeliX" }] }),
  validateSearch: (
    s: Record<string, unknown>,
  ): { turi: Kind | "inv"; id?: number; add?: string } => ({
    // `inv` — faqat tasdiqlangan inventarizatsiyani ko'rish (`?id=`), yangisi `/warehouse/inv` da
    turi:
      s.turi === "kirim" || s.turi === "sex" || s.turi === "inv"
        ? s.turi
        : "chiqim",
    id: typeof s.id === "number" && s.id > 0 ? s.id : undefined,
    add: typeof s.add === "string" && s.add ? s.add : undefined,
  }),
})

type Line = {
  key: number
  item_id: number | null
  name: string
  qty: string
  price: string
  disc: string
  note: string
  //: Kirim, metrdagi pozitsiya: bitta rulon uzunligi (bo'sh — katalogdagi)
  hajm: string
}
type Draft = {
  id?: number
  no?: string
  kind: Kind
  doc_date: string
  head: Record<string, string>
  lines: Line[]
}

let lineKey = 0
const blankLine = (): Line => ({
  key: ++lineKey,
  item_id: null,
  name: "",
  qty: "",
  price: "",
  disc: "",
  note: "",
  hajm: "",
})
const today = () => new Date().toLocaleDateString("sv-SE")
const blank = (kind: Kind, me: string, rate?: string): Draft => ({
  kind,
  doc_date: today(),
  head:
    kind === "kirim"
      ? { receiver: me, rate: rate ?? "" }
      : kind === "sex"
        ? { giver: me }
        : { seller: me },
  lines: [blankLine(), blankLine(), blankLine()],
})
const storeKey = (k: Kind) => `mebelix.ombor.hujjat.${k}`
const loadLocal = (k: Kind): Draft | null => {
  try {
    const d = JSON.parse(localStorage.getItem(storeKey(k)) ?? "null")
    if (d && Array.isArray(d.lines)) {
      for (const l of d.lines) l.key = ++lineKey
      return d
    }
  } catch {
    /* brauzer xotirasi yopiq — bo'sh hujjat */
  }
  return null
}
const saveLocal = (d: Draft) => {
  try {
    localStorage.setItem(storeKey(d.kind), JSON.stringify(d))
  } catch {
    /* saqlanmasa ham ish davom etadi */
  }
}
const clearLocal = (k: Kind) => {
  try {
    localStorage.removeItem(storeKey(k))
  } catch {
    /* ahamiyatsiz */
  }
}

const fromServer = (d: DocRead): Draft => ({
  id: d.id,
  no: d.no,
  kind: d.kind as Kind,
  doc_date: d.doc_date,
  head: d.head,
  lines: [
    ...d.lines.map((l) => ({
      key: ++lineKey,
      item_id: l.item_id,
      name: l.name,
      qty: num(l.qty) ? String(num(l.qty)) : "",
      price: num(l.price) ? String(num(l.price)) : "",
      disc: num(l.discount) ? String(num(l.discount)) : "",
      note: l.note,
      hajm: l.hajm != null ? String(num(l.hajm)) : "",
    })),
    blankLine(),
  ],
})

const units = (l: Line) => parseNum(l.qty) ?? 0
const lineSum = (l: Line) => {
  const g = units(l) * (parseNum(l.price) ?? 0)
  return Math.max(0, g - Math.min(parseNum(l.disc) ?? 0, g))
}
const used = (l: Line) => !!l.item_id || !!l.name.trim() || units(l) > 0

function DocPage() {
  const { turi, id, add } = Route.useSearch()
  const { currentUser } = useCurrentUser()
  const me = currentUser?.name || currentUser?.username || ""
  const docQ = useQuery({
    queryKey: ["stock", "doc", id],
    queryFn: async () =>
      (await StockService.readStockDoc({ path: { doc_id: id as number } }))
        .data,
    enabled: id != null,
  })
  const { data: catalog } = useQuery(getCatalogAllQueryOptions())
  const { data: pricing } = useQuery(getWarehousePricingQueryOptions())

  if (id != null) {
    if (docQ.isError) return <QueryError onRetry={() => docQ.refetch()} />
    if (!docQ.data || !catalog) return <Skeleton className="h-96 w-full" />
    // Tasdiqlangan va storno qilingan (EKO 2.4) hujjat — faqat ko'rish; tahrir faqat qoralamada
    if (docQ.data.status !== "draft") return <ReadOnlyDoc doc={docQ.data} />
    return (
      <Editor
        key={`d${docQ.data.id}`}
        initial={fromServer(docQ.data)}
        catalog={catalog}
        rate={num(pricing?.usd_rate) || 12800}
        me={me}
      />
    )
  }
  if (turi === "inv") return <Navigate to="/warehouse/inv" />
  if (!catalog || !pricing) return <Skeleton className="h-96 w-full" />
  const rate = String(num(pricing.usd_rate) || 12800)
  return (
    <Editor
      key={`new-${turi}`}
      initial={loadLocal(turi) ?? blank(turi, me, rate)}
      catalog={catalog}
      rate={num(rate)}
      me={me}
      addCode={add}
    />
  )
}

function Editor({
  initial,
  catalog,
  rate: globalRate,
  me,
  addCode,
}: {
  initial: Draft
  catalog: CatalogRow[]
  rate: number
  me: string
  addCode?: string
}) {
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [doc, setDoc] = useState<Draft>(initial)
  const [active, setActive] = useState<number | null>(null)
  const [sugIx, setSugIx] = useState(0)
  const [err, setErr] = useState("")
  const [contract, setContract] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const isK = doc.kind === "kirim"
  // Sexga kirim: narx — tannarx (FIFO, tasdiqda aniqlanadi), chegirma va shartnoma yo'q
  const isSx = doc.kind === "sex"
  const isC = doc.kind === "chiqim"
  const byId = useMemo(() => new Map(catalog.map((r) => [r.id, r])), [catalog])
  const rate = isK ? parseNum(doc.head.rate ?? "") || globalRate : globalRate
  const added = useRef(false)

  // Yangi (saqlanmagan) hujjat brauzerda turadi — sahifa yangilansa yo'qolmasin
  useEffect(() => {
    if (doc.id == null) saveLocal(doc)
  }, [doc])

  const focus = (sel: string) =>
    setTimeout(() => {
      const el = document.querySelector<HTMLInputElement>(sel)
      el?.focus()
      el?.select()
    }, 30)

  const priceOf = (r: CatalogRow) =>
    isK
      ? (usdOf(r, rate) ?? 0)
      : isSx
        ? num(r.purchase_price)
        : num(r.sale_price)
  const mergeLine = (lines: Line[], r: CatalogRow, q: number): Line[] => {
    const ex = lines.find((l) => l.item_id === r.id)
    if (ex)
      return lines.map((l) =>
        l === ex ? { ...l, qty: String(units(l) + q) } : l,
      )
    const nl: Line = {
      ...blankLine(),
      item_id: r.id,
      name: r.name,
      qty: String(q),
      price: String(priceOf(r) || ""),
    }
    const ix = lines.findIndex((l) => !used(l))
    return ix > -1
      ? lines.map((l, i) => (i === ix ? { ...nl, key: l.key } : l))
      : [...lines, nl]
  }

  // Kartochkadan «Kirimga / Sotuv listiga qo'shish» — `?add=F-RC-001-01`. Faqat BIR MARTA, ochilganda
  // biome-ignore lint/correctness/useExhaustiveDependencies: boshqa qiymatlar o'zgarsa qayta qo'shmasin
  useEffect(() => {
    if (!addCode || added.current) return
    added.current = true
    const r = catalog.find((x) => x.code === addCode)
    if (r) setDoc((d) => ({ ...d, lines: mergeLine(d.lines, r, 1) }))
    navigate({
      to: "/warehouse/doc",
      search: { turi: doc.kind },
      replace: true,
    })
  }, [addCode])

  const setLine = (key: number, patch: Partial<Line>) => {
    setErr("")
    setDoc((d) => ({
      ...d,
      lines: d.lines.map((l) => (l.key === key ? { ...l, ...patch } : l)),
    }))
  }
  const setHead = (k: string, v: string) => {
    setErr("")
    setDoc((d) => ({ ...d, head: { ...d.head, [k]: v } }))
  }
  const addBlank = () => {
    const nl = blankLine()
    setDoc((d) => ({ ...d, lines: [...d.lines, nl] }))
    focus(`[data-line-name="${nl.key}"]`)
  }

  const body = (): DocIn => ({
    id: doc.id ?? null,
    kind: doc.kind,
    doc_date: doc.doc_date,
    head: doc.head,
    lines: doc.lines.filter(used).map((l) => ({
      item_id: l.item_id,
      name:
        l.name.trim() || (l.item_id ? (byId.get(l.item_id)?.name ?? "") : ""),
      qty: units(l),
      price: parseNum(l.price) ?? 0,
      discount: isK ? 0 : (parseNum(l.disc) ?? 0),
      note: l.note,
      hajm: isK && parseNum(l.hajm) ? parseNum(l.hajm) : null,
    })),
  })
  const reset = () => {
    clearLocal(doc.kind)
    setDoc(blank(doc.kind, me, isK ? String(globalRate) : undefined))
    setErr("")
    navigate({ to: "/warehouse/doc", search: { turi: doc.kind } })
    focus("[data-line-name]")
  }
  const done = () => {
    queryClient.invalidateQueries({ queryKey: ["catalog"] })
    queryClient.invalidateQueries({ queryKey: ["stock"] })
  }
  const save = useMutation({
    mutationFn: async () =>
      (await StockService.saveStockDoc({ body: body() })).data,
    onSuccess: (d) => {
      toast.success(
        `${d.no} qoralama sifatida saqlandi · Hujjatlar bo'limidan ochiladi`,
      )
      done()
      reset()
    },
    onError: handleError,
  })
  const confirmM = useMutation({
    mutationFn: async () => {
      const r = await StockService.confirmStockDoc({
        body: body(),
        throwOnError: false,
      })
      if (r.error) {
        const detail = (r.error as { detail?: unknown }).detail
        throw new Error(typeof detail === "string" ? detail : "Tasdiqlanmadi")
      }
      return r.data as DocRead
    },
    onSuccess: (d) => {
      const profit =
        d.cogs != null
          ? ` · FIFO tannarx ${fmt(d.cogs)} · foyda ${fmt(num(d.total) - num(d.cogs))}`
          : ""
      toast.success(
        `${d.no} tasdiqlandi · ${fmt(d.total)} so'm${profit} — yangi list ochildi`,
      )
      done()
      reset()
    },
    onError: (e: Error) => setErr(e.message),
  })
  const busy = save.isPending || confirmM.isPending
  const usedLines = doc.lines.filter(used)

  const runSave = () => {
    if (!usedLines.length)
      toast.warning("Saqlash uchun kamida bitta qator kiriting")
    else save.mutate()
  }
  const runConfirm = () => {
    if (!busy) confirmM.mutate()
  }

  useEffect(() => {
    if (!canWrite) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "F9") {
        e.preventDefault()
        runConfirm()
      } else if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
        e.preventDefault()
        runSave()
      } else if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault()
        addBlank()
      } else if (e.key === "Escape" && active != null) {
        setActive(null)
        ;(document.activeElement as HTMLElement | null)?.blur()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  // Pozitsiya bo'yicha jami — chiqimda qoldiqdan oshsa qator qizil
  const need = new Map<number, number>()
  for (const l of usedLines)
    if (l.item_id) need.set(l.item_id, (need.get(l.item_id) ?? 0) + units(l))

  const sums = { M: 0, F: 0, X: 0, S: 0 }
  let gross = 0
  let disc = 0
  for (const l of usedLines) {
    const r = l.item_id ? byId.get(l.item_id) : undefined
    const g = units(l) * (parseNum(l.price) ?? 0)
    gross += g
    disc += Math.min(parseNum(l.disc) ?? 0, g)
    if (r) sums[r.catalog as CatalogLetter] += lineSum(l)
  }
  const jami = isK ? gross : gross - disc

  const F = (
    label: string,
    k: string,
    opts: { ph?: string; type?: string; big?: boolean } = {},
  ) => (
    <div className="space-y-1">
      <label
        htmlFor={`h-${k}`}
        className="block text-[11px] font-semibold tracking-wide text-muted-foreground uppercase"
      >
        {label}
      </label>
      <Input
        id={`h-${k}`}
        type={opts.type ?? "text"}
        value={k === "doc_date" ? doc.doc_date : (doc.head[k] ?? "")}
        placeholder={opts.ph}
        className={cn("h-9", opts.big && "font-semibold")}
        disabled={!canWrite}
        onChange={(e) =>
          k === "doc_date"
            ? setDoc((d) => ({ ...d, doc_date: e.target.value }))
            : setHead(k, e.target.value)
        }
      />
    </div>
  )

  const title = isK
    ? "Kirim listi"
    : isSx
      ? "Sexga kirim listi"
      : "Sotuv listi (chiqim)"

  if (contract && isC)
    return (
      <div className="flex flex-col gap-4">
        <div className="flex gap-2 print:hidden">
          <Button variant="outline" onClick={() => setContract(false)}>
            Listga qaytish
          </Button>
          <Button onClick={() => window.print()}>
            <Printer /> Chop etish
          </Button>
        </div>
        <Shartnoma
          head={{
            client: doc.head.client ?? "",
            phone: doc.head.phone ?? "",
            order: doc.head.order ?? "",
            seller: doc.head.seller ?? "",
            dateISO: doc.doc_date,
            dueISO: doc.head.due ?? "",
          }}
          rows={contractRows(usedLines, byId)}
          jami={jami}
        />
      </div>
    )

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Hujjat"
        description="Qoralama — tasdiqlanmaguncha qoldiq o'zgarmaydi"
        actions={<GotoSearch />}
      />
      {isSx && <SexTabs active="give" />}
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-bold">{title}</h2>
        <span className="num text-sm text-muted-foreground">
          {doc.no ?? "yangi"}
        </span>
        <span className="rounded bg-muted px-1.5 text-xs font-semibold tracking-wide uppercase">
          Qoralama
        </span>
        <div className="ml-auto flex gap-2">
          {isC && (
            <Button variant="outline" onClick={() => setContract(true)}>
              Shartnoma
            </Button>
          )}
          {canWrite && (
            <Button variant="outline" onClick={() => setImportOpen(true)}>
              <FileUp /> Excel'dan yuklash
            </Button>
          )}
        </div>
      </div>

      <div className="grid max-w-6xl gap-3 md:grid-cols-2">
        <section className={cn(cardSurface, "space-y-3 p-4")}>
          <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {isK ? "Yetkazib beruvchi" : isSx ? "Kim oldi" : "Mijoz"}
          </h3>
          {isSx ? (
            <>
              {F("Kim oldi (usta)", "taker", {
                ph: "Masalan: Bobur usta",
                big: true,
              })}
              {F("Qaysi uskuna / uchastka uchun", "equip", {
                ph: "Masalan: Raspil stanogi, CNC, kromka stanogi",
              })}
              {F("Izoh", "note", {
                ph: "Masalan: disk sinib qoldi, almashtirildi",
              })}
            </>
          ) : isK ? (
            <>
              {F("Yetkazib beruvchi", "supplier", {
                ph: "Masalan: Ningbo Haitian Hardware",
                big: true,
              })}
              {F("Telefon", "phone", { ph: "+998 __ ___ __ __" })}
              {F("Izoh", "note", { ph: "Masalan: 2 quti zaxira keldi" })}
            </>
          ) : (
            <>
              {F("F.I.Sh. / tashkilot", "client", {
                ph: "Masalan: Jahongir Rustamov",
                big: true,
              })}
              {F("Telefon", "phone", { ph: "+998 __ ___ __ __" })}
              {F("Manzil / yetkazib berish", "addr", {
                ph: "Shahar, tuman, ko'cha, uy",
              })}
            </>
          )}
        </section>
        <section className={cn(cardSurface, "grid grid-cols-2 gap-3 p-4")}>
          <h3 className="col-span-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {isK || isSx ? "Hujjat" : "Buyurtma"}
          </h3>
          {isSx ? (
            <>
              <div className="col-span-2">
                {F("Buyurtma / loyiha №", "order", {
                  ph: "ixtiyoriy",
                  big: true,
                })}
              </div>
              {F("Berdi (omborchi)", "giver")}
              {F("Sana", "doc_date", { type: "date" })}
            </>
          ) : isK ? (
            <>
              <div className="col-span-2">
                {F("Dollar kursi · 1 $ = so'm", "rate", {
                  ph: String(globalRate),
                  big: true,
                })}
              </div>
              {F("Faktura №", "invoice", { ph: "NH-0000", big: true })}
              {F("Qabul qildi (xodim)", "receiver")}
              {F("Sana", "doc_date", { type: "date" })}
              {F("To'lov muddati", "due", { type: "date" })}
            </>
          ) : (
            <>
              {F("Buyurtma №", "order", { ph: "B-2026-000", big: true })}
              {F("Sotuvchi (xodim)", "seller")}
              {F("Sana", "doc_date", { type: "date" })}
              {F("Topshirish muddati", "due", { type: "date" })}
            </>
          )}
        </section>
      </div>

      <section className={cn(cardSurface, "max-w-6xl overflow-visible")}>
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="font-semibold">Mahsulotlar</h3>
          <span className="text-sm text-muted-foreground">
            {usedLines.length} ta qator · <b>JAMI</b>{" "}
            <b className="num text-lg text-foreground">
              {isK ? `${jami.toFixed(2)} $` : fmt(jami)}
            </b>{" "}
            {isK ? `≈ ${fmt(jami * rate)} so'm` : "so'm"}
          </span>
        </div>
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 text-xs uppercase">
              <TableHead className="w-8">№</TableHead>
              {/* Nom — eng muhim ustun: qolgan ustunlar toraytirilib, joy unga berilgan
                  (2026-10-18, omborchi: «nomi ko'rinmay qolyapti») */}
              <TableHead className="min-w-[22rem]">Mahsulot nomi</TableHead>
              <TableHead className="w-20 text-right">Soni</TableHead>
              <TableHead className="w-24 text-right">
                {isK ? "Narx, $" : isSx ? "Tannarx" : "Narxi"}
              </TableHead>
              {isC && (
                <TableHead className="w-24 text-right">Chegirma</TableHead>
              )}
              <TableHead className="w-28 text-right">Summa</TableHead>
              <TableHead className="w-36">Izoh</TableHead>
              <TableHead className="w-8" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {doc.lines.map((l, ix) => (
              <LineRow
                key={l.key}
                no={ix + 1}
                line={l}
                kind={doc.kind}
                rate={rate}
                catalog={catalog}
                item={l.item_id ? byId.get(l.item_id) : undefined}
                need={l.item_id ? (need.get(l.item_id) ?? 0) : 0}
                active={active === l.key}
                sugIx={sugIx}
                isLast={ix === doc.lines.length - 1}
                disabled={!canWrite}
                onFocus={() => {
                  setActive(l.key)
                  setSugIx(0)
                }}
                onBlur={() => setActive(null)}
                setSugIx={setSugIx}
                onChange={(p) => setLine(l.key, p)}
                onPick={(r) => {
                  setLine(l.key, {
                    item_id: r.id,
                    name: r.name,
                    price: l.price || String(priceOf(r) || ""),
                    qty: l.qty || "1",
                  })
                  setActive(null)
                  // DARHOL (timeout'siz): tez yozuvchi yoki skanerning keyingi belgisi nom
                  // maydoniga tushib, tanlovni buzmasin — soni maydoni allaqachon chizilgan
                  const q = document.querySelector<HTMLInputElement>(
                    `[data-line-qty="${l.key}"]`,
                  )
                  q?.focus()
                  q?.select()
                }}
                onNext={() => {
                  const nxt = doc.lines[ix + 1]
                  if (nxt) focus(`[data-line-name="${nxt.key}"]`)
                  else addBlank()
                }}
                onDelete={() =>
                  setDoc((d) => ({
                    ...d,
                    lines:
                      d.lines.length > 1
                        ? d.lines.filter((x) => x.key !== l.key)
                        : [blankLine()],
                  }))
                }
              />
            ))}
          </TableBody>
        </Table>
        <div className="flex flex-wrap items-center gap-3 border-t bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
          {canWrite && (
            <Button size="sm" variant="outline" onClick={addBlank}>
              <Plus /> Yangi qator
            </Button>
          )}
          Nom → Enter → soni → Enter → keyingi qator · ↑↓ ro'yxatda · F9 —
          tasdiqlash · Ctrl+S — qoralama · Esc — yopish
        </div>
      </section>

      {err && (
        <div className="max-w-6xl rounded-md border border-destructive bg-destructive/5 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      <div className="flex max-w-6xl flex-wrap items-end justify-between gap-6">
        <div className="flex gap-10 text-sm">
          {(isK
            ? ["Qabul qildi (omborchi)", "Topshirdi (yetkazib beruvchi)"]
            : isSx
              ? ["Berdi (omborchi)", "Oldi (usta)"]
              : ["Sotuvchi imzosi", "Mijoz imzosi"]
          ).map((s) => (
            <div key={s} className="w-44 border-b pb-1 text-muted-foreground">
              {s}
            </div>
          ))}
        </div>
        <section
          className={cn(cardSurface, "w-full max-w-sm space-y-2 p-4 text-sm")}
        >
          {isC &&
            (["M", "F", "X"] as const).map((c) => (
              <div key={c} className="flex justify-between">
                <span>
                  <span className="mr-1.5 rounded bg-muted px-1 text-xs font-bold">
                    {c}
                  </span>
                  {CATALOG_NAMES[c]}lar
                </span>
                <span className="num">{fmt(sums[c])}</span>
              </div>
            ))}
          <div className="flex justify-between border-t pt-2">
            <span>Mahsulotlar summasi</span>
            <b className="num">{isK ? `$${gross.toFixed(2)}` : fmt(gross)}</b>
          </div>
          {isC && (
            <div className="flex justify-between">
              <span>Chegirma</span>
              <span className="num text-primary">− {fmt(disc)}</span>
            </div>
          )}
          <div className="flex items-baseline justify-between border-t pt-2">
            <b className="text-xs tracking-wide uppercase">
              {isSx ? "Jami tannarx" : "Jami summa"}
            </b>
            <b className="num text-2xl">
              {isK ? `${jami.toFixed(2)} $` : fmt(jami)}{" "}
              <span className="text-xs font-normal">{isK ? "" : "so'm"}</span>
            </b>
          </div>
          {isK && (
            <div className="flex justify-between text-muted-foreground">
              <span>So'mda · kurs {fmt(rate)}</span>
              <b className="num text-foreground">{fmt(jami * rate)} so'm</b>
            </div>
          )}
          {canWrite && (
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                className="text-destructive"
                onClick={reset}
                disabled={busy}
              >
                Tozalash
              </Button>
              <Button variant="outline" onClick={runSave} disabled={busy}>
                Saqlash{" "}
                <kbd className="ml-1 rounded border px-1 text-[10px]">
                  Ctrl+S
                </kbd>
              </Button>
              <Button
                className="flex-1"
                onClick={runConfirm}
                disabled={busy || !usedLines.length}
              >
                Tasdiqlash{" "}
                <kbd className="ml-1 rounded border px-1 text-[10px]">F9</kbd>
              </Button>
            </div>
          )}
        </section>
      </div>

      <ImportLinesDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        catalog={catalog}
        isK={isK}
        onApply={(rows) =>
          setDoc((d) => {
            let lines = d.lines
            for (const { r, q } of rows) lines = mergeLine(lines, r, q)
            return { ...d, lines }
          })
        }
      />
    </div>
  )
}

function contractRows(
  lines: Line[],
  byId: Map<number, CatalogRow>,
): ShartnomaRow[] {
  return lines.map((l) => {
    const r = l.item_id ? byId.get(l.item_id) : undefined
    return {
      key: l.key,
      name: l.name,
      note: l.note,
      code: r?.code,
      unit: r?.unit,
      qty: units(l),
      price: parseNum(l.price) ?? 0,
      sum: lineSum(l),
    }
  })
}

function LineRow({
  no,
  line: l,
  kind,
  rate,
  catalog,
  item,
  need,
  active,
  sugIx,
  isLast,
  disabled,
  onFocus,
  onBlur,
  setSugIx,
  onChange,
  onPick,
  onNext,
  onDelete,
}: {
  no: number
  line: Line
  kind: Kind
  rate: number
  catalog: CatalogRow[]
  item: CatalogRow | undefined
  need: number
  active: boolean
  sugIx: number
  //: Oxirgi qatormi — undan Tab bilan chiqilganda yangi qator ochiladi
  isLast: boolean
  disabled: boolean
  onFocus: () => void
  onBlur: () => void
  setSugIx: (n: number) => void
  onChange: (p: Partial<Line>) => void
  onPick: (r: CatalogRow) => void
  onNext: () => void
  onDelete: () => void
}) {
  const isK = kind === "kirim"
  const isSx = kind === "sex"
  const t = l.name.trim().toLowerCase()
  // Sexga — sex xo'jaligi va asbob/kley furniturasi; kirimga — xizmatsiz; sotuvga — sex mahsulotisiz
  const allowed = (r: CatalogRow) =>
    isSx
      ? r.catalog === "S" || SEX_FROM_F.has(groupKey(r))
      : isK
        ? r.catalog !== "X"
        : r.catalog !== "S"
  // Qidiruv so'zlarga bo'linadi va HAMMASI topilishi kerak: «ldsp beliy» ham, «beliy ldsp» ham
  // ishlaydi. Bitta belgidan boshlanadi — omborchi ko'pincha kodning boshini («f-rc») yoki
  // nomning birinchi harfini teradi.
  const sozlar = t.split(/\s+/).filter(Boolean)
  const mos =
    active && !item && sozlar.length
      ? catalog.filter((r) => {
          if (!allowed(r)) return false
          const xas =
            `${r.code} ${r.name} ${r.decor_name ?? ""} ${r.article ?? ""}`.toLowerCase()
          return sozlar.every((w) => xas.includes(w))
        })
      : []
  // Ekranga chiziladigani cheklangan: bitta harf 1 700 dan ortiq pozitsiyaga mos keladi va
  // har bosishda shuncha tugma chizish tsexdagi kompyuterni sekinlashtiradi. Nechtasi
  // topilgani qator ostida AYTILADI — «topilmadi» degan taassurot qolmasin. Oyna
  // aylantiriladi (ilgari 6 tasi ko'rinardi va qolgani yo'qdek tuyulardi).
  const sug = mos.slice(0, SUG_MAX)
  const six = Math.min(sugIx, Math.max(0, sug.length - 1))
  const svc = item?.catalog === "X"
  const q = units(l)
  const bad = !isK && !!item && !svc && need > num(item.quantity)
  const unknown = !item && !!t
  const meta = svc
    ? `${item.code} · xizmat — omborga ta'sir qilmaydi`
    : item
      ? `${item.code} · omborda ${fmtQty(item.quantity)} ${item.unit ?? ""}${q ? ` → ${fmtQty(isK ? num(item.quantity) + q : num(item.quantity) - q)}` : ""}`
      : unknown
        ? mos.length
          ? `${mos.length} ta topildi · ↑↓ va Enter${mos.length > sug.length ? ` · ${sug.length} tasi ko'rinadi, yozishni davom ettiring` : ""}`
          : "Nomenklaturada topilmadi"
        : ""
  const s = lineSum(l)
  return (
    <TableRow
      className={cn(
        (bad || (unknown && !active)) &&
          "border-l-2 border-l-destructive bg-destructive/5",
      )}
    >
      <TableCell className="num text-muted-foreground">{no}</TableCell>
      <TableCell className="relative">
        <Input
          data-line-name={l.key}
          className="h-8"
          placeholder="Mahsulot nomi yoki kod"
          value={l.name}
          disabled={disabled}
          onFocus={onFocus}
          onBlur={onBlur}
          onChange={(e) => {
            const v = e.target.value
            const exact = catalog.find(
              (r) =>
                r.code.toLowerCase() === v.trim().toLowerCase() ||
                r.name.toLowerCase() === v.trim().toLowerCase(),
            )
            onChange({
              name: v,
              item_id: exact && allowed(exact) ? exact.id : null,
            })
            onFocus()
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown" && sug.length) {
              e.preventDefault()
              setSugIx((six + 1) % sug.length)
            } else if (e.key === "ArrowUp" && sug.length) {
              e.preventDefault()
              setSugIx((six - 1 + sug.length) % sug.length)
            } else if (e.key === "Tab" && !e.shiftKey && sug.length) {
              e.preventDefault()
              onPick(sug[six])
            } else if (e.key === "Enter") {
              e.preventDefault()
              if (sug.length) onPick(sug[six])
              else if (item)
                document
                  .querySelector<HTMLInputElement>(`[data-line-qty="${l.key}"]`)
                  ?.focus()
            }
          }}
        />
        {meta && (
          <div
            className={cn(
              "mt-0.5 text-[11px]",
              bad || (unknown && !sug.length)
                ? "text-destructive"
                : "text-muted-foreground",
            )}
          >
            {meta}
          </div>
        )}
        {sug.length > 0 && (
          <div className="absolute top-full left-2 z-20 max-h-72 w-[min(36rem,90vw)] overflow-y-auto rounded-md border bg-popover shadow-lg">
            {sug.map((r, n) => (
              <button
                key={r.id}
                type="button"
                // Klaviatura bilan tanlangan qator oynadan chiqib ketmasin
                ref={(el) => {
                  if (n === six) el?.scrollIntoView({ block: "nearest" })
                }}
                className={cn(
                  "flex w-full items-center gap-3 px-3 py-1.5 text-left text-sm",
                  n === six && "bg-accent",
                )}
                onMouseDown={(e) => {
                  e.preventDefault()
                  onPick(r)
                }}
              >
                <span className="num w-28 shrink-0 text-xs text-muted-foreground">
                  {r.code}
                </span>
                <span className="min-w-0 flex-1 truncate">{r.name}</span>
                <span className="num text-xs text-muted-foreground">
                  {r.catalog === "X"
                    ? `xizmat · ${fmt(r.sale_price)}`
                    : `${fmtQty(r.quantity)} ${r.unit ?? ""}`}
                </span>
              </button>
            ))}
          </div>
        )}
      </TableCell>
      <TableCell>
        <Input
          data-line-qty={l.key}
          className={cn(
            "num h-8 text-right",
            bad && "font-bold text-destructive",
          )}
          inputMode="decimal"
          placeholder="0"
          value={l.qty}
          disabled={disabled}
          onFocus={(e) => e.target.select()}
          onChange={(e) =>
            onChange({ qty: e.target.value.replace(/[^0-9.,]/g, "") })
          }
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault()
              onNext()
            }
          }}
        />
        {isK && item?.unit === "metr" && (
          // Har rulon alohida barkod oladi (EKO TZ §4.4): miqdor shu uzunlik bo'yicha rulonlarga bo'linadi
          <Input
            className="num mt-1 h-7 text-right text-xs"
            inputMode="decimal"
            placeholder={
              item.birlik_hajm != null
                ? `rulon ${fmtQty(item.birlik_hajm)} m`
                : "1 rulon, m"
            }
            title="Bitta rulon necha metr"
            value={l.hajm}
            disabled={disabled}
            onChange={(e) =>
              onChange({ hajm: e.target.value.replace(/[^0-9.,]/g, "") })
            }
          />
        )}
      </TableCell>
      <TableCell>
        <Input
          className="num h-8 text-right"
          inputMode="decimal"
          placeholder="0"
          value={l.price}
          disabled={disabled || isSx}
          title={
            isSx
              ? "Tannarx FIFO bo'yicha tasdiqda aniqlanadi — bu taxminiy (xarid narxi)"
              : undefined
          }
          onFocus={(e) => e.target.select()}
          onChange={(e) =>
            onChange({ price: e.target.value.replace(/[^0-9.,]/g, "") })
          }
        />
      </TableCell>
      {kind === "chiqim" && (
        <TableCell>
          <Input
            className="num h-8 text-right"
            inputMode="decimal"
            placeholder="0"
            value={l.disc}
            disabled={disabled}
            onFocus={(e) => e.target.select()}
            onChange={(e) =>
              onChange({ disc: e.target.value.replace(/[^0-9.,]/g, "") })
            }
          />
        </TableCell>
      )}
      <TableCell className="num text-right font-semibold">
        {isK ? `$${s.toFixed(2)}` : fmt(s)}
        {isK && s > 0 && (
          <div className="text-[11px] font-normal text-muted-foreground">
            {fmt(s * rate)} so'm
          </div>
        )}
      </TableCell>
      <TableCell>
        <Input
          className="h-8"
          placeholder="—"
          value={l.note}
          disabled={disabled}
          onChange={(e) => onChange({ note: e.target.value })}
          onKeyDown={(e) => {
            // Oxirgi qatorning oxirgi maydonidan Tab — YANGI QATOR (ilgari fokus
            // tasdiqlash tugmasiga o'tib ketardi va omborchi qo'li bilan «Yangi qator»
            // tugmasini izlardi). Shift+Tab odatdagidek orqaga qaytadi.
            if (e.key === "Tab" && !e.shiftKey && isLast && !disabled) {
              e.preventDefault()
              onNext()
            }
          }}
        />
      </TableCell>
      <TableCell>
        {!disabled && (
          <Button
            size="icon"
            variant="ghost"
            className="size-7"
            aria-label={`${no}-qatorni o'chirish`}
            onClick={onDelete}
          >
            <X />
          </Button>
        )}
      </TableCell>
    </TableRow>
  )
}

//: Taklif oynasida bir vaqtda ko'rinadigan eng ko'p qator (qolgani — qidiruvni aniqlashtirib)
const SUG_MAX = 100

/** «Excel'dan yuklash» — kod (yoki to'liq nom) va soni ustunli qatorlar (dizayndagi `parseImport`). */
function ImportLinesDialog({
  open,
  onOpenChange,
  catalog,
  isK,
  onApply,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  catalog: CatalogRow[]
  isK: boolean
  onApply: (rows: { r: CatalogRow; q: number }[]) => void
}) {
  const [text, setText] = useState("")
  const parsed = useMemo(() => {
    const byCode = new Map(catalog.map((r) => [r.code.toLowerCase(), r]))
    const byName = new Map(catalog.map((r) => [r.name.toLowerCase(), r]))
    const rows = new Map<number, { r: CatalogRow; q: number }>()
    const unknown: string[] = []
    let skipped = 0
    for (const raw of text.split(/\r?\n/)) {
      const cells = raw
        .split(/\t|;/)
        .map((c) => c.trim())
        .filter(Boolean)
      if (!cells.length) continue
      const r =
        cells.map((c) => byCode.get(c.toLowerCase())).find(Boolean) ??
        cells.map((c) => byName.get(c.toLowerCase())).find(Boolean)
      const q = [...cells]
        .reverse()
        .map(parseNum)
        .find((n) => n != null && n > 0)
      if (!r) {
        unknown.push(cells[0])
        continue
      }
      if (!q) continue
      if (isK && r.catalog === "X") {
        skipped++
        continue
      }
      const ex = rows.get(r.id)
      rows.set(r.id, { r, q: (ex?.q ?? 0) + q })
    }
    return { rows: [...rows.values()], unknown, skipped }
  }, [text, catalog, isK])
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Excel'dan yuklash — qatorlar</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Excel'dan «kod» (yoki to'liq nom) va «soni» ustunlarini nusxalab
          qo'ying. Bir xil tovar qo'shiladi.
        </p>
        <Textarea
          rows={10}
          className="num text-xs"
          placeholder={"F-RC-001-01\t20\nF-PT-003-01\t100"}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <p className="text-sm">
          Tanildi: <b>{parsed.rows.length}</b> qator
          {parsed.unknown.length > 0 && (
            <span className="text-destructive">
              {" "}
              · tanilmadi: {parsed.unknown.slice(0, 5).join(", ")}
            </span>
          )}
          {parsed.skipped > 0 && (
            <span className="text-muted-foreground">
              {" "}
              · {parsed.skipped} ta xizmat o'tkazib yuborildi (kirim qilinmaydi)
            </span>
          )}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Bekor qilish
          </Button>
          <Button
            disabled={!parsed.rows.length}
            onClick={() => {
              onApply(parsed.rows)
              setText("")
              onOpenChange(false)
            }}
          >
            {parsed.rows.length} qatorni qo'shish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Tasdiqlangan hujjat — qulflangan, faqat ko'rish. */
function ReadOnlyDoc({ doc }: { doc: DocRead }) {
  const [contract, setContract] = useState(false)
  const isK = doc.kind === "kirim"
  const h = doc.head
  if (doc.kind === "inv") return <InvDoc doc={doc} />
  const isSx = doc.kind === "sex"
  const isC = doc.kind === "chiqim"
  const rows: ShartnomaRow[] = doc.lines.map((l) => {
    const g = num(l.qty) * num(l.price)
    return {
      key: l.id,
      name: l.name,
      note: l.note,
      code: l.code,
      unit: l.unit,
      qty: num(l.qty),
      price: num(l.price),
      sum: Math.max(0, g - Math.min(num(l.discount), g)),
    }
  })
  if (contract)
    return (
      <div className="flex flex-col gap-4">
        <div className="flex gap-2 print:hidden">
          <Button variant="outline" onClick={() => setContract(false)}>
            Hujjatga qaytish
          </Button>
          <Button onClick={() => window.print()}>
            <Printer /> Chop etish
          </Button>
        </div>
        <Shartnoma
          head={{
            client: h.client ?? "",
            phone: h.phone ?? "",
            order: h.order ?? "",
            seller: h.seller ?? "",
            dateISO: doc.doc_date,
            dueISO: h.due ?? "",
          }}
          rows={rows}
          jami={num(doc.total)}
        />
      </div>
    )
  const facts: [string, string | undefined][] = isK
    ? [
        ["Yetkazib beruvchi", h.supplier],
        ["Telefon", h.phone],
        ["Faktura №", h.invoice],
        ["Qabul qildi", h.receiver],
        ["Kurs", doc.rate ? `1 $ = ${fmt(doc.rate)} so'm` : undefined],
        ["Izoh", h.note],
      ]
    : isSx
      ? [
          ["Kim oldi", h.taker],
          ["Uskuna / uchastka", h.equip],
          ["Buyurtma / loyiha №", h.order],
          ["Berdi", h.giver],
          ["Izoh", h.note],
        ]
      : [
          ["Mijoz", h.client],
          ["Telefon", h.phone],
          ["Manzil", h.addr],
          ["Buyurtma №", h.order],
          ["Sotuvchi", h.seller],
          ["Topshirish muddati", h.due],
        ]
  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <Link
        to="/warehouse/docs"
        className="text-sm font-semibold text-primary hover:underline"
      >
        ← Hujjatlar
      </Link>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">
          {doc.kind === "storno"
            ? "Storno hujjati"
            : isK
              ? "Kirim listi"
              : isSx
                ? "Sexga kirim listi"
                : "Sotuv listi (chiqim)"}
        </h1>
        <span className="num text-sm text-muted-foreground">{doc.no}</span>
        {doc.status === "storno" ? (
          // EKO 2.4: tasdiqlangan hujjat o'chirilmaydi — teskari STORNO hujjati bilan bekor qilinadi
          <span className="rounded bg-red-600 px-1.5 text-xs font-semibold text-white uppercase">
            Storno qilingan · {h.storno}
          </span>
        ) : (
          <span className="rounded bg-emerald-600 px-1.5 text-xs font-semibold text-white uppercase">
            Tasdiqlangan
          </span>
        )}
        {doc.kind === "storno" && (
          <span className="text-sm">
            asl hujjat: <b>{h.asl}</b> · sabab: {h.sabab}
          </span>
        )}
        {doc.status === "confirmed" &&
          ["kirim", "chiqim", "sex"].includes(doc.kind) && (
            <StornoButton docId={doc.id} no={doc.no} />
          )}
        <span className="text-sm text-muted-foreground">{doc.doc_date}</span>
        {isK && doc.status === "confirmed" && doc.lines.some(isTracked) && (
          // Kirimda list/rulon barkod oladi (EKO TZ §4.4) — yorliqlar shu hujjat bo'yicha
          <Button variant="outline" asChild>
            <Link to="/warehouse/yorliq" search={{ doc: doc.id }}>
              <Printer /> Barkod yorliqlari
            </Link>
          </Button>
        )}
        {isC && (
          <Button
            variant="outline"
            className="ml-auto"
            onClick={() => setContract(true)}
          >
            Shartnoma
          </Button>
        )}
      </div>
      <dl className={cn(cardSurface, "grid gap-3 p-4 text-sm sm:grid-cols-3")}>
        {facts
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs font-semibold text-muted-foreground uppercase">
                {k}
              </dt>
              <dd className="font-semibold">{v}</dd>
            </div>
          ))}
      </dl>
      <section className={cn(cardSurface, "overflow-hidden")}>
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 text-xs uppercase">
              <TableHead className="w-8">№</TableHead>
              <TableHead className="w-32">Kod</TableHead>
              <TableHead>Nom</TableHead>
              <TableHead className="text-right">Soni</TableHead>
              <TableHead className="text-right">
                {isK ? "Narx, $" : isSx ? "Tannarx" : "Narxi"}
              </TableHead>
              {isC && <TableHead className="text-right">Chegirma</TableHead>}
              <TableHead className="text-right">Summa</TableHead>
              {isC && <TableHead className="text-right">Tannarx</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {doc.lines.map((l, i) => (
              <TableRow key={l.id}>
                <TableCell className="num text-muted-foreground">
                  {i + 1}
                </TableCell>
                <TableCell className="num text-xs text-muted-foreground">
                  {l.code ?? "—"}
                </TableCell>
                <TableCell>
                  {l.name}
                  {l.note && (
                    <span className="text-muted-foreground"> — {l.note}</span>
                  )}
                </TableCell>
                <TableCell className="num text-right">
                  {fmtQty(l.qty)} {l.unit ?? ""}
                </TableCell>
                <TableCell className="num text-right">
                  {isK
                    ? `$${num(l.price).toFixed(2)}`
                    : isSx // sexda narx — tasdiqdagi FIFO tannarx (`cost`)
                      ? fmt(num(l.cost) / (num(l.qty) || 1))
                      : fmt(l.price)}
                </TableCell>
                {isC && (
                  <TableCell className="num text-right">
                    {num(l.discount) ? fmt(l.discount) : "—"}
                  </TableCell>
                )}
                <TableCell className="num text-right font-semibold">
                  {isK
                    ? fmt(num(l.qty) * num(l.price) * num(doc.rate))
                    : isSx
                      ? fmt(l.cost)
                      : fmt(rows[i].sum)}
                </TableCell>
                {isC && (
                  <TableCell className="num text-right text-muted-foreground">
                    {l.cost != null ? fmt(l.cost) : "—"}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="flex flex-wrap justify-end gap-6 border-t p-4 text-sm">
          {isC && doc.cogs != null && (
            <>
              <span>
                FIFO tannarx <b className="num">{fmt(doc.cogs)}</b>
              </span>
              <span>
                Foyda{" "}
                <b className="num">{fmt(num(doc.total) - num(doc.cogs))}</b>
              </span>
            </>
          )}
          <span>
            Jami <b className="num text-lg">{fmt(doc.total)} so'm</b>
          </span>
        </div>
      </section>
    </div>
  )
}

/** Tasdiqlangan inventarizatsiya: hisobdagi va sanalgan miqdor, farq va uning summasi */
function InvDoc({ doc }: { doc: DocRead }) {
  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <Link
        to="/warehouse/docs"
        className="text-sm font-semibold text-primary hover:underline"
      >
        ← Hujjatlar
      </Link>
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">Inventarizatsiya</h1>
        <span className="num text-sm text-muted-foreground">{doc.no}</span>
        <span className="rounded bg-emerald-600 px-1.5 text-xs font-semibold text-white uppercase">
          Tasdiqlangan
        </span>
        <span className="text-sm text-muted-foreground">{doc.doc_date}</span>
        {doc.head.note && (
          <span className="text-sm text-muted-foreground">
            · {doc.head.note}
          </span>
        )}
      </div>
      <section className={cn(cardSurface, "overflow-hidden")}>
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 text-xs uppercase">
              <TableHead className="w-8">№</TableHead>
              <TableHead className="w-32">Kod</TableHead>
              <TableHead>Nom</TableHead>
              <TableHead className="text-right">Hisobda</TableHead>
              <TableHead className="text-right">Haqiqiy</TableHead>
              <TableHead className="text-right">Farq</TableHead>
              <TableHead className="text-right">Summa farqi</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {doc.lines.map((l, i) => {
              const d = num(l.qty) - num(l.book_qty)
              return (
                <TableRow key={l.id}>
                  <TableCell className="num text-muted-foreground">
                    {i + 1}
                  </TableCell>
                  <TableCell className="num text-xs text-muted-foreground">
                    {l.code ?? "—"}
                  </TableCell>
                  <TableCell>{l.name}</TableCell>
                  <TableCell className="num text-right">
                    {fmtQty(l.book_qty)}
                  </TableCell>
                  <TableCell className="num text-right">
                    {fmtQty(l.qty)} {l.unit ?? ""}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "num text-right font-semibold",
                      d < 0 ? "text-destructive" : "text-emerald-600",
                    )}
                  >
                    {d > 0 ? "+" : ""}
                    {fmtQty(d)}
                  </TableCell>
                  <TableCell className="num text-right">
                    {l.cost != null ? fmt(l.cost) : "—"}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
        <div className="flex justify-end border-t p-4 text-sm">
          <span>
            Jami farq <b className="num text-lg">{fmt(doc.total)} so'm</b>
          </span>
        </div>
      </section>
    </div>
  )
}
