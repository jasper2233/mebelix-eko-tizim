/** Bazis modelining brauzerdagi ko'rinishi.
 *
 * Shakl backenddagi `services/bazis/viewer.py` bilan QO'LDA oynalangan —
 * kalitlar qisqa (`p`, `q`, `o`), chunki 268 panelli mahsulotda uzun nomlar
 * JSON'ni sezilarli kattalashtiradi, sahifa esa telefonda ochiladi.
 */

import { MAT_RANG } from "./matRang.gen"

export type BazisPanel = {
  /** Detal kodi (`01_005`) — MESdagi `Part.code` ning aynan o'zi. Bo'sh bo'lishi mumkin. */
  id: string
  /** Detal nomi (`Tom`, `Fasad`) */
  n: string
  /** `mats` massividagi material indeksi */
  m: number
  /** Qalinlik, mm */
  t: number
  /** Gabarit [eni, bo'yi], mm */
  s: [number, number]
  /** Mahsulot ichidagi joylashuvi */
  p: [number, number, number]
  /** Burilish kvaternioni */
  q: [number, number, number, number]
  /** Eshik/tortma OCHILGAN holatdagi joylashuv va burilish. Faqat
   * harakatlanadigan panelda bo'ladi (2285 dan 570 tasi) — qolganida yo'q. */
  po?: [number, number, number]
  qo?: [number, number, number, number]
  /** Kontur ko'pburchagi, panelning o'z tekisligida */
  o: [number, number][]
  /** Aylana kesmalar `[cx, cy, r]` — rozetka, rakovina */
  c?: [number, number, number][]
  /** Konturning O'ZI aylana (yumaloq javon): `o` — taqribiy ko'pburchak. */
  rd?: 1
}

/** Modelda umuman ochiladigan detal bormi — boshqaruvda «Ochiq» bo'lishi shundan. */
export const hasOpenState = (model: BazisModel): boolean =>
  model.panels.some((p) => p.po !== undefined)

export type BazisModel = {
  v: number
  code: string
  name: string
  mats: string[]
  panels: BazisPanel[]
}

/** Mahsulot kartochkasi — ochiq sahifaning bosh ro'yxati. */
export type PublicProduct = { code: string; name: string; panels: number }

/** Material rangi. Mebel ohangi — kamalak emas: bir xil materialdagi detallar
 * bir xil ko'rinadi, ya'ni yig'uvchi "bular bitta plitadan" ekanini rangdan
 * biladi. Ro'yxat tugasa boshidan aylanadi. */
/** Material NOMIDAN ko'rinish — KATALOGDA topilmagan nomlar uchun ZAXIRA yo'l.
 * Birinchi navbat `MAT_RANG` da (`matRang.gen.ts`, ishlatilishning 84% i).
 *
 * Kalit so'zlar 437 ta haqiqiy buyurtmadagi
 * 162 material nomidan olingan (85 753 ishlatilish), o'ylab topilmagan:
 * `kromka PVC 06-19 oq`, `LDSP DUB VATAN TEKSTURA`, `AKRIL KASHMIR GLYANETS`.
 *
 * Nega nom bo'yicha, indeks bo'yicha emas: ilgari rang `mats` massividagi
 * o'rindan olinardi, ya'ni AYNAN BIR XIL material bir mahsulotda bej,
 * boshqasida kulrang chiqardi — bitta buyurtmaning ikki mahsulotini
 * solishtirgan usta chalg'irdi.
 *
 * Nega katalogdan emas: Bazis katalogidagi `PARAM_1` teksturali materialda
 * ANDOZA — 90 yozuvdan 89 tasi bir xil `#F6B67F`; haqiqiy rang faqat
 * teksturasizlarida (64 yozuv, 37 xil rang). Ya'ni katalog bu qoidaning
 * o'rnini bosmaydi, faqat teksturasiz materiallarda uni aniqlashtiradi. */
/** Xona yuzasi — devor, pol, shift, kafel. MEBEL EMAS: bazischi mahsulot
 * qayerga qo'yilishini ko'rsatish uchun qo'shadi.
 *
 * 460 ta haqiqiy modelda o'lchandi: 107 tasida (23%) xona yuzasi bor va u
 * yuzaning 50-100% ini egallaydi — 100 mm qalin, berk qutini yasab, mebelni
 * butunlay yopib qo'yadi. Qoida 140 ta material nomidan ATIGI uchtasini
 * tutadi (`Devor` 171, `Pol` 59, `KAFEL 300x60 mm` 99), ya'ni yolg'on
 * ijobiysi yo'q. `pol` so'z sifatida: `polka` (javon) bunga tushmaydi. */
export const XONA_YUZASI =
  /devor|(^|[^a-z])pol([^a-z]|$)|стен|потол|wall|floor|kafel|кафел/i

const RANGLAR: [RegExp, string][] = [
  // Xona yuzalari BIRINCHI: ular mebel emas va zaxira rangda «yong'oq devor»
  // bo'lib chiqardi.
  [XONA_YUZASI, "#d3d6da"],
  [/oyna|shisha|stek|стек|зерк|экран|kozgu|ko'zgu/i, "#9fc2d6"],
  [/qora|чёрн|черн|black/i, "#2a2a2c"],
  [/metalik|metlik|серебр|silver|nikel|xrom|хром|chrome/i, "#b9bdc2"],
  [/mokriy|mokko|wenge|venge|tyomniy|темн/i, "#6d5647"],
  [/dub|votan|vatan|oak|орех|yong'oq/i, "#b98f5e"],
  [/sasna|asina|sosna|pine|olxa/i, "#cfa878"],
  [/kashmir|кашемир|krem|беж|bej|cream/i, "#d9c9ad"],
  [/zolota|tilla|gold|золот/i, "#c4a24a"],
  [/kaspiy|grafit|seriy|серый|grey|gray/i, "#9aa0a6"],
  [/oq|beli|бел|white/i, "#f2f1ee"],
]

/** Kalitga tushmagan nom uchun BETARAF ohang — ataylab yog'och ham, bej ham
 * emas. Ilgari zaxira palitrasida bej bor edi va `zamena material` (jami
 * ishlatilishning 3.9% i) kashmir bilan deyarli bir xil chiqib, tumbaning
 * ikki eshigi qolganidan ajralmay qolgan edi. Noma'lum material noma'lum
 * bo'lib ko'rinishi kerak, oilaga taqlid qilmasligi kerak. */
const ZAXIRA = [
  "#cfd2d6",
  "#c2c5c9",
  "#d5d2cd",
  "#b8bcc1",
  "#c9c5c0",
  "#dbd8d4",
]

const hash = (s: string): number => {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

/** Bir xil KALITGA tushgan ikki materialni ajratib turish uchun nozik
 * tafovut: yorqinlik ±7%, ohang ±8°. Nomdan olingani uchun barqaror.
 *
 * Kerak, chunki `LDSP KASHMIR SHAGREN` va `zamena material` bitta oilaga
 * tushib, tumbaning ikki eshigi qolganidan farq qilmay qolgan edi — usta
 * ularning BOSHQA material ekanini ko'rmasdi. Tafovut kichik: oila saqlanadi
 * («dub» baribir yog'och bo'lib ko'rinadi), lekin panellar ajraladi. */
const tafovut = (hex: string, nom: string): string => {
  const n = Number.parseInt(hex.slice(1), 16)
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255]
  const h = hash(nom)
  // -1..+1 oralig'ida ikki mustaqil kichik siljish
  const yorug = (((h % 101) / 50 - 1) * 7) / 100
  const ohang = ((((h / 101) | 0) % 101) / 50 - 1) * 8
  const o = [r, g, b].map((c) => c / 255)
  const mx = Math.max(...o)
  const mn = Math.min(...o)
  let H = 0
  const L = Math.min(1, Math.max(0, (mx + mn) / 2 + yorug))
  const S = mx === mn ? 0 : (mx - mn) / (1 - Math.abs(mx + mn - 1))
  if (mx !== mn) {
    const d = mx - mn
    H =
      mx === o[0]
        ? ((o[1] - o[2]) / d + (o[1] < o[2] ? 6 : 0)) * 60
        : mx === o[1]
          ? ((o[2] - o[0]) / d + 2) * 60
          : ((o[0] - o[1]) / d + 4) * 60
  }
  H = (H + ohang + 360) % 360
  const c = (1 - Math.abs(2 * L - 1)) * S
  const x = c * (1 - Math.abs(((H / 60) % 2) - 1))
  const m = L - c / 2
  const t: number[][] = [
    [c, x, 0],
    [x, c, 0],
    [0, c, x],
    [0, x, c],
    [x, 0, c],
    [c, 0, x],
  ]
  const [R, G, B] = t[Math.floor(H / 60) % 6].map((v) =>
    Math.round((v + m) * 255),
  )
  return `#${((R << 16) | (G << 8) | B).toString(16).padStart(6, "0")}`
}

/** Material nomini katalog kaliti holiga keltiradi.
 *
 * `scripts/bazis-material-colors.py: norm()` bilan QO'LDA oynalangan —
 * birini o'zgartirsang ikkinchisini ham, aks holda jadval kaliti mos
 * kelmay qoladi va rang jimgina regexga tushib ketadi.
 *
 * Texnolog Bazisda plita kvadraturasini va yetkazuvchini nomga qo'shadi
 * (`LDSP DUB VOTAN 5.03 kv.  Khatdekor`), katalogda esa `LDSP DUB VATAN`
 * turadi — shu shovqin olib tashlanadi. */
const normMat = (nom: string): string =>
  nom
    .toLowerCase()
    .trim()
    .replace(/\d+[.,]\d+\s*kv\.?/g, " ")
    .replace(/\d{3,4}\s*[xх*]\s*\d{3,4}(\s*[xх*]\s*\d+)?(\s*mm)?/g, " ")
    .replace(/\(\s*\d+\s*mm\s*\)/g, " ")
    .replace(/\b\d+\s*mm\b/g, " ")
    .replace(/khatde[ck]or|kronospan|xitoy|mestniy|местный/g, " ")
    .replace(/\bagt\b|\bbir tomon\b/g, " ")
    .replace(/votan/g, "vatan")
    .replace(/mokrik/g, "mokriy")
    .replace(/beliy?/g, "beli")
    .replace(/tiilla/g, "tilla")
    .replace(/glyans/g, "glyanets")
    .replace(/mativiy/g, "matviy")
    .replace(/[^a-z0-9а-яё ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()

/** Panel rangi. Katalogdagi HAQIQIY rangga TEGILMAYDI — u tekstura rasmining
 * o'rtachasi yoki katalogda yozilgan rang, ya'ni taxmin emas. Tafovut faqat
 * regex zaxirasiga qo'llanadi: u yerda rang baribir taxminiy va bir kalitga
 * tushgan ikki materialni ajratib turish kerak. Bir xil rang chiqqan ikki
 * dekor rostdan bir xil ko'rinadi — yaltiroqligi `materialRoughness` da. */
export const materialColor = (nom: string): string => {
  const katalog = MAT_RANG[normMat(nom)]
  if (katalog) return katalog
  for (const [naqsh, rang] of RANGLAR)
    if (naqsh.test(nom)) return tafovut(rang, nom)
  return tafovut(ZAXIRA[hash(nom) % ZAXIRA.length], nom)
}

/** Yaltiroqlik ham nomdan: `GLYANETS` yaltiroq, `MATVIY`/`SHAGREN` mat.
 * 437 buyurtmada `glyanets` 10.7%, `matviy` 7.8%, `shagren` 5.1% ishlatilgan. */
export const materialRoughness = (nom: string): number => {
  if (/oyna|shisha|stek|стек|зерк/i.test(nom)) return 0.12
  if (/glyanets|glyans|глянц|gloss/i.test(nom)) return 0.28
  if (/matviy|мат|shagren|шагрен/i.test(nom)) return 0.85
  return 0.7
}

/** `01_005` -> `1_5`: boshidagi nollar terilmasa ham topilsin. */
const normalize = (raw: string): string =>
  raw
    .trim()
    .toLowerCase()
    .replace(/\d+/g, (d) => String(Number(d)))

/** Detalni kod yoki nom bo'yicha topish — yig'uvchi qo'lidagi chekdan o'qiydi.
 *
 * XOM ko'rinish ham tekshiriladi: faqat normallashtirilgani bilan `01_0` kabi
 * TUGALLANMAGAN kod hech narsa topmasdi (`01_0` -> `1_0`, kod esa `1_5`), ya'ni
 * har terilgan harfda ro'yxat bo'sh chiqardi. */
export const matchPanel = (panel: BazisPanel, query: string): boolean => {
  const q = query.trim().toLowerCase()
  if (!q) return false
  const id = panel.id.toLowerCase()
  return (
    id.includes(q) ||
    normalize(id).includes(normalize(q)) ||
    panel.n.toLowerCase().includes(q)
  )
}

/** Oyna, shisha va ekran — ular ORQASI ko'rinishi kerak, aks holda model
 * ichidagi javonlar yo'qoladi. Nomlar prodda uchraganidek: rus va o'zbek. */
const SHAFFOF = /oyna|shisha|stek|стек|зерк|экран/i

export const isGlass = (materialName: string): boolean =>
  SHAFFOF.test(materialName)
