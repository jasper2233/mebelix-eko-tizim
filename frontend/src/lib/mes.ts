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
  arrachi: "Arrachi",
  kromkachi: "Kromkachi",
  prisadkachi: "Prisadkachi",
  pazchi: "Pazchi",
  roverchi: "Roverchi",
  stolyar: "Stolyar",
}

// Operator rollar — o'z posti terminalini ko'radi (stanok/beyjik shart emas)
export const OPERATOR_ROLES = [
  "arrachi",
  "kromkachi",
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

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  const d = new Date(value)
  return `${p2(d.getDate())}.${p2(d.getMonth() + 1)}.${d.getFullYear()} ${p2(d.getHours())}:${p2(d.getMinutes())}`
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
