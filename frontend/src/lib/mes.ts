// MES domain constants: Uzbek labels + stage colors (4.4, 6.1)

import type {
  EmployeeStatus,
  MachineStatus,
  OrderPriority,
  OrderStatus,
  PostCode,
  UserRole,
} from "@/client"

/** Beyjik QR'i = xodim UUID'i. Backend bilan umumiy shartnoma — bitta nusxa:
 *  uni ikkala skan tinglagichi (`useBadgeScan`, `useTerminalScan`) shu yerdan oladi. */
export const BADGE_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Yorliq/rang xaritalari `satisfies` bilan backend enum'iga bog'langan: yangi/noto'g'ri kalit build'ni
 *  yiqitadi. Tashqi tip `Record<string, ...>` — chaqiruvchilar kalitni API'dan xom `string` oladi. */
export const ORDER_STATUS_LABELS: Record<string, string> = {
  draft: "QORALAMA",
  technical_review: "TEXNOLOGDA",
  production: "JARAYONDA",
  completed: "TAYYOR",
  delivered: "TOPSHIRILDI",
  cancelled: "BEKOR QILINGAN",
} satisfies Record<OrderStatus, string>

export const ORDER_STATUS_COLORS: Record<string, string> = {
  draft: "var(--status-draft)",
  technical_review: "var(--status-review)",
  production: "var(--status-production)",
  completed: "var(--status-completed)",
  delivered: "var(--status-delivered)",
  cancelled: "var(--status-cancelled)",
} satisfies Record<OrderStatus, string>

// Terminal (yakuniy) holatlar: yakunlangan ish sanoqqa kirmaydi
export const TERMINAL_STATUSES: readonly OrderStatus[] = [
  "delivered",
  "cancelled",
]

export const PRIORITY_LABELS: Record<string, string> = {
  low: "Past",
  medium: "O'rta",
  high: "Yuqori",
  urgent: "Shoshilinch",
} satisfies Record<OrderPriority, string>

// Prioritet ranglari bitta manbadan: select nuqtalari va reestr matni
export const PRIORITY_DOT_CLASSES: Record<string, string> = {
  low: "bg-slate-300",
  medium: "bg-slate-400",
  high: "bg-orange-500",
  urgent: "bg-red-500",
} satisfies Record<OrderPriority, string>

export const PRIORITY_TEXT_CLASSES: Record<string, string> = {
  low: "text-muted-foreground",
  medium: "text-muted-foreground",
  high: "font-semibold text-orange-700",
  urgent: "font-bold text-red-600",
} satisfies Record<OrderPriority, string>

/** Prioritet TASMASI: TABLO qatorining chap qirrasi.
 *
 * `PRIORITY_DOT_CLASSES` bilan bir xil ranglar — buyurtma formasi va reestr
 * qanday ko'rsatsa, taxta ham shunday: bitta prioritet ikki ekranda ikki xil
 * rangda bo'lmaydi. (Avval faqat `urgent` belgilangan edi — tsex to'rttala
 * rangni so'radi.)
 */
export const PRIORITY_EDGE: Record<string, string> = {
  low: "border-l-slate-300",
  medium: "border-l-slate-400",
  high: "border-l-orange-500",
  urgent: "border-l-red-500",
} satisfies Record<OrderPriority, string>

export const PRIORITY_BADGE_CLASSES: Record<string, string> = {
  low: "bg-muted text-muted-foreground",
  medium: "bg-muted text-muted-foreground",
  high: "bg-orange-600 text-white",
  urgent: "bg-red-600 text-white",
} satisfies Record<OrderPriority, string>

/** Reestrni prioritet bo'yicha saralash tartibi. Yorliq/rang xaritalari bilan
 * yonma-yon: yangi prioritet ularning hech birida unutilmasin. */
export const PRIORITY_RANK: Record<string, number> = {
  low: 0,
  medium: 1,
  high: 2,
  urgent: 3,
} satisfies Record<OrderPriority, number>

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
} satisfies Record<PostCode, string>

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

/** Texnolog chizgan marshrut — jarayon NOMLARI tartib bilan (dum va o'chirilgan
 * qadamlar tashlanadi). Matritsa ustuni ham, Nostandart tabidagi zanjir ham shundan. */
export function routeStepNames(
  routes: { process_code: number; seq: number; is_enabled: boolean }[],
): string[] {
  return [...routes]
    .filter((r) => r.is_enabled && !TAIL_CODES.includes(r.process_code))
    .sort((a, b) => a.seq - b.seq)
    .map((r) => PROCESS_OPS[r.process_code]?.name ?? String(r.process_code))
}

/** Marshrut DUMI — backend o'zi qo'shadigan qadamlar (backend `TAIL_CODES` bilan qo'lda oynalangan).
 *  Saqlangan marshrutni o'qiganda filtrlanadi, aks holda tahrir dumni o'rtada qoldirardi. */
export const TAIL_CODES = [15, 16]

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
/** Yozish huquqi (mijoz, buyurtma, anketa): backend `ManagerUser` ning oynasi */
export const isManager = (u?: RoleUser | null) =>
  isAdmin(u) || u?.role === "manager"
/** Boshqaruv sahifalari (mijozlar, hodimlar, hisobotlar): admin + manager + direktor */
export const isManagement = (u?: RoleUser | null) =>
  isManager(u) || u?.role === "director"
/** Ishlab chiqarish sahifalari (buyurtmalar, ish markazlari): boshqaruv + texnolog */
export const isProductionStaff = (u?: RoleUser | null) =>
  isManagement(u) || u?.role === "texnolog"

// Ish markazi bog'lami MAJBURIY rollar — qurilma akkauntlari (Admin dialoglarida
// rol tanlovi, machine_id validatsiyasi va bog'lamni uzish shu ro'yxatdan)
export const MACHINE_BOUND_ROLES: readonly UserRole[] = ["terminal", "tablo"]

/** Lavozimlar — tizim biladigan ro'yxat. Lavozim odamning butun sozlamasini
 * hal qiladi, shuning uchun u dialogdagi YAGONA tanlov:
 *   tsex   -> beyjik bilan ishlaydi, posti oldindan belgilanadi (backend POST_ROLES)
 *   ofis   -> parol bilan kiradi, roli shu yerdan keladi
 *   boshqa -> tizimga kirmaydi (haydovchi, farrosh) — nomi qo'lda yoziladi
 *
 * Lavozim BEYJIKDA chop etiladi va mahsuldorlik hisobotida ustun bo'ladi:
 * erkin matn bo'lganda "Arrachi" va "arrachi" ikki qator berardi. */
type PositionKind = "tsex" | "ofis" | "boshqa"

// Tsex lavozimida ham `role` bor: skaneri yo'q postda (ARRA) xodimga SHAXSIY
// hisob ochiladi va u parol bilan kiradi. Rol backend `POST_ROLES` bilan bir xil
// jadval — hisob roli o'sha post terminalini ochadi.
// Yorliq ROLE_LABELS dan olinadi — rol nomi BITTA jadvalda yozilsin (ilgari
// ikkalasi qo'lda takrorlanardi va beyjik bilan hisobot ayri ketishi mumkin edi).
const position = (role: UserRole, kind: PositionKind, post?: string) => ({
  label: ROLE_LABELS[role],
  kind,
  post,
  role,
})

export const POSITIONS: {
  label: string
  kind: PositionKind
  post?: string
  role?: UserRole
}[] = [
  position("arrachi", "tsex", "ARRA"),
  position("kromkachi", "tsex", "KROMKA"),
  position("ovalchi", "tsex", "OVAL"),
  position("prisadkachi", "tsex", "PRISADKA"),
  position("roverchi", "tsex", "ROVER"),
  position("stolyar", "tsex", "STOLYARKA"),
  position("boyoqchi", "tsex", "BOYOQ"),
  position("upakovkachi", "tsex", "UPAKOVKA"),
  position("omborchi", "tsex", "TMO"),
  position("manager", "ofis"),
  position("texnolog", "ofis"),
  position("director", "ofis"),
  position("admin", "ofis"),
]

export const OTHER_POSITION = "Boshqa"

// Operator rollar — o'z posti terminalini ko'radi (ish markazi/beyjik shart emas)
export const OPERATOR_ROLES: readonly UserRole[] = [
  "arrachi",
  "kromkachi",
  "ovalchi",
  "prisadkachi",
  "roverchi",
  "stolyar",
  "boyoqchi",
  "upakovkachi",
  "omborchi",
]

export const EMPLOYEE_STATUS_LABELS: Record<string, string> = {
  active: "AKTIV",
  inactive: "NOFAOL",
} satisfies Record<EmployeeStatus, string>

export const MACHINE_STATUS_LABELS: Record<string, string> = {
  active: "AKTIV",
  inactive: "NOAKTIV",
  repair: "TA'MIRDA",
} satisfies Record<MachineStatus, string>

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
  return `${formatDate(value)} ${p2(d.getHours())}:${p2(d.getMinutes())}`
}

/** Raqamlar satrini minglik guruhlarga ajratadi: "5000000" → "5 000 000".
 * PULNING YAGONA FORMAT QOIDASI — ko'rsatish (`formatMoney`) ham, kiritish
 * maydoni (`lib/validation` `formatMoneyInput`) ham shu funksiyani ishlatadi.
 * Ilgari ikki xil edi: ekranda `Intl uz-Latn` vergul bilan ("5,000,000"),
 * maydonda bo'shliq — ekrandan nusxalab maydonga qo'yilganda vergul minglik
 * ekanini taxmin qilishga to'g'ri kelardi. Endi vergul pulda hech qayerda
 * minglik emas, ya'ni maydonda u faqat KASR bo'la oladi. */
export function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, " ")
}

/** So'm butun son (tiyin yo'q): API'dan kelgan "14000000.00" ham, hisoblangan
 * qoldiq ham butunga yaxlitlanadi. */
export function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—"
  const n = Math.round(Number(value))
  if (!Number.isFinite(n)) return "—"
  return `${n < 0 ? "−" : ""}${groupThousands(String(Math.abs(n)))} so'm`
}

/** Qoldiq to'lov = umumiy narx − boshlang'ich to'lov. `amount` yo'qligini
 * ("—" ko'rsatishni) chaqiruvchi o'zi tekshiradi. */
export const remainingPayment = (o: {
  amount?: string | number | null
  advance_payment?: string | number | null
}) => Number(o.amount) - Number(o.advance_payment ?? 0)

/** Audit log amallari — foydalanuvchiga ko'rinadigan nom (Loglar sahifasi va
 * buyurtma kartasidagi «Oxirgi amal»). Backend `log_action(action=...)` bilan qo'lda oynalangan. */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  recorded: "yozildi",
  rejected: "rad etildi",
  cancelled: "bekor qilindi",
  label_sent: "chek yuborildi",
  label_cancelled: "chek bekor qilindi",
  waste_label_sent: "qoldiq cheki yuborildi",
  waste_label_cancelled: "qoldiq cheki bekor qilindi",
  created: "yaratildi",
  updated: "o'zgartirildi",
  deleted: "o'chirildi",
  started: "boshlandi",
  ended: "tugadi",
  machine_linked: "ish markazi bog'landi",
  machine_unlinked: "ish markazidan uzildi",
  login: "tizimga kirdi",
  login_failed: "kirish rad etildi",
  logout: "tizimdan chiqdi",
  can_print_changed: "chek chiqarish o'zgardi",
  scx_regenerated: "SCX qayta yaratildi",
  matrix_edited: "matritsa tahrirlandi",
  code_regenerated: "yangi ulanish kodi",
  paired: "ulandi",
  badge_regenerated: "beyjik qayta yaratildi",
  survey_saved: "anketa saqlandi",
  survey_photo_added: "anketa rasmi qo'shildi",
  survey_photo_deleted: "anketa rasmi o'chirildi",
  delivered: "topshirildi",
  confirmed: "tasdiqlandi",
  production_started: "ishlab chiqarishga uzatildi",
  machines_assigned: "ish markazlari biriktirildi",
  project_uploaded: "fayl yuklandi",
  accepted: "TMO ga qabul qilindi",
  shipped: "yuklab jo'natildi",
  closed: "yopildi",
  item_removed: "pachkadan olindi",
  badge_queued: "beyjik chop etishga yuborildi",
}

/** Skan xato kodlari — backend `services/scanning.py` `ScanRejected` docstring'i
 * bilan QO'LDA oynalangan (kod barqaror, matn tahrirlanadi). Loglar panelida
 * «E008» yolg'iz turmasin: kim harakat qilishi shu yerdan o'qiladi. */
export const SCAN_ERROR_LABELS: Record<string, string> = {
  E001: "Detal/plan mos kelmadi — operator chekni tekshiradi",
  E002: "QR formati buzuq — chek qayta chop etiladi",
  E003: "Buyurtma bekor qilingan — menejerga",
  E004: "Navbat buzildi — oldingi bosqich kutiladi",
  E005: "Aktiv smena yo'q — beyjik bilan kirish kerak",
  E006: "Beyjik/hodim muammosi — admin",
  E007: "Aloqa uzildi (terminalning o'zi beradi, server kodi emas)",
  E008: "Ish allaqachon bajarilgan — xato emas, ogohlantirish",
  E009: "Sozlama xatosi (post/ish markazi yo'q) — admin tuzatadi",
}

/** Fayl hajmi: 1 KB gacha bayt, 1 MB gacha KB, undan yuqori MB (1 kasr). */
export function formatBytes(size: number | null | undefined): string {
  if (size == null) return "—"
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

/** Backend `FileKind` (models/enums.py) — foydalanuvchiga ko'rinadigan nom. */
export const FILE_KIND_LABELS: Record<string, string> = {
  project: "Project fayl",
  scx: "SCX dasturi",
  label_pdf: "Yorliq PDF",
  document: "Hujjat",
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
