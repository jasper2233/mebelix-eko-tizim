// MES domain constants: Uzbek labels + stage colors (TZ 3, 4.4, 6.1)

import type { UserRole } from "@/client"

export const ORDER_STATUS_LABELS: Record<string, string> = {
  draft: "QORALAMA",
  technical_review: "TEXNOLOGDA",
  production: "JARAYONDA",
  completed: "TAYYOR",
  delivered: "TOPSHIRILDI",
  cancelled: "BEKOR QILINGAN",
}

export const ORDER_STATUS_COLORS: Record<string, string> = {
  draft: "var(--status-draft)",
  technical_review: "var(--status-review)",
  production: "var(--status-production)",
  completed: "var(--status-completed)",
  delivered: "var(--status-delivered)",
  cancelled: "var(--status-cancelled)",
}

// Terminal (yakuniy) holatlar: yakunlangan ish sanoqqa kirmaydi
export const TERMINAL_STATUSES = ["delivered", "cancelled"] as const

export const PRIORITY_LABELS: Record<string, string> = {
  low: "Past",
  medium: "O'rta",
  high: "Yuqori",
  urgent: "Shoshilinch",
}

// Prioritet ranglari bitta manbadan: select nuqtalari va reestr matni
export const PRIORITY_DOT_CLASSES: Record<string, string> = {
  low: "bg-slate-300",
  medium: "bg-slate-400",
  high: "bg-orange-500",
  urgent: "bg-red-500",
}

export const PRIORITY_TEXT_CLASSES: Record<string, string> = {
  low: "text-muted-foreground",
  medium: "text-muted-foreground",
  high: "font-semibold text-orange-700",
  urgent: "font-bold text-red-600",
}

export const PRIORITY_BADGE_CLASSES: Record<string, string> = {
  low: "bg-muted text-muted-foreground",
  medium: "bg-muted text-muted-foreground",
  high: "bg-orange-600 text-white",
  urgent: "bg-red-600 text-white",
}

export const POST_COLORS: Record<string, string> = {
  ARRA: "var(--post-arra)",
  KROMKA: "var(--post-kromka)",
  OVAL: "var(--post-oval)",
  PRISADKA: "var(--post-prisadka)",
  ROVER: "var(--post-rover)",
  STOLYARKA: "var(--post-stolyarka)",
  BOYOQ: "var(--post-boyoq)",
  UPAKOVKA: "var(--post-upakovka)",
  TMO: "var(--post-tmo)",
}

/** Rangning oq bilan `pct`% tinti — chip/katak fonlari uchun. */
export const mixTint = (color: string, pct: number) =>
  `color-mix(in srgb, ${color} ${pct}%, white)`

/**
 * Chip rang formulasi (WCAG AA): matn rangning to'qroq variantida, fon oq tint.
 * Sof rang o'z tinti ustida atigi 4.25-4.35:1 berardi — matn ham, fon ham bir
 * tondan olingani uchun. `78%, black` bilan nisbat 6.18-7.01:1 ga chiqadi va
 * chipning yengil ko'rinishi saqlanadi. Ilgari PostBadge/StatusBadge/OrderMatrix
 * shu satrni alohida-alohida takrorlardi; fon foizini komponent o'zi tanlaydi.
 */
export const chipColors = (color: string, bgPct: number) => ({
  color: `color-mix(in srgb, ${color} 78%, black)`,
  backgroundColor: mixTint(color, bgPct),
})

// Tsexning "Jarayon uchun kodlar" jadvali — backend `PROCESS_POSTS`
// (services/giblab/models.py) bilan bir xil bo'lishi shart. Bu yerda faqat
// KO'RSATISH uchun: marshrutni backend quradi, frontend esa operatorga qaysi
// AMAL ekanini aytadi. Noma'lum kodda chip umuman chiqmaydi (xato nom emas).
export const PROCESS_OPS: Record<number, { name: string; post: string }> = {
  1: { name: "Raspil", post: "ARRA" },
  2: { name: "45° kesish", post: "ARRA" },
  3: { name: "Kromka", post: "KROMKA" },
  4: { name: "Fasat kromka", post: "KROMKA" },
  5: { name: "Oval kromka", post: "OVAL" },
  6: { name: "Prisadka", post: "PRISADKA" },
  7: { name: "Rover", post: "ROVER" },
  8: { name: "Bo'yoq", post: "BOYOQ" },
  9: { name: "Baget", post: "STOLYARKA" },
  10: { name: "Utalshonka", post: "STOLYARKA" },
  11: { name: "G petlya o'ngdan", post: "STOLYARKA" },
  12: { name: "G petlya chapdan", post: "STOLYARKA" },
  13: { name: "V petlya o'ngdan", post: "STOLYARKA" },
  14: { name: "V petlya chapdan", post: "STOLYARKA" },
  // Qadoqlash texnolog tanlaydigan jarayon emas — anketadagi bayroq qo'shadi.
  // Bu yerda faqat NOM uchun (chek marshruti, terminal chipi).
  15: { name: "Qadoqlash", post: "UPAKOVKA" },
  16: { name: "TMO qabuli", post: "TMO" },
}

/**
 * Detallar matritsasida ko'rinadigan postlar — STANDART detalning butun yo'li.
 * Rover, stolyarka, bo'yoq va oval kromka faylga qarab avtomatik berilmaydi:
 * roverdan chiqqan detal keyin bo'yalishi mumkinligini fayl bilmaydi. Ular
 * "Nostandart detallar" tabida qo'lda chiziladi.
 */
export const STANDARD_MATRIX_POSTS = ["ARRA", "KROMKA", "PRISADKA"]

/** Nostandart marshrut faqat shulardan boshlanadi — chek o'sha postda chiqadi. */
export const ROUTE_START_POSTS = ["ARRA", "ROVER"]

// Rollar manbasi — backend enum'i (generatsiya qilingan UserRole); yorliq
// yozilmagan yangi rol build'ni yiqitadi
export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  director: "Direktor",
  manager: "Menejer",
  texnolog: "Texnolog",
  terminal: "Terminal",
  tablo: "TABLO",
  arrachi: "Arrachi",
  kromkachi: "Kromkachi",
  ovalchi: "Oval kromkachi",
  prisadkachi: "Prisadkachi",
  roverchi: "Roverchi",
  stolyar: "Stolyar",
  boyoqchi: "Bo'yoqchi",
  upakovkachi: "Qadoqlovchi",
  omborchi: "TMO omborchisi",
  material_omborchi: "Materiallar omborchisi",
}

// Sahifa huquqi BITTA joyda: sidebar menyusi ham, route guard ham shu ikkisini
// ishlatadi. Ilgari ikkalasi alohida yozilgani uchun "menyuda ko'rinadi, ochsang
// bosh sahifaga uloqtiradi" holati chiqib qolgandi.
// Rol nomi UserRole (backend enum'i) dan: rol qayta nomlansa solishtirish
// jimgina "false" bo'lib qolmasin — ROLE_LABELS kabi build yiqilsin
type RoleUser = { role?: UserRole | null; is_superuser?: boolean | null }
/** Foydalanuvchilarni boshqarish — telefon raqamlar ochiladi (backend SuperUserDep) */
export const isSuperuser = (u?: RoleUser | null) => Boolean(u?.is_superuser)
/** Tizim sozlamalari: printer agentlar, loglar/audit izi (backend AdminUser) */
export const isAdmin = (u?: RoleUser | null) =>
  Boolean(u?.is_superuser || u?.role === "admin")
/** Boshqaruv sahifalari (mijozlar, hodimlar, hisobotlar): admin + manager + direktor */
export const isManagement = (u?: RoleUser | null) =>
  isAdmin(u) || u?.role === "manager" || u?.role === "director"
/** Ishlab chiqarish sahifalari (buyurtmalar, ish markazlari, ombor): boshqaruv + texnolog */
export const isProductionStaff = (u?: RoleUser | null) =>
  isManagement(u) || u?.role === "texnolog"
/** Materiallar ombori — qoldiqni yuritadigan xodim + ofis (u yo'qligida ish
 * to'xtamasin). `omborchi` bu yerda EMAS: u TMO da tayyor mahsulot qabul
 * qiladi va monoblokda ishlaydi, bu esa boshqa odam va boshqa joy. */
export const isStockStaff = (u?: RoleUser | null) =>
  isProductionStaff(u) || isStockOnly(u)
/** FAQAT omborni ko'radigan rol. `_layout` uni kirishda `/stock` ga yuboradi,
 * ya'ni menyudagi boshqa hamma narsa u uchun boshi berk ko'cha: bosilsa
 * qaytarib yuboriladi. Shuning uchun ular ro'yxatdan ham olib tashlanadi. */
export const isStockOnly = (u?: RoleUser | null) =>
  u?.role === "material_omborchi"

// Ish markazi bog'lami MAJBURIY rollar — qurilma akkauntlari (Admin dialoglarida
// rol tanlovi, machine_id validatsiyasi va bog'lamni uzish shu ro'yxatdan)
export const MACHINE_BOUND_ROLES = ["terminal", "tablo"] as const

/** Lavozimlar — tizim biladigan ro'yxat. Lavozim odamning butun sozlamasini
 * hal qiladi, shuning uchun u dialogdagi YAGONA tanlov:
 *   tsex   -> beyjik bilan ishlaydi, posti oldindan belgilanadi (backend POST_ROLES)
 *   ofis   -> parol bilan kiradi, roli shu yerdan keladi
 *   boshqa -> tizimga kirmaydi (haydovchi, farrosh) — nomi qo'lda yoziladi
 *
 * Lavozim BEYJIKDA chop etiladi va mahsuldorlik hisobotida ustun bo'ladi:
 * erkin matn bo'lganda "Arrachi" va "arrachi" ikki qator berardi. */
export type PositionKind = "tsex" | "ofis" | "boshqa"

export const POSITIONS: {
  label: string
  kind: PositionKind
  post?: string
  role?: UserRole
}[] = [
  { label: "Arrachi", kind: "tsex", post: "ARRA" },
  { label: "Kromkachi", kind: "tsex", post: "KROMKA" },
  { label: "Oval kromkachi", kind: "tsex", post: "OVAL" },
  { label: "Prisadkachi", kind: "tsex", post: "PRISADKA" },
  { label: "Roverchi", kind: "tsex", post: "ROVER" },
  { label: "Stolyar", kind: "tsex", post: "STOLYARKA" },
  { label: "Bo'yoqchi", kind: "tsex", post: "BOYOQ" },
  { label: "Qadoqlovchi", kind: "tsex", post: "UPAKOVKA" },
  { label: "TMO omborchisi", kind: "tsex", post: "TMO" },
  { label: "Menejer", kind: "ofis", role: "manager" },
  { label: "Texnolog", kind: "ofis", role: "texnolog" },
  { label: "Direktor", kind: "ofis", role: "director" },
  { label: "Materiallar omborchisi", kind: "ofis", role: "material_omborchi" },
  { label: "Admin", kind: "ofis", role: "admin" },
]

export const OTHER_POSITION = "Boshqa"

// Operator rollar — o'z posti terminalini ko'radi (ish markazi/beyjik shart emas)
export const OPERATOR_ROLES = [
  "arrachi",
  "kromkachi",
  "ovalchi",
  "prisadkachi",
  "roverchi",
  "stolyar",
  "boyoqchi",
  "upakovkachi",
  "omborchi",
] as const

export const EMPLOYEE_STATUS_LABELS: Record<string, string> = {
  active: "AKTIV",
  inactive: "NOFAOL",
}

export const MACHINE_STATUS_LABELS: Record<string, string> = {
  active: "AKTIV",
  inactive: "NOAKTIV",
  repair: "TA'MIRDA",
}

// Kalitlar — backend `CapacityUnit` enum'i (generatsiya qilingan tip)
export const CAPACITY_UNIT_LABELS: Record<string, string> = {
  m2_per_hour: "m²/soat",
  meter_per_hour: "m/soat",
  units_per_hour: "dona/soat",
}

// Hamma joyda bir xil: kun.oy.yil (brauzer locale'iga bog'liq emas)
const p2 = (n: number) => String(n).padStart(2, "0")

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—"
  const d = new Date(value)
  return `${p2(d.getDate())}.${p2(d.getMonth() + 1)}.${d.getFullYear()}`
}

/** Arrachi nazarida "kesildi": ARRA skan bor YOKI chek chiqarilgan.
 * CutmapView va SheetSvg SHU predikatdan foydalanadi — ta'rif bitta joyda. */
export const isCut = (i: { done?: boolean; label_printed_at?: unknown }) =>
  Boolean(i.done || i.label_printed_at)

/**
 * Muddat ohangi: o'tgan = qizil, bugun = amber.
 * Kun aniqligida solishtiriladi — `deadline` backend'da `date` tipida keladi va
 * `new Date("2026-07-28")` UTC yarim tuni bo'lgani uchun xom solishtirish
 * Toshkentda soat 05:00 dan keyin bugungi buyurtmani "o'tgan" deb ko'rsatardi.
 */
export function deadlineTone(value?: string | null): "overdue" | "today" | "" {
  if (!value) return ""
  const d = new Date(value)
  const today = new Date()
  d.setHours(0, 0, 0, 0)
  today.setHours(0, 0, 0, 0)
  if (d < today) return "overdue"
  if (d.getTime() === today.getTime()) return "today"
  return ""
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  const d = new Date(value)
  return `${p2(d.getDate())}.${p2(d.getMonth() + 1)}.${d.getFullYear()} ${p2(d.getHours())}:${p2(d.getMinutes())}`
}

// Formatter bir marta quriladi — Intl.NumberFormat konstruktori qimmat, reestrda
// esa har qatorda ikki marta chaqiriladi.
const moneyFormat = new Intl.NumberFormat("uz-Latn-UZ")

export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—"
  return `${moneyFormat.format(Number(value))} so'm`
}

/** Qoldiq to'lov = umumiy narx − boshlang'ich to'lov. `amount` yo'qligini
 * ("—" ko'rsatishni) chaqiruvchi o'zi tekshiradi. */
export const remainingPayment = (o: {
  amount?: string | number | null
  advance_payment?: string | number | null
}) => Number(o.amount) - Number(o.advance_payment ?? 0)

export function formatSize(
  l?: number | null,
  w?: number | null,
  t?: number | null,
): string {
  if (!l && !w) return "—"
  const base = `${l ?? "?"} × ${w ?? "?"}`
  return t ? `${base} × ${t} mm` : `${base} mm`
}
