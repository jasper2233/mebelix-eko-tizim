import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { ClientsService, type StockItemRead, StockService } from "@/client"
import { SelectField } from "@/components/Common/SelectField"
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

import { num, uzs } from "./format"

const digits = (v: string) => v.replace(/[^\d.]/g, "")

/** Materiallar omboridan SOTUV — mijozga to'g'ridan-to'g'ri.
 *
 * To'lanmagan qism qarz bo'lib qoladi, shuning uchun qarzda MIJOZ majburiy:
 * kimdan undirishni bilmasak, yozuvning ma'nosi yo'q. Naqd to'langan sotuvda
 * mijoz shart emas — o'tkinchi xaridor.
 *
 * Hozircha BITTA tovar. Backend ko'p satrni qo'llab-quvvatlaydi
 * (`lines[]`), ya'ni savat keyin faqat frontendda quriladi. */
export function SaleDialog({
  item,
  onClose,
}: {
  item: StockItemRead
  onClose: () => void
}) {
  const [amount, setAmount] = useState("1")
  const [price, setPrice] = useState(
    item.sale_uzs ? String(num(item.sale_uzs)) : "",
  )
  const [clientId, setClientId] = useState("")
  const [paid, setPaid] = useState("")
  const [method, setMethod] = useState<"cash" | "card" | "transfer">("cash")
  const [note, setNote] = useState("")

  const { data: clients } = useQuery({
    queryKey: ["clients", "for-sale"],
    queryFn: () => ClientsService.readClients({ limit: 100 }),
    staleTime: 60_000,
  })

  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["stock"], "Sotuv rasmiylashtirildi")
  const total = Number(amount) * Number(price || 0)
  const paidNum = paid === "" ? total : Number(paid)
  const debt = total - paidNum

  const mutation = useMutation({
    mutationFn: () =>
      StockService.createSale({
        requestBody: {
          lines: [{ item_id: item.id, qty: amount, price_uzs: price || null }],
          client_id: clientId ? Number(clientId) : null,
          paid_uzs: String(paidNum),
          method,
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
    Number(amount) > 0 &&
    Number(amount) <= num(item.qty) &&
    Number(price) > 0 &&
    paidNum >= 0 &&
    paidNum <= total &&
    (debt === 0 || !!clientId)

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Sotuv — {item.name}</DialogTitle>
          <DialogDescription>
            {item.code} · qoldiq {num(item.qty)}
            {item.unit ? ` ${item.unit}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Miqdor">
            <Input
              value={amount}
              onChange={(e) => setAmount(digits(e.target.value))}
              inputMode="decimal"
              autoFocus
            />
          </Field>
          <Field label="Narx (so'm)">
            <Input
              value={price}
              onChange={(e) => setPrice(digits(e.target.value))}
              inputMode="decimal"
            />
          </Field>
        </div>

        <div className="rounded-md border bg-muted/40 px-3 py-2 text-sm">
          Jami: <b className="num">{uzs(total)} so'm</b>
        </div>

        <Field label="Mijoz — qarzga sotilsa MAJBURIY">
          <SelectField
            value={clientId}
            onChange={setClientId}
            emptyLabel="O'tkinchi xaridor"
            placeholder="Mijozni tanlang"
            options={(clients?.data ?? []).map((c) => ({
              value: String(c.id),
              label: c.full_name,
              hint: c.phone ?? undefined,
            }))}
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="To'landi (bo'sh = to'liq)">
            <Input
              value={paid}
              onChange={(e) => setPaid(digits(e.target.value))}
              inputMode="decimal"
              placeholder={String(total)}
            />
          </Field>
          <Field label="Usuli">
            <SelectField
              value={method}
              onChange={(v) => setMethod(v as "cash" | "card" | "transfer")}
              options={[
                { value: "cash", label: "Naqd" },
                { value: "card", label: "Karta" },
                { value: "transfer", label: "O'tkazma" },
              ]}
            />
          </Field>
        </div>

        {debt > 0 && (
          <p className="text-sm text-(--status-cancelled)">
            Qarz: <b className="num">{uzs(debt)} so'm</b>
            {!clientId && " — mijozni tanlang"}
          </p>
        )}

        <Field label="Izoh">
          <Input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={200}
          />
        </Field>

        <DialogFooter>
          <LoadingButton
            disabled={!valid}
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Sotish
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Qarzni to'lash — to'liq yoki qisman. */
export function PaymentDialog({
  saleId,
  debt,
  onClose,
}: {
  saleId: number
  debt: number
  onClose: () => void
}) {
  const [amount, setAmount] = useState(String(debt))
  const [method, setMethod] = useState<"cash" | "card" | "transfer">("cash")
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["stock"], "To'lov qabul qilindi")
  const mutation = useMutation({
    mutationFn: () =>
      StockService.addSalePayment({
        saleId,
        requestBody: { amount_uzs: amount, method },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })
  const value = Number(amount)

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>To'lov qabul qilish</DialogTitle>
          <DialogDescription>
            Qarz: <b className="num">{uzs(debt)} so'm</b>
          </DialogDescription>
        </DialogHeader>
        <Input
          value={amount}
          onChange={(e) => setAmount(digits(e.target.value))}
          inputMode="decimal"
          className="h-12 text-center text-xl"
          autoFocus
        />
        <div className="flex gap-2">
          {(
            [
              ["cash", "Naqd"],
              ["card", "Karta"],
              ["transfer", "O'tkazma"],
            ] as const
          ).map(([m, label]) => (
            <Button
              key={m}
              type="button"
              variant={method === m ? "default" : "outline"}
              className="flex-1"
              onClick={() => setMethod(m)}
            >
              {label}
            </Button>
          ))}
        </div>
        <DialogFooter>
          <LoadingButton
            disabled={!(value > 0 && value <= debt)}
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

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="grid gap-1.5">
      <span className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {children}
    </div>
  )
}
