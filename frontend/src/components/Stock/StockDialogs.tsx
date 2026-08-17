import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { type StockGroup, type StockItemRead, StockService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { SelectField } from "@/components/Common/SelectField"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { crudCallbacks } from "@/queries/mes"
import { num, qty } from "./format"

const digits = (v: string) => v.replace(/[^\d.]/g, "")

/** Pozitsiya qo'shish / tahrirlash — bitta dialog, ikkala ish uchun.
 *
 * KOD SO'RALMAYDI: yangi pozitsiyada uni server beradi (guruhdagi eng katta
 * model raqami + 1). Excel katalogida "Keyingi bo'sh model kodi" ustunini odam
 * qo'lda yuritardi — o'sha ish serverga o'tdi. Mavjud modelning boshqa rangi
 * kerak bo'lsa kod qo'lda yoziladi (`F-RC-001-04`).
 *
 * Guruh mavjudlaridan tanlanadi yoki yangisi yoziladi: guruhlar alohida jadval
 * emas, pozitsiyalarning o'zidan yig'iladi.
 *
 * Tahrirlashda QOLDIQ maydoni yo'q — u faqat "Kirim / Chiqim" orqali o'zgaradi,
 * aks holda audit izi uzilib, qoldiq qayerdan kelganini hech kim aytolmasdi. */
export function ItemDialog({
  groups,
  item,
  onClose,
}: {
  groups: StockGroup[]
  item?: StockItemRead
  onClose?: () => void
}) {
  const editing = !!item
  const [open, setOpen] = useState(editing)
  // Kodni qo'lda kiritish — kamdan-kam holat, shuning uchun yashirin
  const [manualCode, setManualCode] = useState(false)
  const [form, setForm] = useState({
    catalog: item?.catalog ?? "F",
    group: item ? `${item.catalog}|${item.group_code}` : "",
    newGroupCode: "",
    newGroupName: "",
    code: "",
    name: item?.name ?? "",
    variant: item?.variant ?? "",
    size: item?.size ?? "",
    unit: item?.unit ?? "",
    qty: "",
    min_qty: item ? qty(item.min_qty) : "",
    purchase_uzs: item?.purchase_uzs ? String(num(item.purchase_uzs)) : "",
    sale_uzs: item?.sale_uzs ? String(num(item.sale_uzs)) : "",
    note: item?.note ?? "",
  })
  const set = (k: keyof typeof form, v: string) =>
    setForm((f) => ({ ...f, [k]: v }))

  const queryClient = useQueryClient()
  const cb = crudCallbacks(
    queryClient,
    ["stock"],
    editing ? "Pozitsiya yangilandi" : "Pozitsiya qo'shildi",
  )
  const mutation = useMutation({
    mutationFn: () => {
      const shared = {
        name: form.name.trim(),
        variant: form.variant.trim() || null,
        size: form.size.trim() || null,
        unit: form.unit.trim() || null,
        min_qty: form.min_qty === "" ? "0" : form.min_qty,
        purchase_uzs: form.purchase_uzs || null,
        sale_uzs: form.sale_uzs || null,
        note: form.note.trim() || null,
      }
      if (item)
        return StockService.updateStockItem({
          itemId: item.id,
          requestBody: shared,
        })
      const [catalog, groupCode] = form.group
        ? form.group.split("|")
        : [form.catalog, form.newGroupCode.toUpperCase()]
      const groupName =
        groups.find((g) => `${g.catalog}|${g.group_code}` === form.group)
          ?.group_name ?? form.newGroupName.trim()
      return StockService.createStockItem({
        requestBody: {
          ...shared,
          code: form.code.trim() || null,
          catalog: catalog as "F" | "M",
          group_code: groupCode,
          group_name: groupName,
          qty: form.qty === "" ? "0" : form.qty,
        },
      })
    },
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      setOpen(false)
      onClose?.()
    },
  })

  const newGroup = !form.group
  const valid =
    form.name.trim().length > 1 &&
    (editing ||
      !newGroup ||
      (form.newGroupCode.trim().length >= 2 &&
        form.newGroupName.trim().length > 1))

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (!v) onClose?.()
      }}
    >
      {!editing && (
        <DialogTrigger asChild>
          <Button>
            <Plus /> Pozitsiya qo'shish
          </Button>
        </DialogTrigger>
      )}
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? item.name : "Yangi pozitsiya"}</DialogTitle>
          <DialogDescription>
            {editing
              ? `${item.code} · qoldiqni "Kirim / Chiqim" bilan o'zgartiring`
              : "Kodni server o'zi beradi — guruhni tanlash kifoya"}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          {!editing && (
            <>
              <Field label="Guruh">
                <SelectField
                  value={form.group}
                  onChange={(v) => set("group", v)}
                  emptyLabel="Yangi guruh ochish"
                  placeholder="Guruhni tanlang"
                  options={groups.map((g) => ({
                    value: `${g.catalog}|${g.group_code}`,
                    label: g.group_name,
                    hint: `${g.catalog}-${g.group_code}`,
                  }))}
                />
              </Field>
              {newGroup && (
                <div className="grid grid-cols-3 gap-3">
                  <Field label="Katalog">
                    <SelectField
                      value={form.catalog}
                      onChange={(v) => set("catalog", v)}
                      options={[
                        { value: "F", label: "Furnitura" },
                        { value: "M", label: "Material" },
                      ]}
                    />
                  </Field>
                  <Field label="Guruh kodi">
                    <Input
                      value={form.newGroupCode}
                      onChange={(e) =>
                        set(
                          "newGroupCode",
                          e.target.value.replace(/[^a-zA-Z]/g, "").slice(0, 4),
                        )
                      }
                      placeholder="RC"
                      className="uppercase"
                    />
                  </Field>
                  <Field label="Guruh nomi">
                    <Input
                      value={form.newGroupName}
                      onChange={(e) => set("newGroupName", e.target.value)}
                      placeholder="Ruchkalar"
                    />
                  </Field>
                </div>
              )}
              {/* Kod SO'RALMAYDI: uni server beradi. Ilgari bu yerda bo'sh
                  matn maydoni turib, yorlig'i "bo'sh qoldiring" deb yozardi —
                  ya'ni foydalanuvchidan hech narsa qilmaslikni so'rardi.
                  Maydon faqat BITTA holatda kerak: mavjud modelning yangi
                  varianti (o'sha ruchkaning boshqa rangi), shuning uchun u
                  ochib qo'yiladigan holatda. */}
              {manualCode ? (
                <Field label="Kod — mavjud modelning varianti">
                  <Input
                    value={form.code}
                    onChange={(e) => set("code", e.target.value.toUpperCase())}
                    placeholder="F-RC-001-04"
                    autoFocus
                  />
                </Field>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Kod avtomatik shakllanadi.{" "}
                  <button
                    type="button"
                    className="underline underline-offset-4 hover:text-foreground"
                    onClick={() => setManualCode(true)}
                  >
                    Mavjud modelning varianti
                  </button>
                </p>
              )}
            </>
          )}

          <Field label="Nomi">
            <Input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="Ruchka 0014 bronza 128"
            />
          </Field>

          <div className="grid grid-cols-3 gap-3">
            <Field label="Rang / struktura">
              <Input
                value={form.variant}
                onChange={(e) => set("variant", e.target.value)}
              />
            </Field>
            <Field label="O'lcham">
              <Input
                value={form.size}
                onChange={(e) => set("size", e.target.value)}
              />
            </Field>
            <Field label="O'lchov">
              <Input
                value={form.unit}
                onChange={(e) => set("unit", e.target.value)}
                placeholder="dona"
              />
            </Field>
          </div>

          <div className="grid grid-cols-3 gap-3">
            {!editing && (
              <Field label="Boshlang'ich qoldiq">
                <Input
                  value={form.qty}
                  onChange={(e) => set("qty", digits(e.target.value))}
                  inputMode="decimal"
                />
              </Field>
            )}
            <Field label="Min zaxira">
              <Input
                value={form.min_qty}
                onChange={(e) => set("min_qty", digits(e.target.value))}
                inputMode="decimal"
              />
            </Field>
            <Field label="Xarid (so'm)">
              <Input
                value={form.purchase_uzs}
                onChange={(e) => set("purchase_uzs", digits(e.target.value))}
                inputMode="decimal"
              />
            </Field>
            <Field label="Sotuv (so'm)">
              <Input
                value={form.sale_uzs}
                onChange={(e) => set("sale_uzs", digits(e.target.value))}
                inputMode="decimal"
              />
            </Field>
          </div>

          <Field label="Izoh">
            <Input
              value={form.note}
              onChange={(e) => set("note", e.target.value)}
              maxLength={200}
            />
          </Field>
        </div>

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

export function DeleteItem({
  item,
  onClose,
}: {
  item: StockItemRead | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["stock"], "Pozitsiya o'chirildi")
  const mutation = useMutation({
    mutationFn: (id: number) => StockService.deleteStockItem({ itemId: id }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })
  return (
    <ConfirmDialog
      open={!!item}
      onOpenChange={(v) => !v && onClose()}
      title="Pozitsiyani o'chirish"
      description={
        item
          ? `${item.code} — ${item.name} ro'yxatdan chiqadi. Kirim/chiqim tarixi audit logda qoladi.`
          : ""
      }
      confirmText="O'chirish"
      destructive
      loading={mutation.isPending}
      onConfirm={() => item && mutation.mutate(item.id)}
    />
  )
}
