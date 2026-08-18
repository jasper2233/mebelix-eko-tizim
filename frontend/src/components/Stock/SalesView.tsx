import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { type SaleRead, StockService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import { num, uzs } from "./format"
import { PaymentDialog } from "./SaleDialog"

const STATUS: Record<string, { label: string; color: string }> = {
  paid: { label: "TO'LANDI", color: "var(--status-completed)" },
  partial: { label: "QISMAN", color: "var(--status-review)" },
  debt: { label: "QARZ", color: "var(--status-cancelled)" },
}

/** Sotuvlar va qarzdorlar. Alohida sahifa emas — Materiallar ombori sahifasidagi ikkinchi
 * ko'rinish: omborchi kun davomida ikkalasi orasida tez-tez o'tadi, sahifa
 * almashtirish ortiqcha qadam bo'lardi. */
export function SalesView() {
  const [debtsOnly, setDebtsOnly] = useState(false)
  const [payFor, setPayFor] = useState<SaleRead | null>(null)

  const { data: sales, isLoading } = useQuery({
    queryKey: ["stock", "sales", debtsOnly],
    queryFn: async () =>
      (
        await StockService.readSales({
          query: { debts: debtsOnly || undefined, limit: 100 },
        })
      ).data,
  })
  const { data: summary } = useQuery({
    queryKey: ["stock", "sales", "summary"],
    queryFn: async () => (await StockService.readSalesSummary()).data,
  })

  return (
    <div>
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <Stat label="Sotuvlar" value={String(summary?.sales ?? "—")} />
        <Stat
          label="Savdo"
          value={summary ? `${uzs(summary.total_uzs)}` : "—"}
        />
        <Stat
          label="Tushgan pul"
          value={summary ? `${uzs(summary.paid_uzs)}` : "—"}
        />
        <Stat
          label="Qarz"
          value={summary ? `${uzs(summary.debt_uzs)}` : "—"}
          warn={num(summary?.debt_uzs) > 0}
        />
      </div>

      <div className="mb-3">
        <Button
          variant={debtsOnly ? "default" : "outline"}
          size="sm"
          onClick={() => setDebtsOnly(!debtsOnly)}
        >
          Faqat qarzdorlar
        </Button>
      </div>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>№</TableHead>
                <TableHead>Sana</TableHead>
                <TableHead>Mijoz</TableHead>
                <TableHead className="text-right">Jami</TableHead>
                <TableHead className="text-right">To'landi</TableHead>
                <TableHead className="text-right">Qarz</TableHead>
                <TableHead>Holat</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {sales?.length ? (
                sales.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="num font-medium">#{s.id}</TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {new Date(s.created_at).toLocaleDateString("ru-RU")}
                    </TableCell>
                    <TableCell>
                      {s.client_name ?? (
                        <span className="text-muted-foreground">
                          o'tkinchi xaridor
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="num text-right">
                      {uzs(s.total_uzs)}
                    </TableCell>
                    <TableCell className="num text-right text-muted-foreground">
                      {uzs(s.paid_uzs)}
                    </TableCell>
                    <TableCell className="num text-right font-bold">
                      {num(s.debt_uzs) > 0 ? uzs(s.debt_uzs) : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        style={{ backgroundColor: STATUS[s.status]?.color }}
                        className="text-white"
                      >
                        {STATUS[s.status]?.label ?? s.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {num(s.debt_uzs) > 0 && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPayFor(s)}
                        >
                          To'lov
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <EmptyRow colSpan={8}>
                  {debtsOnly
                    ? "Qarzdor yo'q."
                    : 'Hali sotuv yo\'q — katalogdan "Sotish" bilan boshlang.'}
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {payFor && (
        <PaymentDialog
          key={payFor.id}
          saleId={payFor.id}
          debt={num(payFor.debt_uzs)}
          onClose={() => setPayFor(null)}
        />
      )}
    </div>
  )
}

function Stat({
  label,
  value,
  warn,
}: {
  label: string
  value: string
  warn?: boolean
}) {
  return (
    <div className="rounded-lg border bg-card px-4 py-3">
      <div className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={`num mt-0.5 text-xl font-bold ${warn ? "text-(--status-cancelled)" : ""}`}
      >
        {value}
      </div>
    </div>
  )
}
