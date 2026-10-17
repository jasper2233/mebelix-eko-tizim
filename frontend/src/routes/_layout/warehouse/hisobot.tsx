// Mahsulotlar ombori — Hisobot (dizayndagi `rep` ekrani, docs/14 §11): guruh bo'yicha qoldiq va
// aylanma, ABC tahlili, harakatsiz tovarlar. Qoldiq va qiymat — HOZIRGI holat, kirim/chiqim va
// harakatsizlik esa tanlangan ORALIQDA (dizaynda oraliq yo'q edi — u brauzer sessiyasini sanardi).

import { useQuery } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Download } from "lucide-react"
import { useState } from "react"

import { StockService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { DatePicker } from "@/components/ui/date-picker"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { requireAccess } from "@/lib/guards"
import { isoOf, isWarehouseStaff } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { CATALOG_NAMES, downloadCsv, fmt, fmtQty, num } from "@/lib/warehouse"

export const Route = createFileRoute("/_layout/warehouse/hisobot")({
  component: StockReportPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Ombor hisoboti | MebeliX" }] }),
})

//: ABC ustunlarining rangi — A eng qimmat uchlik, C eng arzon quyruq
const ABC_COLOR: Record<string, string> = {
  A: "bg-primary",
  B: "bg-primary/55",
  C: "bg-primary/25",
}

function StockReportPage() {
  const navigate = useNavigate()
  // Bo'sh filtr — backend joriy oyni oladi (`routes/stock.py: _range`); DatePicker'lar
  // ham shu bilan boshlanadi, aks holda «bo'sh» hamma vaqt degan ma'no berardi
  const bugun = new Date()
  const [dateFrom, setDateFrom] = useState(
    isoOf(new Date(bugun.getFullYear(), bugun.getMonth(), 1)),
  )
  const [dateTo, setDateTo] = useState(isoOf(bugun))

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stock", "report", dateFrom, dateTo],
    queryFn: async () =>
      (
        await StockService.readStockReport({
          query: {
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
          },
        })
      ).data,
  })

  const eksport = () => {
    if (!data) return
    downloadCsv("ombor-hisoboti.csv", [
      [
        "Katalog",
        "Guruh",
        "Nomi",
        "Pozitsiya",
        "Kirim",
        "Chiqim",
        "Qoldiq qiymati",
      ],
      ...data.groups.map((g) => [
        g.catalog,
        `${g.catalog}-${g.group_code}`,
        g.group_name,
        g.positions,
        fmtQty(g.qty_in),
        fmtQty(g.qty_out),
        fmt(g.value),
      ]),
    ])
  }

  return (
    <div>
      <PageHeader
        title="Ombor hisoboti"
        description={
          data
            ? `${fmt(data.value)} so'm · ${data.positions} pozitsiya · aylanma ${dateFrom} — ${dateTo}`
            : "Guruh bo'yicha qoldiq va aylanma, ABC tahlili, harakatsiz tovarlar"
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <DatePicker value={dateFrom} onChange={setDateFrom} />
            <span className="text-muted-foreground">—</span>
            <DatePicker value={dateTo} onChange={setDateTo} />
            <Button variant="outline" onClick={eksport} disabled={!data}>
              <Download /> Excel'ga chiqarish
            </Button>
          </div>
        }
      />

      {isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : isError || !data ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-start">
          <div>
            <h2 className="mb-2 px-1 font-semibold">
              Guruh bo'yicha qoldiq va aylanma
            </h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Guruh</TableHead>
                  <TableHead className="text-right">Pozitsiya</TableHead>
                  <TableHead className="text-right">Kirim</TableHead>
                  <TableHead className="text-right">Chiqim</TableHead>
                  <TableHead className="text-right">Qiymat</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.groups.length ? (
                  data.groups.map((g) => (
                    <TableRow
                      key={`${g.catalog}-${g.group_code}`}
                      className="cursor-pointer"
                      onClick={() =>
                        navigate({
                          to: "/warehouse",
                          search: {
                            katalog: g.catalog,
                            guruh: `${g.catalog}-${g.group_code}`,
                          },
                        })
                      }
                    >
                      <TableCell>
                        <span className="block truncate font-medium">
                          {g.group_name}
                        </span>
                        <span className="num block text-xs text-muted-foreground">
                          {g.catalog}-{g.group_code} ·{" "}
                          {CATALOG_NAMES[
                            g.catalog as keyof typeof CATALOG_NAMES
                          ] ?? g.catalog}
                        </span>
                      </TableCell>
                      <TableCell className="num text-right">
                        {g.positions}
                      </TableCell>
                      {/* Aylanmasi yo'q guruh — chiziqcha: nol bilan aralashmasin */}
                      <TableCell className="num text-right text-emerald-700">
                        {num(g.qty_in) ? fmtQty(g.qty_in) : "—"}
                      </TableCell>
                      <TableCell className="num text-right text-amber-700">
                        {num(g.qty_out) ? fmtQty(g.qty_out) : "—"}
                      </TableCell>
                      <TableCell className="num text-right font-semibold">
                        {fmt(g.value)}
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <EmptyRow colSpan={5}>Katalog bo'sh.</EmptyRow>
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex flex-col gap-4">
            <section className={cn(cardSurface, "p-5")}>
              <h2 className="font-semibold">ABC tahlil (qiymat bo'yicha)</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Qoldiq qiymatining 80% ini beradigan pozitsiyalar — A, keyingi
                15% — B, qolgani — C.
              </p>
              {/* Ulushlar bitta yo'lakda: uchta sinfning og'irligi bir qarashda ko'rinsin */}
              <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-muted">
                {data.abc.map((a) => (
                  <div
                    key={a.cls}
                    className={ABC_COLOR[a.cls]}
                    style={{ width: `${a.pct}%` }}
                    title={`${a.cls}: ${a.pct}%`}
                  />
                ))}
              </div>
              <dl className="mt-4 space-y-2">
                {data.abc.map((a) => (
                  <div
                    key={a.cls}
                    className="flex items-baseline justify-between gap-3 text-sm"
                  >
                    <dt className="flex items-center gap-2">
                      <span
                        className={cn("size-2.5 rounded-sm", ABC_COLOR[a.cls])}
                      />
                      <span className="font-semibold">{a.cls} sinf</span>
                      <span className="num text-muted-foreground">
                        {a.positions} ta · {a.pct}%
                      </span>
                    </dt>
                    <dd className="num font-semibold">{fmt(a.value)}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className={cn(cardSurface, "p-5")}>
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="font-semibold">Harakatsiz tovarlar</h2>
                <span className="num text-sm text-muted-foreground">
                  {data.dead_total} ta
                </span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Qoldig'i bor, lekin tanlangan oraliqda bitta ham kirim-chiqimi
                yo'q — eng qimmatlari birinchi.
              </p>
              <div className="mt-3 divide-y">
                {data.dead.length ? (
                  data.dead.map((d) => (
                    <button
                      key={d.item_id}
                      type="button"
                      onClick={() =>
                        navigate({
                          to: "/warehouse/item/$code",
                          params: { code: d.code },
                        })
                      }
                      className="flex w-full items-baseline justify-between gap-3 py-2 text-left hover:bg-muted/50"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm">{d.name}</span>
                        <span className="num block text-xs text-muted-foreground">
                          {d.code} · {fmtQty(d.quantity)} {d.unit ?? ""}
                        </span>
                      </span>
                      <span className="num shrink-0 text-sm font-semibold">
                        {fmt(d.value)}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    Hamma tovar qimirlagan.
                  </p>
                )}
              </div>
              {data.dead_total > data.dead.length && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Yana {data.dead_total - data.dead.length} ta — ro'yxat eng
                  qimmat {data.dead.length} tasi bilan cheklangan.
                </p>
              )}
            </section>
          </div>
        </div>
      )}
    </div>
  )
}
