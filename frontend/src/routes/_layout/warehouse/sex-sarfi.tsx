// Mahsulotlar ombori — Sex sarfi (dizayndagi «Sex sarfi», docs/14 §10): tasdiqlangan «Sexga kirim»
// qatorlari — kim, qachon, qaysi uskuna uchun nima oldi. Qidiruv, usta filtri, CSV.

import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { Download, Plus } from "lucide-react"
import { useMemo, useState } from "react"

import { StockService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
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
import { SexTabs } from "@/components/Warehouse/SexTabs"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { downloadCsv, fmt, fmtQty, num } from "@/lib/warehouse"

export const Route = createFileRoute("/_layout/warehouse/sex-sarfi")({
  component: SexLogPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Sex sarfi | MebeliX" }] }),
})

function SexLogPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stock", "sex-log"],
    queryFn: async () => (await StockService.readStockSexLog()).data,
  })
  const [q, setQ] = useState("")
  const [taker, setTaker] = useState("")
  const all = data ?? []
  const takers = useMemo(
    () => [...new Set(all.map((r) => r.taker))].sort(),
    [all],
  )
  const t = q.trim().toLowerCase()
  const rows = all.filter(
    (r) =>
      (!taker || r.taker === taker) &&
      (!t ||
        [r.taker, r.equip, r.code, r.name, r.doc_no].some((s) =>
          s.toLowerCase().includes(t),
        )),
  )
  const total = rows.reduce((a, r) => a + num(r.amount), 0)
  const perTaker = [
    ...rows
      .reduce(
        (m, r) => m.set(r.taker, (m.get(r.taker) ?? 0) + num(r.amount)),
        new Map<string, number>(),
      )
      .entries(),
  ].sort((a, b) => b[1] - a[1])

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Sex xo'jaligi"
        description="Sexga berilgan zapchast, asbob va sarf — kim, qachon, nima uchun"
      />
      <SexTabs active="log" />
      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="w-72"
          placeholder="Qidirish: usta, uskuna, tovar"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          aria-label="Usta"
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={taker}
          onChange={(e) => setTaker(e.target.value)}
        >
          <option value="">Barcha ustalar</option>
          {takers.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <div className="ml-auto flex gap-2">
          <Button
            variant="outline"
            disabled={!rows.length}
            onClick={() =>
              downloadCsv("sex-sarfi.csv", [
                [
                  "Sana",
                  "Hujjat",
                  "Kim oldi",
                  "Uskuna",
                  "Buyurtma",
                  "Kod",
                  "Nom",
                  "Soni",
                  "Birlik",
                  "Tannarx",
                  "Berdi",
                ],
                ...rows.map((r) => [
                  r.doc_date,
                  r.doc_no,
                  r.taker,
                  r.equip,
                  r.order,
                  r.code,
                  r.name,
                  num(r.qty),
                  r.unit,
                  r.amount != null ? num(r.amount) : "",
                  r.giver,
                ]),
              ])
            }
          >
            <Download /> CSV
          </Button>
          <Button asChild>
            <Link to="/warehouse/doc" search={{ turi: "sex" }}>
              <Plus /> Sexga kirim{" "}
              <kbd className="ml-1 rounded border px-1 text-[10px]">F3</kbd>
            </Link>
          </Button>
        </div>
      </div>
      {perTaker.length > 0 && (
        <div
          className={cn(
            cardSurface,
            "flex flex-wrap gap-x-6 gap-y-1 p-4 text-sm",
          )}
        >
          <span>
            Jami <b className="num">{fmt(total)} so'm</b>
          </span>
          {perTaker.map(([k, v]) => (
            <span key={k} className="text-muted-foreground">
              {k} <b className="num text-foreground">{fmt(v)}</b>
            </span>
          ))}
        </div>
      )}
      {isError ? (
        <QueryError onRetry={refetch} />
      ) : isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <section className={cn(cardSurface, "overflow-hidden")}>
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50 text-xs uppercase">
                <TableHead className="w-28">Sana</TableHead>
                <TableHead className="w-32">Hujjat</TableHead>
                <TableHead>Kim oldi</TableHead>
                <TableHead>Uskuna</TableHead>
                <TableHead>Tovar</TableHead>
                <TableHead className="text-right">Soni</TableHead>
                <TableHead className="text-right">Tannarx</TableHead>
                <TableHead>Berdi</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length ? (
                rows.map((r, i) => (
                  <TableRow
                    key={`${r.doc_id}-${i}`}
                    className="cursor-pointer"
                    onClick={() =>
                      navigate({
                        to: "/warehouse/doc",
                        search: { turi: "sex", id: r.doc_id },
                      })
                    }
                  >
                    <TableCell className="text-muted-foreground">
                      {r.doc_date}
                    </TableCell>
                    <TableCell className="num">{r.doc_no}</TableCell>
                    <TableCell className="font-semibold">{r.taker}</TableCell>
                    <TableCell>{r.equip || "—"}</TableCell>
                    <TableCell>
                      <span className="num text-xs text-muted-foreground">
                        {r.code}
                      </span>{" "}
                      {r.name}
                    </TableCell>
                    <TableCell className="num text-right">
                      {fmtQty(r.qty)} {r.unit ?? ""}
                    </TableCell>
                    <TableCell className="num text-right">
                      {r.amount != null ? fmt(r.amount) : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {r.giver}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <EmptyRow colSpan={8}>
                  Sexga hali hech narsa berilmagan
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </section>
      )}
    </div>
  )
}
