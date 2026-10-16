// «Excel'dan yuklash» — shablon bo'yicha YANGI pozitsiyalar (dizayndagi `parseTemplate`).
// Excel'da to'ldirilgan jadval nusxalab qo'yiladi (Tab bilan ajraladi) yoki CSV fayl tanlanadi.
// Brauzer qatorlarni tekshiradi va oldindan ko'rsatadi; server hammasini BITTA tranzaksiyada
// yaratadi — bitta xato qator bo'lsa hech narsa yozilmaydi.

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Download, FileUp } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import {
  type CatalogItemCreate,
  type CatalogRow,
  CatalogService,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { downloadCsv, groupKey, parseNum, SEX_GROUPS } from "@/lib/warehouse"
import { handleError } from "@/utils"

export const TEMPLATE_HEAD = [
  "Tur",
  "Guruh kodi",
  "Nom",
  "Tavsif",
  "Birlik",
  "Boshlang'ich qoldiq",
  "Min zaxira",
  "Joy",
  "Xarid narxi (so'm)",
  "Sotuv narxi (so'm)",
]
const EXAMPLE = [
  [
    "S",
    "S-ZP",
    "Pila diski 300×3,2×30 Z96",
    "raspil stanogi uchun",
    "dona",
    "4",
    "2",
    "B-01-1",
    "450000",
    "",
  ],
  [
    "S",
    "S-KG",
    "Qog'oz A4 500 varaq",
    "chizma, hujjat",
    "pachka",
    "10",
    "3",
    "B-03-1",
    "45000",
    "",
  ],
  [
    "F",
    "F-RC",
    "Ruchka namuna 128 mm qora",
    "qora · 128 mm",
    "dona",
    "100",
    "20",
    "A-01-1",
    "12000",
    "",
  ],
  [
    "M",
    "M-HD",
    "HDF orqa devor 2800x2070x3",
    "oq",
    "list",
    "10",
    "",
    "",
    "95000",
    "120000",
  ],
  [
    "X",
    "X-PR",
    "Prisadka — maxsus teshik",
    "",
    "xizmat",
    "",
    "",
    "",
    "",
    "3000",
  ],
]

function parse(text: string, groups: Set<string>) {
  const ok: CatalogItemCreate[] = []
  const errs: string[] = []
  text.split(/\r?\n/).forEach((raw, ix) => {
    if (!raw.trim()) return
    const c = raw.split(/\t|;/).map((s) => s.trim().replace(/^"|"$/g, ""))
    if (/^tur$/i.test(c[0]) || c[0].startsWith("#")) return
    const gk = (c[1] ?? "").toUpperCase()
    const name = c[2] ?? ""
    if (!name) return
    if (!groups.has(gk)) {
      errs.push(`${ix + 1}-qator: «${c[1] ?? ""}» guruh kodi yo'q`)
      return
    }
    const tur = (c[0] ?? "").trim().toUpperCase()[0]
    if (tur && tur !== gk[0]) {
      errs.push(`${ix + 1}-qator: ${gk} guruhi «${c[0]}» turiga tegishli emas`)
      return
    }
    const xizmat = gk[0] === "X"
    ok.push({
      catalog: gk[0] as "M" | "F" | "X" | "S",
      group_code: gk.slice(2),
      name,
      description: c[3] || null,
      unit: c[4] || (gk[0] === "M" ? "list" : xizmat ? "xizmat" : "dona"),
      quantity: xizmat ? 0 : (parseNum(c[5] ?? "") ?? 0),
      min_quantity: xizmat ? null : parseNum(c[6] ?? ""),
      location: c[7] || null,
      purchase_price: parseNum(c[8] ?? ""),
      sale_price: parseNum(c[9] ?? ""),
    })
  })
  return { ok, errs }
}

export function ImportDialog({
  open,
  onOpenChange,
  rows,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  rows: CatalogRow[]
}) {
  const queryClient = useQueryClient()
  const [text, setText] = useState("")
  const groups = useMemo(
    () => new Set([...rows.map(groupKey), ...SEX_GROUPS.map(([k]) => k)]),
    [rows],
  )
  const { ok, errs } = useMemo(() => parse(text, groups), [text, groups])

  const run = useMutation({
    mutationFn: async () =>
      (await CatalogService.importCatalogItems({ body: { rows: ok } })).data,
    onSuccess: (r) => {
      toast.success(`${r.codes.length} ta yangi mahsulot qo'shildi`)
      setText("")
      onOpenChange(false)
    },
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["catalog"] }),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Excel'dan yuklash — yangi mahsulotlar</DialogTitle>
          <DialogDescription>
            Shablonni yuklab oling, Excel'da to'ldiring va qatorlarni shu yerga
            nusxalab qo'ying (yoki CSV faylni tanlang). Kod avtomatik beriladi.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              downloadCsv("yangi-mahsulot-shablon.csv", [
                TEMPLATE_HEAD,
                ...EXAMPLE,
              ])
            }
          >
            <Download /> Shablonni yuklab olish
          </Button>
          <Button variant="outline" size="sm" asChild>
            <label className="cursor-pointer">
              <FileUp /> CSV faylni tanlash
              <input
                type="file"
                accept=".csv,.txt"
                className="sr-only"
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  if (file) setText((await file.text()).replace(/^﻿/, ""))
                  e.target.value = ""
                }}
              />
            </label>
          </Button>
        </div>
        <Textarea
          rows={10}
          className="num text-xs"
          placeholder={TEMPLATE_HEAD.join("\t")}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <p className="text-sm">
          Tayyor: <b>{ok.length}</b> qator
          {errs.length > 0 && (
            <span className="text-destructive">
              {" "}
              · {errs.length} ta xato: {errs.slice(0, 3).join(" · ")}
            </span>
          )}
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Bekor qilish
          </Button>
          <Button
            disabled={!ok.length || errs.length > 0 || run.isPending}
            onClick={() => run.mutate()}
          >
            {ok.length} ta mahsulotni qo'shish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
