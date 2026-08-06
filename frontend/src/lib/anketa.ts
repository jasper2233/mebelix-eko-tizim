// Buyurtma anketasi (mijoz so'rovnomasi + o'lchov varag'i) uchun variantlar katalogi.
// Qog'oz anketa: uploads/forma/mebel_buyurtma_anketa.html
// Kodlar bazaga JSON'da yoziladi, matnlar faqat shu yerda — o'zgarsa tarix buzilmaydi.

export type Option = { value: string; label: string }

/** 2-bo'lim: qanday mebel kerak (bir nechta tanlanadi) */
export const FURNITURE_TYPES: Option[] = [
  { value: "oshxona", label: "Oshxona garnituri" },
  { value: "shkaf_kupe", label: "Shkaf-kupe" },
  { value: "yotoq", label: "Yotoq (karovat)" },
  { value: "divan", label: "Divan / yumshoq" },
  { value: "bolalar", label: "Bolalar mebeli" },
  { value: "ofis", label: "Ofis mebeli" },
  { value: "prixojaya", label: "Prixojaya" },
  { value: "tv_tumba", label: "TV tumba" },
  { value: "komod", label: "Komod" },
  { value: "vannaxona", label: "Vannaxona mebeli" },
]

/** 3-bo'lim: xonadagi shakl / joylashuv */
export const LAYOUT_SHAPES: Option[] = [
  { value: "togri", label: "To'g'ri (I)" },
  { value: "burchak", label: "Burchak (L)" },
  { value: "p_shakl", label: "П-shakl (U)" },
  { value: "orolchali", label: "Orolchali" },
]

/** 4-bo'lim: korpus materiali */
export const CORPUS_MATERIALS: Option[] = [
  { value: "ldsp", label: "LDSP (laminat)" },
  { value: "mdf", label: "MDF" },
  { value: "massiv", label: "Massiv yog'och" },
  { value: "plastik", label: "Plastik" },
  { value: "fanera", label: "Fanera" },
]

export const CORPUS_THICKNESS: Option[] = [
  { value: "16", label: "16 mm" },
  { value: "18", label: "18 mm" },
  { value: "boshqa", label: "Boshqa" },
]

/** 5-bo'lim: fasad materiali */
export const FACADE_MATERIALS: Option[] = [
  { value: "ldsp", label: "LDSP" },
  { value: "mdf_mat", label: "MDF matoviy" },
  { value: "mdf_glyanets", label: "MDF glyanets" },
  { value: "akril", label: "Akril" },
  { value: "shpon", label: "Shpon" },
  { value: "ramkali", label: "Ramkali (profil)" },
  { value: "shisha", label: "Shisha (steklo)" },
]

/** 5-bo'lim: stol usti (asosan oshxona) */
export const COUNTERTOPS: Option[] = [
  { value: "postforming", label: "Postforming (LDSP)" },
  { value: "sunly_tosh", label: "Sun'iy tosh (kvarts)" },
  { value: "massiv", label: "Massiv" },
  { value: "yoq", label: "Kerak emas" },
]

/** 6-bo'lim: furnitura darajasi */
export const HARDWARE_LEVELS: Option[] = [
  { value: "oddiy", label: "Oddiy" },
  { value: "medium", label: "Medium" },
  { value: "premium", label: "Premium" },
]

/** 6-bo'lim: xona jihozlari — har xonada alohida bo'lishi mumkin.
 *  Yetkazib berish va montaj bu ro'yxatda EMAS: ular butun buyurtmaga tegishli
 *  (bitta mashina, bitta brigada), shuning uchun OrderSurvey darajasida. */
export const EXTRA_SERVICES: Option[] = [
  { value: "led", label: "LED yoritish" },
  { value: "rozetka", label: "Rozetka bloki" },
  { value: "organayzer", label: "Ichki tortmalar (organayzer)" },
  { value: "oyna", label: "Oyna / ko'zgu" },
]

/** O'lchov varag'i: devor harflari (A dan soat yo'nalishi bo'yicha) */
export const WALL_LETTERS = ["A", "B", "C", "D", "E"] as const

/** Kod -> matn: saqlangan qiymatni ko'rsatish uchun */
export function labelOf(options: Option[], value: string): string {
  return options.find((o) => o.value === value)?.label ?? value
}

/** Kodlar ro'yxatini o'qiladigan matnga: ["led","oyna"] -> "LED yoritish, Oyna / ko'zgu" */
export function labelsOf(
  options: Option[],
  values: string[] | undefined,
): string {
  return (values ?? []).map((v) => labelOf(options, v)).join(", ")
}
