// Mahsulotlar ombori — umumiy qoidalar va formatlash (docs/14 §8, «Qudrat Ombor» dizayni).
// Narx HISOBI serverda (`backend/app/services/warehouse.py`); bu yerda faqat ko'rsatish.

import type { CatalogRow, WarehousePricingOutput } from "@/client"

export const CATALOG_NAMES = {
  M: "Material",
  F: "Furnitura",
  X: "Xizmat",
  S: "Sex xo'jaligi",
} as const
export type CatalogLetter = keyof typeof CATALOG_NAMES

/** Sex xo'jaligi guruhlari — varaqda yo'q, birinchi pozitsiya shu nom bilan ochiladi.
 *  Backend'dagi nusxasi: `services/warehouse.py: SEX_GROUPS`. */
export const SEX_GROUPS: [string, string][] = [
  ["S-ZP", "Uskuna zapchastlari"],
  ["S-AS", "Sex asbob va sarfi"],
  ["S-KG", "Qog'oz va kanselyariya"],
  ["S-XJ", "Xo'jalik va himoya"],
  ["S-UP", "Upakovka materiali"],
]
/** Sexga berilishi mumkin bo'lgan furnitura guruhlari (asbob, kley) — dizayndagi takliflar filtri */
export const SEX_FROM_F = new Set(["F-AS", "F-KL"])

export const TIERS = [
  ["S", "Standart"],
  ["M", "Medium"],
  ["P", "Premium"],
] as const
export const TIER_NAME: Record<string, string> = Object.fromEntries(TIERS)
//: Sinf narxi qo'llanadigan guruhlar: `[guruh, nom, narx nimaga]` — LDSP va LMDF dekorlari,
//: narx BITTA LIST uchun. Backenddagi nusxasi: `services/warehouse.py: TIER_GROUPS`.
export const TIER_GROUPS = [
  ["M-LD", "LDSP", "1 list"],
  ["M-LM", "LMDF", "1 list"],
] as const
//: Sinf qo'yish mumkin bo'lgan guruhlar — yuqoridagining kalitlari
export const TIERABLE = new Set<string>(TIER_GROUPS.map(([gk]) => gk))

//: Kromka guruhi: narxi SINF emas, O'LCHAM bo'yicha (1 metr uchun) — `services/warehouse.py`
export const KROMKA_GROUP = "F-KM"
const KROMKA_OLCHAM = /(\d+)\s*[×xXхХ]\s*(\d+(?:[.,]\d+)?)\s*mm/i
/** Kromka nomidan o'lcham kaliti: «Kromka PVC 19×1 mm krem» → `19×1`. Varaqda alohida ustun
 *  yo'q, manba — nom. Backenddagi nusxasi: `services/warehouse.py: kromka_size`. */
export const kromkaSize = (name: string): string | null => {
  const m = KROMKA_OLCHAM.exec(name ?? "")
  return m ? `${m[1]}×${m[2].replace(".", ",")}` : null
}

export const num = (v: string | number | null | undefined): number =>
  v === null || v === undefined || v === "" ? 0 : Number(v) || 0

/** `12 800` — dizayndagi `fmt`: bo'shliq bilan guruhlangan butun son, birliksiz. */
export function fmt(v: string | number | null | undefined): string {
  const n = Math.round(num(v))
  return `${n < 0 ? "−" : ""}${String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " ")}`
}

/** Miqdor: kasr bo'lsa 3 xonagacha (`metr`), aks holda butun. */
export function fmtQty(v: string | number | null | undefined): string {
  const n = num(v)
  if (Number.isInteger(n)) return fmt(n)
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 3 })
}

export const fmtUsd = (v: number): string => `$${v.toFixed(2)}`

/** Foydalanuvchi kiritgan son: bo'shliq va vergul bilan ham («12 800», «0,29»). */
export const parseNum = (s: string): number | null => {
  const t = s.replace(/[\s ]/g, "").replace(",", ".")
  if (t === "") return null
  const n = Number(t)
  return Number.isFinite(n) && n >= 0 ? n : null
}

export const groupKey = (r: { catalog: string; group_code: string }) =>
  `${r.catalog}-${r.group_code}`

/** Kam qoldiq: chegara bor va qoldiq undan past. Material — faqat zaxiraga olingani
 *  (2 000+ dekorning hammasi omborda turmaydi), xizmat — hech qachon. */
export const isLow = (r: CatalogRow): boolean =>
  r.catalog !== "X" &&
  (r.catalog !== "M" || r.tracked) &&
  num(r.min_quantity) > 0 &&
  num(r.quantity) < num(r.min_quantity)

/** Xarid dollarda: kirimdan kelgani yoki so'mdagi xarid ÷ kurs. */
export const usdOf = (r: CatalogRow, rate: number): number | null =>
  r.purchase_usd != null
    ? num(r.purchase_usd)
    : r.purchase_price != null && rate > 0
      ? Math.round((num(r.purchase_price) / rate) * 100) / 100
      : null

/** Amaldagi ustama: pozitsiyaniki → guruhniki → umumiy (server bilan bir xil). */
export function markupOf(
  r: CatalogRow,
  p: WarehousePricingOutput | undefined,
): number | null {
  if (r.markup_pct != null) return num(r.markup_pct)
  const g = p?.markup_groups?.[groupKey(r)]
  if (g != null) return num(g)
  return p?.markup_all != null ? num(p.markup_all) : null
}

/** Excel o'qiy oladigan CSV (`;`, UTF-8 BOM) — dizayndagi `download`. */
export function downloadCsv(
  name: string,
  rows: (string | number | null | undefined)[][],
) {
  const csv = rows
    .map((r) =>
      r
        .map((c) => {
          const s = c == null ? "" : String(c)
          return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
        })
        .join(";"),
    )
    .join("\r\n")
  const url = URL.createObjectURL(
    new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8" }),
  )
  const a = document.createElement("a")
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, 500)
}
