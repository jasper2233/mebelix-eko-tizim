// Mahsulotlar ombori — Inventarizatsiya (dizayndagi «Inventarizatsiya», docs/14 §10): guruh tanlanadi,
// har pozitsiyaga sanalgan HAQIQIY miqdor kiritiladi (Enter/↓ — keyingisi, ↑ — oldingisi), F9 — tasdiq.
// Bo'sh qoldirilgan qator sanalmagan hisoblanadi va hujjatga kirmaydi. Server farqni qoldiqqa yozadi
// (ortiqcha — partiya, kami — FIFO) va tasdiqlangan `INV` hujjatini qaytaradi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { FileUp } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { StockService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { fmt, fmtQty, fmtSum, groupKey, num, parseNum } from "@/lib/warehouse"
import { getCatalogAllQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/warehouse/inv")({
  component: InvPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Inventarizatsiya | MebeliX" }] }),
})

function InvPage() {
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: catalog } = useQuery(getCatalogAllQueryOptions())
  const [group, setGroup] = useState("")
  const [counts, setCounts] = useState<Record<number, string>>({})
  const [importOpen, setImportOpen] = useState(false)
  const inputs = useRef<(HTMLInputElement | null)[]>([])

  // Xizmat sanalmaydi — qoldig'i yo'q
  const groups = useMemo(() => {
    const m = new Map<string, string>()
    for (const r of catalog ?? [])
      if (r.catalog !== "X") m.set(groupKey(r), r.group_name)
    return [...m].sort(([a], [b]) => a.localeCompare(b))
  }, [catalog])
  const rows = useMemo(
    () => (catalog ?? []).filter((r) => groupKey(r) === group),
    [catalog, group],
  )
  const diffOf = (id: number, book: string) => {
    const v = parseNum(counts[id] ?? "")
    return v == null ? null : v - num(book)
  }
  const found = rows.filter((r) => {
    const d = diffOf(r.id, r.quantity)
    return d != null && d !== 0
  })
  const sumDiff = found.reduce(
    (a, r) => a + (diffOf(r.id, r.quantity) ?? 0) * num(r.purchase_price),
    0,
  )

  const save = useMutation({
    mutationFn: async () =>
      (
        await StockService.confirmStockInventory({
          body: {
            doc_date: new Date().toLocaleDateString("sv-SE"),
            head: { group },
            counts: rows
              .filter((r) => parseNum(counts[r.id] ?? "") != null)
              .map((r) => ({
                item_id: r.id,
                qty: parseNum(counts[r.id]) ?? 0,
              })),
          },
        })
      ).data,
    onSuccess: (d) => {
      toast.success(`${d.no} tasdiqlandi — qoldiq to'g'rilandi`)
      setCounts({})
      navigate({ to: "/warehouse/docs" })
    },
    onError: handleError,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["stock"] })
      queryClient.invalidateQueries({ queryKey: ["catalog"] })
    },
  })
  const counted = rows.some((r) => parseNum(counts[r.id] ?? "") != null)
  const submit = () => {
    if (canWrite && counted && !save.isPending) save.mutate()
  }
  const submitRef = useRef(submit)
  submitRef.current = submit
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "F9") return
      e.preventDefault()
      submitRef.current()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  if (!catalog) return <Skeleton className="h-96 w-full" />
  const byCode = new Map(rows.map((r) => [r.code.toUpperCase(), r.id]))

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Inventarizatsiya"
        description="Sanalgan haqiqiy miqdorni kiriting — farq tasdiqda qoldiqqa yoziladi"
      />
      <div className="flex flex-wrap items-center gap-2">
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={group}
          onChange={(e) => {
            setGroup(e.target.value)
            setCounts({})
          }}
        >
          <option value="">— Guruhni tanlang —</option>
          {groups.map(([k, n]) => (
            <option key={k} value={k}>
              {k} · {n}
            </option>
          ))}
        </select>
        {group && (
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <FileUp /> Excel'dan yuklash
          </Button>
        )}
        {canWrite && (
          <Button className="ml-auto" disabled={!counted} onClick={submit}>
            Tasdiqlash va qoldiqni to'g'rilash{" "}
            <kbd className="ml-1 rounded border px-1 text-[10px]">F9</kbd>
          </Button>
        )}
      </div>
      {group && (
        <div className="grid gap-3 sm:grid-cols-3">
          {(
            [
              ["Pozitsiya", fmt(rows.length)],
              ["Farq topildi", fmt(found.length)],
              ["Summada", `${fmtSum(sumDiff)} so'm`],
            ] as const
          ).map(([k, v]) => (
            <div key={k} className={cn(cardSurface, "p-4")}>
              <div className="text-xs font-semibold text-muted-foreground uppercase">
                {k}
              </div>
              <div className="num text-xl font-bold">{v}</div>
            </div>
          ))}
        </div>
      )}
      {group && (
        <section className={cn(cardSurface, "overflow-hidden")}>
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50 text-xs uppercase">
                <TableHead className="w-32">Kod</TableHead>
                <TableHead>Nom</TableHead>
                <TableHead className="w-28">Joy</TableHead>
                <TableHead className="w-28 text-right">Hisobda</TableHead>
                <TableHead className="w-32 text-right">Haqiqiy</TableHead>
                <TableHead className="w-24 text-right">Farq</TableHead>
                <TableHead className="w-32 text-right">Summa</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => {
                const d = diffOf(r.id, r.quantity)
                return (
                  <TableRow key={r.id}>
                    <TableCell className="num text-xs text-muted-foreground">
                      {r.code}
                    </TableCell>
                    <TableCell>{r.name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {r.location ?? "—"}
                    </TableCell>
                    <TableCell className="num text-right">
                      {fmtQty(r.quantity)} {r.unit ?? ""}
                    </TableCell>
                    <TableCell>
                      <Input
                        ref={(el) => {
                          inputs.current[i] = el
                        }}
                        aria-label={`${r.code} haqiqiy miqdor`}
                        className="num h-8 text-right"
                        inputMode="decimal"
                        value={counts[r.id] ?? ""}
                        onChange={(e) =>
                          setCounts({ ...counts, [r.id]: e.target.value })
                        }
                        onKeyDown={(e) => {
                          const to =
                            e.key === "Enter" || e.key === "ArrowDown"
                              ? i + 1
                              : e.key === "ArrowUp"
                                ? i - 1
                                : null
                          if (to == null) return
                          e.preventDefault()
                          inputs.current[to]?.focus()
                        }}
                      />
                    </TableCell>
                    <TableCell
                      className={cn(
                        "num text-right font-semibold",
                        d != null && d < 0 && "text-destructive",
                        d != null && d > 0 && "text-emerald-600",
                      )}
                    >
                      {d == null ? "" : `${d > 0 ? "+" : ""}${fmtQty(d)}`}
                    </TableCell>
                    <TableCell className="num text-right text-muted-foreground">
                      {d ? fmtSum(d * num(r.purchase_price)) : ""}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </section>
      )}
      <ImportCounts
        open={importOpen}
        onOpenChange={setImportOpen}
        byCode={byCode}
        onApply={(m) => setCounts({ ...counts, ...m })}
      />
    </div>
  )
}

/** Excel'dan «kod · soni» ustunlari nusxalab qo'yiladi; kod tanlangan guruhda bo'lishi shart. */
function ImportCounts({
  open,
  onOpenChange,
  byCode,
  onApply,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  byCode: Map<string, number>
  onApply: (m: Record<number, string>) => void
}) {
  const [text, setText] = useState("")
  const ok: Record<number, string> = {}
  const errs: string[] = []
  text.split(/\r?\n/).forEach((raw, ix) => {
    const [code = "", qty = ""] = raw.split(/\t|;/).map((s) => s.trim())
    if (!code || /^kod$/i.test(code)) return
    const id = byCode.get(code.toUpperCase())
    if (id == null || parseNum(qty) == null)
      errs.push(`${ix + 1}-qator: «${code}»`)
    else ok[id] = qty
  })
  const n = Object.keys(ok).length
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Excel'dan yuklash — sanalgan miqdorlar</DialogTitle>
          <DialogDescription>
            Ikki ustun: Kod va Soni. Excel'dan nusxalab qo'ying.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          rows={10}
          className="num text-xs"
          placeholder={"Kod\tSoni"}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <p className="text-sm">
          Tayyor: <b>{n}</b> qator
          {errs.length > 0 && (
            <span className="text-destructive">
              {" "}
              · {errs.length} ta xato (guruhda yo'q yoki son noto'g'ri):{" "}
              {errs.slice(0, 3).join(" · ")}
            </span>
          )}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Bekor qilish
          </Button>
          <Button
            disabled={!n}
            onClick={() => {
              onApply(ok)
              setText("")
              onOpenChange(false)
            }}
          >
            {n} ta qatorni qo'yish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
