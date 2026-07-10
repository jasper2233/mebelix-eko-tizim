// MES domain constants: Uzbek labels + stage colors (TZ 3, 4.4, 6.1)

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

export const POST_COLORS: Record<string, string> = {
  ARRA: "var(--post-arra)",
  KROMKA: "var(--post-kromka)",
  PRISADKA: "var(--post-prisadka)",
  PAZ: "var(--post-paz)",
  ROVER: "var(--post-rover)",
  STOLYARKA: "var(--post-stolyarka)",
}

export const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  director: "Direktor",
  manager: "Manager",
  texnolog: "Texnolog",
  terminal: "Terminal",
  tablo: "TABLO",
}

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

export const CLIENT_TYPE_LABELS: Record<string, string> = {
  individual: "Jismoniy",
  legal: "Yuridik",
}

const dateFmt = new Intl.DateTimeFormat("uz-Latn-UZ", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
})
const dateTimeFmt = new Intl.DateTimeFormat("uz-Latn-UZ", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
})

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—"
  return dateFmt.format(new Date(value))
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  return dateTimeFmt.format(new Date(value))
}

export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—"
  return `${new Intl.NumberFormat("uz-Latn-UZ").format(Number(value))} so'm`
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
