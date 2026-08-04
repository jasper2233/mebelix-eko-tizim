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
  high: "font-semibold text-orange-600",
  urgent: "font-bold text-red-600",
}

export const PRIORITY_BADGE_CLASSES: Record<string, string> = {
  low: "bg-muted text-muted-foreground",
  medium: "bg-muted text-muted-foreground",
  high: "bg-orange-500 text-white",
  urgent: "bg-red-500 text-white",
}

export const POST_COLORS: Record<string, string> = {
  ARRA: "var(--post-arra)",
  KROMKA: "var(--post-kromka)",
  OVAL: "var(--post-oval)",
  PRISADKA: "var(--post-prisadka)",
  PAZ: "var(--post-paz)",
  ROVER: "var(--post-rover)",
  STOLYARKA: "var(--post-stolyarka)",
}

// Rollar manbasi — backend enum'i (generatsiya qilingan UserRole); yorliq
// yozilmagan yangi rol build'ni yiqitadi
export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  director: "Direktor",
  manager: "Manager",
  texnolog: "Texnolog",
  terminal: "Terminal",
  tablo: "TABLO",
  arrachi: "Arrachi",
  kromkachi: "Kromkachi",
  ovalchi: "Oval kromkachi",
  prisadkachi: "Prisadkachi",
  pazchi: "Pazchi",
  roverchi: "Roverchi",
  stolyar: "Stolyar",
}

// Sahifa huquqi BITTA joyda: sidebar menyusi ham, route guard ham shu uchtasini
// ishlatadi. Ilgari ikkalasi alohida yozilgani uchun "menyuda ko'rinadi, ochsang
// bosh sahifaga uloqtiradi" holati chiqib qolgandi.
// Rol nomi UserRole (backend enum'i) dan: rol qayta nomlansa solishtirish
// jimgina "false" bo'lib qolmasin — ROLE_LABELS kabi build yiqilsin
type RoleUser = { role?: UserRole | null; is_superuser?: boolean | null }
/** Foydalanuvchilarni boshqarish — telefon raqamlar ochiladi (backend SuperUserDep) */
export const isSuperuser = (u?: RoleUser | null) => Boolean(u?.is_superuser)
/** Tizim sozlamalari: printer agentlar, loglar (backend AdminUser) */
export const isAdmin = (u?: RoleUser | null) =>
  Boolean(u?.is_superuser || u?.role === "admin")
/** Audit izi — rahbariyat ko'radi (backend DirectorUser) */
export const isAdminOrDirector = (u?: RoleUser | null) =>
  isAdmin(u) || u?.role === "director"

// Operator rollar — o'z posti terminalini ko'radi (stanok/beyjik shart emas)
export const OPERATOR_ROLES = [
  "arrachi",
  "kromkachi",
  "ovalchi",
  "prisadkachi",
  "pazchi",
  "roverchi",
  "stolyar",
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

export const MATERIAL_TYPE_LABELS: Record<string, string> = {
  sheet: "List",
  band: "Kromka lenta",
  hardware: "Furnitura",
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

export function formatSize(
  l?: number | null,
  w?: number | null,
  t?: number | null,
): string {
  if (!l && !w) return "—"
  const base = `${l ?? "?"} × ${w ?? "?"}`
  return t ? `${base} × ${t} mm` : `${base} mm`
}
