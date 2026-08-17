import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Minus, Plus } from "lucide-react"
import { useState } from "react"

import { OrdersService, type StockItemRead, StockService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { crudCallbacks } from "@/queries/mes"

import { num, qty } from "./format"

const digits = (v: string) => v.replace(/[^\d.]/g, "")

/** KIRIM / CHIQIM — qoldiqni qo'lda yozish emas, O'ZGARISH miqdori.
 *
 * Omborchi "20 ta keldi" deb o'ylaydi, "endi 174 ta bo'ldi" deb emas. Delta
 * bo'lgani uchun ikki kishi bir vaqtda yozsa ham hech biri yo'qolmaydi.
 *
 * Chiqimning TURI so'raladi, chunki miqdorning o'zi javob bermaydi: 12 ta petlya
 * kamaydi — buyurtmagami, yo'qoldimi? Hisobot aynan shu farqqa tayanadi
 * (buyurtmada TANNARX). Sotuv bu yerda yo'q — u alohida hujjat, mijoz va to'lov
 * bilan (`SaleDialog`). */
export function MoveDialog({
  item,
  onClose,
}: {
  item: StockItemRead
  onClose: () => void
}) {
  const [amount, setAmount] = useState("")
  const [kind, setKind] = useState<"kirim" | "buyurtma" | "chiqim">("kirim")
  const [orderId, setOrderId] = useState("")
  const [note, setNote] = useState("")
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["stock"], "Qoldiq yangilandi")

  // Buyurtmalar ro'yxati FAQAT kerak bo'lganda — kirim yo'lida u ochilmaydi
  const { data: orders } = useQuery({
    queryKey: ["orders", "for-stock"],
    queryFn: () => OrdersService.readOrders({ limit: 100 }),
    enabled: kind === "buyurtma",
    staleTime: 60_000,
  })

  const value = Number(amount)
  const sign = kind === "kirim" ? 1 : -1
  const after = num(item.qty) + sign * value

  const mutation = useMutation({
    mutationFn: () =>
      StockService.moveStockItem({
        itemId: item.id,
        requestBody: {
          delta: String(sign * value),
          kind,
          order_id: kind === "buyurtma" ? Number(orderId) : null,
          note: note.trim() || null,
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })

  const valid =
    amount !== "" &&
    value > 0 &&
    after >= 0 &&
    (kind !== "buyurtma" || !!orderId)

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{item.name}</DialogTitle>
          <DialogDescription>
            {item.code} · hozirgi qoldiq <b>{qty(item.qty)}</b>
            {item.unit ? ` ${item.unit}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-3 gap-2">
          {(
            [
              ["kirim", "Kirim", <Plus key="i" />],
              ["buyurtma", "Buyurtmaga", <Minus key="o" />],
              ["chiqim", "Hisobdan", <Minus key="w" />],
            ] as const
          ).map(([k, label, icon]) => (
            <Button
              key={k}
              type="button"
              variant={kind === k ? "default" : "outline"}
              onClick={() => setKind(k)}
            >
              {icon} {label}
            </Button>
          ))}
        </div>

        {kind === "buyurtma" && (
          <select
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            className="h-10 w-full rounded-md border bg-card px-2 text-sm"
          >
            <option value="">— buyurtmani tanlang —</option>
            {(orders?.data ?? []).map((o) => (
              <option key={o.id} value={o.id}>
                {o.number}
                {o.project_name ? ` · ${o.project_name}` : ""}
              </option>
            ))}
          </select>
        )}

        <Input
          value={amount}
          onChange={(e) => setAmount(digits(e.target.value))}
          inputMode="decimal"
          placeholder="Miqdor"
          className="h-12 text-center text-xl"
          autoFocus
        />
        <Input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={
            kind === "kirim"
              ? "Izoh (kimdan keldi)"
              : kind === "buyurtma"
                ? "Izoh (nima uchun)"
                : "Izoh (sabab: yaroqsiz, yo'qolgan)"
          }
          maxLength={200}
        />

        <p className="text-sm text-muted-foreground">
          Yangi qoldiq:{" "}
          <b className={after < 0 ? "text-(--status-cancelled)" : ""}>
            {amount === "" ? qty(item.qty) : after}
          </b>
          {after < 0 && " — qoldiq yetmaydi"}
        </p>

        <DialogFooter>
          <LoadingButton
            disabled={!valid}
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Saqlash
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
