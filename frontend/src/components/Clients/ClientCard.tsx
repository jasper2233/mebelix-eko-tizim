import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"

import { ClientsService } from "@/client"
import { ClientCredit } from "@/components/Clients/ClientCredit"
import { ClientSegment } from "@/components/Clients/ClientSegment"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { StatusBadge } from "@/components/Common/StatusBadge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  deadlineTone,
  formatDate,
  formatMoney,
  PRIORITY_LABELS,
  PRIORITY_TEXT_CLASSES,
  remainingPayment,
  TERMINAL_STATUSES,
} from "@/lib/mes"
import { formatUzPhone } from "@/lib/validation"

/** Mijoz kartochkasi: qator ustiga bosilganda ochiladi.
 *
 * Reestrdagi savol "bu mijoz kim" emas, "bu mijoz nima buyurtma qilgan" —
 * shuning uchun asosiy joyni buyurtmalar ro'yxati egallaydi, kontakt esa
 * yuqoridagi bitta qatorga sig'adi. Buyurtma raqami buyurtma sahifasiga
 * havola: kartochka yakuniy manzil emas, o'tish joyi.
 */
export function ClientCard({
  clientId,
  onClose,
}: {
  clientId: number | null
  onClose: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["clients", "detail", clientId],
    queryFn: async () =>
      (
        await ClientsService.readClientDetail({
          path: { client_id: clientId as number },
        })
      ).data,
    enabled: clientId !== null,
  })
  // Qarz = qoldiq to'lovlar yig'indisi — mijoz kartochkasidagi asosiy savol
  // («bizga qarzi bormi?»). QORALAMA KIRMAYDI: u hali tasdiqlanmagan, mijoz
  // hech narsaga majbur emas. Boshqaruv panelidagi «qarz» ham aynan shu
  // filtrni ishlatadi (`reports.py` money bloki) — ikki ekran bir xil raqam bersin.
  const debt = (data?.orders ?? [])
    .filter(
      (o) =>
        o.status !== "cancelled" && o.status !== "draft" && o.amount != null,
    )
    .reduce((sum, o) => sum + Math.max(0, remainingPayment(o)), 0)

  return (
    <Dialog open={clientId !== null} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            {data?.full_name ?? "Mijoz"}
            {data && <ClientSegment segment={data.segment} />}
          </DialogTitle>
          <DialogDescription>
            {data
              ? `${data.orders_count} buyurtma · ${formatMoney(data.total_amount)} · aylanmaning ${(data.share_pct ?? 0).toFixed(1)}%${
                  debt > 0 ? ` · qarz ${formatMoney(debt)}` : ""
                }`
              : "Yuklanmoqda..."}
          </DialogDescription>
        </DialogHeader>

        {isLoading || !data ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <>
            <div className="grid gap-3 rounded-lg border border-border p-3 text-sm sm:grid-cols-4">
              <Maydon
                nom="Telefon"
                qiymat={data.phone ? formatUzPhone(data.phone) : null}
                num
              />
              <Maydon
                nom="Qo'shimcha telefon"
                qiymat={data.phone_alt ? formatUzPhone(data.phone_alt) : null}
                num
              />
              <Maydon nom="Manzil" qiymat={data.address} />
              <Maydon nom="Qo'shilgan" qiymat={formatDate(data.created_at)} />
              {data.notes && (
                <div className="sm:col-span-4">
                  <div className="text-xs uppercase tracking-wider text-muted-foreground">
                    Izoh
                  </div>
                  <div className="whitespace-pre-wrap">{data.notes}</div>
                </div>
              )}
            </div>

            <ClientCredit key={data.id} client={data} />

            <div className="max-h-[50vh] overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Buyurtma</TableHead>
                    <TableHead>Holat</TableHead>
                    <TableHead>Prioritet</TableHead>
                    <TableHead>Muddat</TableHead>
                    <TableHead className="text-right">Summa</TableHead>
                    <TableHead className="text-right">Qoldiq</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.orders?.length ? (
                    data.orders.map((o) => (
                      <TableRow key={o.id}>
                        <TableCell>
                          <Link
                            to="/orders/$orderId"
                            params={{ orderId: String(o.id) }}
                            className="font-semibold underline-offset-4 hover:underline"
                            onClick={onClose}
                          >
                            {o.number}
                          </Link>
                          {o.project_name && (
                            <span className="block text-sm text-muted-foreground">
                              {o.project_name}
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={o.status} />
                        </TableCell>
                        {/* Reestr bilan bir xil: prioritet rangi, faol buyurtmada
                            muddat ohangi (o'tgan — qizil, bugun — amber) */}
                        <TableCell>
                          <span
                            className={
                              PRIORITY_TEXT_CLASSES[o.priority] ??
                              "text-muted-foreground"
                            }
                          >
                            {PRIORITY_LABELS[o.priority] ?? o.priority}
                          </span>
                        </TableCell>
                        <TableCell
                          className={`num ${
                            TERMINAL_STATUSES.includes(o.status as never)
                              ? "text-muted-foreground"
                              : deadlineTone(o.deadline) === "overdue"
                                ? "font-semibold text-destructive"
                                : deadlineTone(o.deadline) === "today"
                                  ? "font-semibold text-amber-600"
                                  : "text-muted-foreground"
                          }`}
                        >
                          {formatDate(o.deadline)}
                        </TableCell>
                        <TableCell className="num text-right font-semibold">
                          {formatMoney(o.amount)}
                        </TableCell>
                        <TableCell className="num text-right">
                          {o.amount == null ? (
                            "—"
                          ) : remainingPayment(o) <= 0 ? (
                            <span className="text-muted-foreground">
                              To'langan
                            </span>
                          ) : (
                            formatMoney(remainingPayment(o))
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <EmptyRow colSpan={6}>
                      Bu mijozda hali buyurtma yo'q.
                    </EmptyRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

function Maydon({
  nom,
  qiymat,
  num = false,
}: {
  nom: string
  qiymat?: string | null
  num?: boolean
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted-foreground">
        {nom}
      </div>
      <div className={num ? "num" : undefined}>{qiymat || "—"}</div>
    </div>
  )
}
