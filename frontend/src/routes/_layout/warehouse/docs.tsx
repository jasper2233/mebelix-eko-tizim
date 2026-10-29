// Mahsulotlar ombori — Hujjatlar (dizayndagi «Hujjatlar»): qoralamalar va tasdiqlangan (qulflangan)
// hujjatlar, Excel'ga chiqarish (hujjatlar va barcha harakatlar). Qatorni bosish — hujjatni ochadi:
// qoralama tahrirlanadi, tasdiqlangan faqat ko'rinadi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Download, Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { type DocRow, StockService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { downloadCsv, fmt, num } from "@/lib/warehouse"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/warehouse/docs")({
  component: DocsPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Hujjatlar | MebeliX" }] }),
})

const KIND: Record<string, string> = {
  kirim: "Kirim",
  chiqim: "Chiqim (sotuv)",
  sex: "Sexga kirim",
  inv: "Inventarizatsiya",
  storno: "Storno",
}

function DocsPage() {
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["stock", "docs"],
    queryFn: async () => (await StockService.readStockDocs()).data,
  })
  const [del, setDel] = useState<DocRow | null>(null)
  const remove = useMutation({
    mutationFn: (id: number) =>
      StockService.deleteStockDoc({ path: { doc_id: id } }),
    onSuccess: () => toast.success("Qoralama o'chirildi"),
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["stock"] }),
  })
  const exportMoves = useMutation({
    mutationFn: async () => (await StockService.readStockMoves()).data,
    onSuccess: (moves) =>
      downloadCsv("harakatlar.csv", [
        [
          "Vaqt",
          "Hujjat",
          "Kod",
          "Nom",
          "Tur",
          "Miqdor",
          "Qoldiq",
          "Summa",
          "Izoh",
        ],
        ...moves.map((m) => [
          new Date(m.created_at).toLocaleString("uz-UZ"),
          m.doc_no ?? "",
          m.code,
          m.name,
          m.kind,
          num(m.qty),
          num(m.balance),
          m.amount != null ? num(m.amount) : "",
          m.note,
        ]),
      ]),
    onError: handleError,
  })

  const rows = data ?? []
  const drafts = rows.filter((d) => d.status === "draft")
  const done = rows.filter((d) => d.status !== "draft")
  const open = (d: DocRow) =>
    navigate({
      to: "/warehouse/doc",
      search: { turi: d.kind as "kirim" | "chiqim" | "sex" | "inv", id: d.id },
    })

  const table = (list: DocRow[], draft: boolean) => (
    <Table>
      <TableHeader>
        <TableRow className="bg-muted/50 text-xs uppercase">
          <TableHead className="w-36">Hujjat</TableHead>
          <TableHead className="w-32">Tur</TableHead>
          <TableHead className="w-28">Sana</TableHead>
          <TableHead>Izoh</TableHead>
          <TableHead className="w-16 text-right">Qator</TableHead>
          <TableHead className="w-32 text-right">Summa</TableHead>
          <TableHead className="w-28 text-right">
            {draft ? "" : "Foyda"}
          </TableHead>
          <TableHead className="w-28 text-right">Holat</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {list.length ? (
          list.map((d) => (
            <TableRow
              key={d.id}
              className="cursor-pointer"
              onClick={() => open(d)}
            >
              <TableCell className="num font-semibold">{d.no}</TableCell>
              <TableCell>{KIND[d.kind] ?? d.kind}</TableCell>
              <TableCell className="text-muted-foreground">
                {d.doc_date}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {d.who || "—"}
                {d.kind === "kirim" &&
                  d.rate &&
                  !draft &&
                  ` · kurs ${fmt(d.rate)}`}
              </TableCell>
              <TableCell className="num text-right">{d.rows}</TableCell>
              <TableCell className="num text-right font-semibold">
                {draft ? "—" : fmt(d.total)}
              </TableCell>
              <TableCell className="num text-right text-muted-foreground">
                {!draft && d.kind === "chiqim" && d.cogs != null
                  ? fmt(num(d.total) - num(d.cogs))
                  : ""}
              </TableCell>
              <TableCell
                className="text-right"
                onClick={(e) => draft && e.stopPropagation()}
              >
                {draft ? (
                  canWrite ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive"
                      onClick={() => setDel(d)}
                    >
                      <Trash2 />
                    </Button>
                  ) : (
                    "Qoralama"
                  )
                ) : d.status === "storno" ? (
                  <span className="rounded bg-red-600 px-1.5 text-xs font-semibold text-white">
                    Storno qilingan
                  </span>
                ) : (
                  <span className="rounded bg-emerald-600 px-1.5 text-xs font-semibold text-white">
                    Tasdiqlangan
                  </span>
                )}
              </TableCell>
            </TableRow>
          ))
        ) : (
          <EmptyRow colSpan={8}>
            {draft ? "Qoralama yo'q" : "Hali tasdiqlangan hujjat yo'q"}
          </EmptyRow>
        )}
      </TableBody>
    </Table>
  )

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Hujjatlar"
        description="Tasdiqlangan hujjatlar qulflangan"
        actions={<GotoSearch />}
      />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">
          {done.length} tasdiqlangan hujjat · {drafts.length} qoralama
        </span>
        <Button
          size="sm"
          variant="outline"
          className="ml-auto"
          onClick={() =>
            downloadCsv("hujjatlar.csv", [
              [
                "Hujjat",
                "Tur",
                "Sana",
                "Izoh",
                "Qator",
                "Summa",
                "Tannarx",
                "Holat",
              ],
              ...rows.map((d) => [
                d.no,
                KIND[d.kind] ?? d.kind,
                d.doc_date,
                d.who,
                d.rows,
                num(d.total),
                d.cogs != null ? num(d.cogs) : "",
                d.status === "draft" ? "Qoralama" : "Tasdiqlangan",
              ]),
            ])
          }
        >
          <Download /> Hujjatlarni Excel'ga chiqarish
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={exportMoves.isPending}
          onClick={() => exportMoves.mutate()}
        >
          <Download /> Harakatlarni Excel'ga chiqarish
        </Button>
      </div>
      {isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <>
          {drafts.length > 0 && (
            <section className={cn(cardSurface, "overflow-hidden")}>
              <h2 className="border-b px-4 py-2 text-sm font-semibold">
                Qoralamalar
              </h2>
              {table(drafts, true)}
            </section>
          )}
          <section className={cn(cardSurface, "overflow-hidden")}>
            {table(done, false)}
          </section>
        </>
      )}
      <ConfirmDialog
        open={del != null}
        onOpenChange={(v) => !v && setDel(null)}
        title={`${del?.no ?? ""} qoralamasi o'chirilsinmi?`}
        description="Qoralama qoldiqqa ta'sir qilmagan — o'chirilsa hech narsa o'zgarmaydi."
        destructive
        confirmText="O'chirish"
        loading={remove.isPending}
        onConfirm={() => {
          if (del) remove.mutate(del.id)
          setDel(null)
        }}
      />
    </div>
  )
}
