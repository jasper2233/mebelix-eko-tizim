// Nomenklatura jadvali ustidagi «Yangi mahsulot» qatori (dizayndagidek — dialog emas, qatorning o'zi).
// Kod oldindan ko'rsatiladi (guruhning keyingi modeli yoki tanlangan modelning keyingi varianti), lekin
// HAQIQIY kodni server beradi: o'chirilgan kodlar ham band, ular bu ro'yxatda yo'q. Saqlangach qator
// ochiq qoladi va nom maydoniga qaytadi — ketma-ket bir nechta pozitsiya kiritiladi.

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { X } from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { type CatalogRow, CatalogService } from "@/client"
import { SelectField } from "@/components/Common/SelectField"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  type CatalogLetter,
  groupKey,
  parseNum,
  SEX_GROUPS,
} from "@/lib/warehouse"
import { handleError } from "@/utils"

const UNIT_OF: Record<CatalogLetter, string> = {
  M: "list",
  F: "dona",
  X: "xizmat",
  S: "dona",
}

export function NewItemRow({
  catalog,
  rows,
  defaultGroup,
  onClose,
}: {
  catalog: CatalogLetter
  /** Butun nomenklatura — guruhlar, modellar va kod ko'rinishi shundan */
  rows: CatalogRow[]
  defaultGroup?: string
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const groups = useMemo(() => {
    // Sex xo'jaligi guruhlari pozitsiyasiz ham tanlanadi (birinchisi shu yerdan ochiladi)
    const m = new Map<string, string>(catalog === "S" ? SEX_GROUPS : [])
    for (const r of rows)
      if (r.catalog === catalog) m.set(groupKey(r), r.group_name)
    return [...m].sort(([a], [b]) => a.localeCompare(b))
  }, [rows, catalog])
  const [gk, setGk] = useState(
    defaultGroup && groups.some(([k]) => k === defaultGroup)
      ? defaultGroup
      : (groups[0]?.[0] ?? ""),
  )
  const [model, setModel] = useState("")
  const empty = {
    name: "",
    description: "",
    unit: UNIT_OF[catalog],
    quantity: "",
    min: "",
    purchase: "",
    sale: "",
  }
  const [f, setF] = useState(empty)
  const nameRef = useRef<HTMLInputElement>(null)
  const xizmat = catalog === "X"

  // Guruhdagi modellar: `F-RC-008` → «F-RC-008 · Ruchka 5129 CC …»
  const models = useMemo(() => {
    const m = new Map<string, string>()
    for (const r of rows)
      if (groupKey(r) === gk) m.set(r.code.slice(0, 8), r.name)
    return [...m]
  }, [rows, gk])
  const preview = useMemo(() => {
    const codes = rows.filter((r) => groupKey(r) === gk).map((r) => r.code)
    if (model) {
      const v = Math.max(
        0,
        ...codes
          .filter((c) => c.startsWith(`${model}-`))
          .map((c) => Number(c.slice(9))),
      )
      return `${model}-${String(v + 1).padStart(2, "0")}`
    }
    const m = Math.max(0, ...codes.map((c) => Number(c.slice(5, 8))))
    return `${gk}-${String(m + 1).padStart(3, "0")}-01`
  }, [rows, gk, model])

  const create = useMutation({
    mutationFn: async () =>
      (
        await CatalogService.createCatalogItem({
          body: {
            catalog,
            group_code: gk.slice(2),
            model: model || null,
            name: f.name.trim(),
            description: f.description.trim() || null,
            unit: f.unit.trim() || UNIT_OF[catalog],
            quantity: xizmat ? 0 : (parseNum(f.quantity) ?? 0),
            min_quantity: xizmat ? null : parseNum(f.min),
            purchase_price: parseNum(f.purchase),
            sale_price: parseNum(f.sale),
          },
        })
      ).data,
    onSuccess: (it) => {
      toast.success(`${it.code} · ${it.name} qo'shildi`)
      setF({ ...empty, unit: f.unit })
      nameRef.current?.focus()
    },
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["catalog"] }),
  })
  const submit = () => {
    if (!f.name.trim()) {
      toast.error("Mahsulot nomini kiriting")
      nameRef.current?.focus()
      return
    }
    create.mutate()
  }
  const field =
    (k: keyof typeof empty) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setF({ ...f, [k]: e.target.value })
  const onEnter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault()
      submit()
    } else if (e.key === "Escape") onClose()
  }

  return (
    <div className="space-y-2 border-b border-l-4 border-l-primary bg-primary/5 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="num w-32 shrink-0 font-semibold text-primary">
          {preview}
        </span>
        <SelectField
          className="h-9 w-64"
          value={gk}
          onChange={(v) => {
            setGk(v)
            setModel("")
          }}
          options={groups.map(([k, n]) => ({ value: k, label: `${k} · ${n}` }))}
        />
        <SelectField
          className="h-9 w-72"
          value={model}
          onChange={setModel}
          emptyLabel="Yangi model"
          options={models.map(([k, n]) => ({
            value: k,
            label: `${k} · ${n}`,
          }))}
        />
        <Input
          ref={nameRef}
          autoFocus
          className="h-9 min-w-48 flex-1"
          placeholder="To'liq nomi"
          value={f.name}
          onChange={field("name")}
          onKeyDown={onEnter}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="h-9 min-w-48 flex-1"
          placeholder="Tavsif: rang / o'lcham"
          value={f.description}
          onChange={field("description")}
          onKeyDown={onEnter}
        />
        <Input
          className="h-9 w-24"
          placeholder="Birlik"
          value={f.unit}
          onChange={field("unit")}
          onKeyDown={onEnter}
        />
        {!xizmat && (
          <>
            <Input
              className="h-9 w-24"
              inputMode="decimal"
              placeholder="Qoldiq"
              value={f.quantity}
              onChange={field("quantity")}
              onKeyDown={onEnter}
            />
            <Input
              className="h-9 w-20"
              inputMode="decimal"
              placeholder="Min"
              value={f.min}
              onChange={field("min")}
              onKeyDown={onEnter}
            />
          </>
        )}
        <Input
          className="h-9 w-36"
          inputMode="decimal"
          placeholder={xizmat ? "Xarajat, so'm" : "Xarid, so'm"}
          value={f.purchase}
          onChange={field("purchase")}
          onKeyDown={onEnter}
        />
        <Input
          className="h-9 w-36"
          inputMode="decimal"
          placeholder={
            catalog === "F" ? "Sotuv (bo'sh — ustamadan)" : "Sotuv, so'm"
          }
          value={f.sale}
          onChange={field("sale")}
          onKeyDown={onEnter}
        />
        <Button size="sm" onClick={submit} disabled={create.isPending}>
          Qo'shish · Enter
        </Button>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Yopish"
          onClick={onClose}
        >
          <X />
        </Button>
      </div>
    </div>
  )
}
