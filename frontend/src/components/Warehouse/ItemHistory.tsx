// Tovar kartochkasi: FIFO partiyalar (eng eskisi birinchi — keyingi chiqim shundan) va harakat tarixi
// (`GET /stock/items/{id}/history`, docs/14 §9).

import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"

import { StockService } from "@/client"
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
import { cn } from "@/lib/utils"
import { fmtQty, fmtSum, num } from "@/lib/warehouse"

const MOVE_KIND: Record<string, string> = {
  kirim: "Kirim",
  chiqim: "Sotuv",
  sex: "Sexga kirim",
  inv: "Inventarizatsiya",
  tuzatish: "Tuzatish",
}
const INITIAL = "Boshlang'ich"

export function ItemHistory({
  itemId,
  unit,
}: {
  itemId: number
  unit: string | null
}) {
  const { data } = useQuery({
    queryKey: ["stock", "history", itemId],
    queryFn: async () =>
      (
        await StockService.readStockItemHistory({
          path: { item_id: itemId },
        })
      ).data,
  })
  if (!data) return <Skeleton className="h-32 w-full" />
  const value = data.lots.reduce(
    (s, l) => s + num(l.qty_left) * num(l.unit_cost),
    0,
  )
  return (
    <>
      <section className={cn(cardSurface, "overflow-hidden")}>
        <h3 className="border-b px-4 py-2 font-semibold">
          Partiyalar (FIFO){" "}
          <span className="text-sm font-normal text-muted-foreground">
            Avval eng eski partiya chiqadi
            {data.next_cost != null &&
              ` · keyingi chiqim narxi ${fmtSum(data.next_cost)} so'm`}{" "}
            · qoldiq qiymati {fmtSum(value)} so'm
          </span>
        </h3>
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 text-xs uppercase">
              <TableHead className="w-8">№</TableHead>
              <TableHead>Sana</TableHead>
              <TableHead>Hujjat</TableHead>
              <TableHead className="text-right">Qoldiq</TableHead>
              <TableHead className="text-right">Tannarx</TableHead>
              <TableHead className="text-right">Summa</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.lots.length ? (
              data.lots.map((l, i) => (
                <TableRow
                  key={l.id || INITIAL}
                  className={cn(i === 0 && "bg-primary/5")}
                >
                  <TableCell className="num text-muted-foreground">
                    {i + 1}
                  </TableCell>
                  <TableCell>
                    {l.source === INITIAL ? INITIAL : l.received_on}
                  </TableCell>
                  <TableCell className="num">
                    {l.source === INITIAL ? "—" : l.source}
                  </TableCell>
                  <TableCell className="num text-right font-semibold">
                    {fmtQty(l.qty_left)} {unit ?? ""}
                  </TableCell>
                  <TableCell className="num text-right">
                    {fmtSum(l.unit_cost)}
                    {l.usd != null && (
                      <span className="text-xs text-muted-foreground">
                        {" "}
                        · ${num(l.usd).toFixed(2)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="num text-right">
                    {fmtSum(num(l.qty_left) * num(l.unit_cost))}
                    {i === 0 && (
                      <span className="ml-1 text-xs font-semibold">
                        keyingi chiqim
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-center text-muted-foreground"
                >
                  Omborda yo'q
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </section>
      <section className={cn(cardSurface, "overflow-hidden")}>
        <h3 className="border-b px-4 py-2 font-semibold">Harakat tarixi</h3>
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 text-xs uppercase">
              <TableHead>Vaqt</TableHead>
              <TableHead>Hujjat</TableHead>
              <TableHead>Tur</TableHead>
              <TableHead className="text-right">Miqdor</TableHead>
              <TableHead className="text-right">Qoldiq</TableHead>
              <TableHead className="text-right">Summa</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.moves.length ? (
              data.moves.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="text-muted-foreground">
                    {new Date(m.created_at).toLocaleString("uz-UZ", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </TableCell>
                  <TableCell className="num">
                    {m.doc_id && m.doc_no ? (
                      <Link
                        to="/warehouse/doc"
                        search={{
                          turi: m.kind === "kirim" ? "kirim" : "chiqim",
                          id: m.doc_id,
                        }}
                        className="text-primary hover:underline"
                      >
                        {m.doc_no}
                      </Link>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {MOVE_KIND[m.kind] ?? m.kind}
                    {m.note && (
                      <span className="text-xs text-muted-foreground">
                        {" "}
                        · {m.note.replace(/^(Kirim|Sotuv|Sexga kirim) · /, "")}
                      </span>
                    )}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "num text-right font-semibold",
                      num(m.qty) > 0 ? "text-emerald-700" : "text-destructive",
                    )}
                  >
                    {num(m.qty) > 0 ? "+" : "−"}
                    {fmtQty(Math.abs(num(m.qty)))}
                  </TableCell>
                  <TableCell className="num text-right">
                    {fmtQty(m.balance)}
                  </TableCell>
                  <TableCell className="num text-right text-muted-foreground">
                    {m.amount != null ? fmtSum(m.amount) : "—"}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="text-center text-muted-foreground"
                >
                  Bu tovar bo'yicha hali harakat yo'q
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </section>
    </>
  )
}
