// GibSaw uslubidagi to'liq list SVG renderi (GibLabViewer'dan portlangan,
// foto-tekshirilgan): detallar, kesim chiziqlari, teshiklar, dims zanjiri,
// zoom/pan/swipe. CutmapView va print oqimi shu komponentni ishlatadi.

import { useEffect, useRef, useState } from "react"

import type {
  CutmapCell,
  CutmapHole,
  CutmapInstanceState,
  CutmapSheet,
} from "@/client"
import { isCut } from "@/lib/mes"

// Xarita turlari SHU YERDA e'lon qilinadi va CutmapView ularni import qiladi:
// ikkalasi bir xil yoyilgan listni ko'radi, ta'rif ikki joyda turmasin.
export type SheetPart = CutmapCell
/** Yoyilgan list: `mult` li sxema alohida listlarga bo'linadi, o'shanda `no`
 *  "3c2" ko'rinishini oladi (matn) va `disp` ketma-ket raqam beradi. `rover` —
 *  listning egasi, kataklar marshrutidan hisoblanadi (serverda yo'q). */
export type Sheet = Omit<CutmapSheet, "no"> & {
  no: number | string
  disp?: number
  rover?: boolean
}

// Barcha detallar bir xil to'q apelsin; tanlangani moviy bo'lib ajraladi.
// Xarita paneli kulrang (oq emas) — yorug' tsexda ko'z qamashtirmaydi, detallar ajralib turadi
const PART_FILL = "#e88b00"
const PART_SELECTED = "#2596be"
// Chek chiqarilgan yoki skan qilingan katak — "kesildi" yashili (TZ 7.1.7).
// Tailwind green-500: kromka/prisadka nusxa chiplari (green-600) bilan bir
// oilada — xarita ajralib qolmasin. List kartasi endi yengil tint
// (green-50 fon, green-700 matn): to'ldirilgan katak SVG'da undan to'q
const PART_DONE = "#22c55e"
// Nostandart detal — marshrutini texnolog qo'lda chizgan. Kesilmagan holatda
// sariq o'rniga BINAFSHA turadi, chek chiqarilgach odatdagidek YASHIL bo'ladi,
// chek bekor qilinsa yana binafshaga qaytadi (`allDone` fondan ustun).
//
// Nega binafsha: qizil "bekor qilingan" (--status-cancelled), pushti esa ROVER
// postining rangi (--post-rover) — ikkalasi ham noto'g'ri ma'no berardi.
const PART_CUSTOM = "#a78bfa"

/** Uzoq bosishda ruxsat etilgan siljish, piksel.
 *
 * TURGA QARAB EMAS, ataylab bitta son. Ilgari `pointerType` bo'yicha
 * ajratilgandi (barmoqqa kengroq), lekin bu DRAYVER ROSTGO'YLIGIGA tayanadi:
 * tsexdagi panel barmoqni "mouse" deb xabar qilsa, tor sichqoncha chegarasi
 * qo'llanib uzoq bosish yiqilardi — sinov panelida esa ishlardi. Aynan shu
 * farq kuzatilgan.
 *
 * 30px = 17" 1920x1080 da ~6 mm. Sichqoncha qo'yib qo'yilganda NOL piksel
 * qimirlaydi, ya'ni keng chegara sichqonchaga hech qanday zarar qilmaydi. */
const LP_SLOP = 30

/** O'lcham yozuvi EKRANDA shu oraliqda bo'ladi (SVG birligi emas, piksel).
 *
 * Arrachi o'lchamga qarab kesadi — bu uning ASOSIY ma'lumoti, detal nomidan
 * muhimroq. Shuning uchun o'lcham eng oxirida yo'qoladi: joy tanqislashganda
 * ketma-ketlik `nom -> faqat raqam -> nom yo'q -> o'lcham`.
 */
const DIM_MIN = 12 // bundan past — umuman chizilmaydi
const DIM_MAX = 46 // katta detalda ham me'yorida

/** Bitta o'lcham yozuvining kattaligi va ko'rinishi.
 *
 * `bo'ylab` — yozuv joylashadigan qirra uzunligi, `ko'ndalang` — unga
 * perpendikular o'lcham. W va H uchun aynan bir xil hisob, faqat o'qlar
 * almashadi — shuning uchun bitta funksiya.
 *
 * `zoom` bo'yicha baholash: shrift ekranda doimiy qolsin va yaqinlashtirish
 * yozuvni kattaytirmasdan, sig'maganlarini OCHSIN.
 */
function dimFit(boylab: number, kondalang: number, matn: string, zoom: number) {
  const sig = Math.min(
    kondalang * 0.28,
    (boylab * 0.9) / Math.max(3, matn.length * 0.6),
  )
  return {
    fs: Math.min(sig, DIM_MAX / zoom),
    show: boylab > 16 && sig * zoom >= DIM_MIN,
  }
}

// --- GibSaw render qoidalari (GibLabViewer'dan portlangan, foto-tekshirilgan) ---

/** Teshik koordinatasi detal lokal (l×w) o'qidan katakka: rot = o'q almashinuvi, OYNASIZ. */
export function holeXY(
  p: SheetPart,
  H: CutmapHole,
  bx: number,
  by: number,
): [number, number] {
  // `l`/`w` — detalning tayyor o'lchami, fayl bermasa `null`. Nol bilan
  // bo'lish avvalgidek Infinity beradi (JS'da `null` ham 0 ga aylanardi),
  // ya'ni geometriyasiz detal teshigi ekrandan tashqarida qoladi.
  const hl = H.l ?? 0
  const hw = H.w ?? 0
  const cx = p.rot ? p.x + by * (p.w / hw) : p.x + bx * (p.w / hl)
  const cy = p.rot ? p.y + bx * (p.h / hl) : p.y + by * (p.h / hw)
  return [cx, cy]
}

/** Qirra teshigi lokal nuqtasi: side chetida, pos shu chet bo'ylab. */
export function edgeLocalXY(
  H: CutmapHole,
  side: string,
  pos: number,
): [number, number] {
  if (side === "t") return [pos, 0]
  if (side === "b") return [pos, H.w ?? 0]
  if (side === "l") return [0, pos]
  return [H.l ?? 0, pos]
}

/** Qirra teshigi: eng yaqin chetdan ichkariga to'rtburchak, uzunlik = burg'u chuqurligi. */
export function edgeBoreRect(
  p: SheetPart,
  cx: number,
  cy: number,
  d: number,
  dp: number,
) {
  const dl = cx - p.x
  const dr = p.x + p.w - cx
  const dt = cy - p.y
  const db = p.y + p.h - cy
  const m = Math.min(dl, dr, dt, db)
  const len = Math.max(dp || 12, 6)
  const dd = Math.max(d, 5)
  if (m === dl) return { x: p.x, y: cy - dd / 2, w: len, h: dd }
  if (m === dr) return { x: p.x + p.w - len, y: cy - dd / 2, w: len, h: dd }
  if (m === dt) return { x: cx - dd / 2, y: p.y, w: dd, h: len }
  return { x: cx - dd / 2, y: p.y + p.h - len, w: dd, h: len }
}

const PAD = 110 // dims zanjiri viewBox'dan siqilib qolmasin

export function SheetSvg({
  sheet,
  holes,
  instancesByCell,
  onSelect,
  onOpenPart,
  selectedCell,
  thumbnail = false,
  registerZoom,
  onSwipe,
}: {
  sheet: Sheet
  holes: Record<string, CutmapHole>
  instancesByCell: Map<string, CutmapInstanceState[]>
  onSelect: (part: SheetPart) => void
  /** Uzoq bosish (~600ms): chekni bekor qilish — noto'g'ri chiqarilgan yorliq */
  /** Detal kartochkasini ochadi. IKKI jest ham shuni chaqiradi: ikki marta
   *  bosish (GibSaw dagi odat) va uzoq bosish (o'rganib qolganlar uchun). */
  onOpenPart?: (part: SheetPart) => void
  selectedCell: number | null
  /** Mini preview (material kartasi): interaktivsiz, scroll bloklamaydi */
  thumbnail?: boolean
  /** Chap toolbar zoom tugmalari uchun API (GibLab uslubi) */
  registerZoom?: (api: {
    zin: () => void
    zout: () => void
    reset: () => void
  }) => void
  /** To'liq ko'rinishda gorizontal swipe (sensorli monoblok): list almashtirish */
  onSwipe?: (dir: "next" | "prev") => void
}) {
  const { L, W } = sheet
  const svgRef = useRef<SVGSVGElement>(null)
  const [vb, setVb] = useState<{
    x: number
    y: number
    w: number
    h: number
  } | null>(null)
  const panRef = useRef<{
    x: number
    y: number
    vx: number
    vy: number
  } | null>(null)
  const ptsRef = useRef(new Map<number, { x: number; y: number }>())
  const pinchRef = useRef<number | null>(null)
  const swipeRef = useRef<{ x: number; y: number; t: number } | null>(null)
  // Long press (chekni bekor qilish): taymer + boshlang'ich nuqta; barmoq
  // siljisa/ko'tarilsa bekor. Otilgach keyingi click yutiladi (tanlash ochilmasin)
  const lpRef = useRef<{
    t: number
    x: number
    y: number
    /** Bosishni BOSHLAGAN ko'rsatkich. Boshqa barmoq (yoki kaft) qimirlaganda
     *  uzoq bosish bekor bo'lmasin — 17" monoblokda kaft ekranga tegib turadi. */
    id: number
    /** Chidamlilik ko'rsatkich TURIGA bog'liq (pastda). */
    type: string
  } | null>(null)
  const lpFiredRef = useRef(false)
  /** Oxirgi bosish — IKKI MARTA BOSISH aniqlash uchun (pastdagi izohga qara) */
  const tapRef = useRef<{ cell: number; t: number } | null>(null)
  //: Hozir uzoq bosilayotgan katak — faqat KO'RSATISH uchun (jarayon bo'yog'i)
  const [holding, setHolding] = useState<number | null>(null)
  const cancelLP = () => {
    if (lpRef.current) clearTimeout(lpRef.current.t)
    lpRef.current = null
    setHolding(null)
  }

  // Assimetrik ramka: dims zanjiri faqat tepada/chapda — o'ng/past minimal (bo'sh joy qolmasin)
  const base = { x: -PAD, y: -PAD, w: L + PAD + 28, h: W + PAD + 28 }

  // biome-ignore lint/correctness/useExhaustiveDependencies: zoom har yangi listda tiklanadi
  useEffect(() => setVb(null), [sheet.no])

  const applyVb = (x: number, y: number, w: number, h: number) => {
    const cx = Math.max(base.x, Math.min(x, base.x + base.w - w))
    const cy = Math.max(base.y, Math.min(y, base.y + base.h - h))
    setVb(w >= base.w - 1 ? null : { x: cx, y: cy, w, h })
  }

  const svgPoint = (clientX: number, clientY: number) => {
    const ctm = svgRef.current?.getScreenCTM()
    if (!ctm) return null
    return new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse())
  }

  // f — zoom faktori (>1 uzoqlashtiradi), (ax, ay) SVG nuqtasi joyida qoladi.
  // base.w/14 — maksimal yaqinlik: g'ildirak/pinch/tugma uchun yagona chegara
  const zoomAt = (f: number, ax: number, ay: number) => {
    const cur = svgRef.current?.viewBox.baseVal
    if (!cur) return
    const nw = Math.min(base.w, Math.max(base.w / 14, cur.width * f))
    const nh = nw * (base.h / base.w)
    applyVb(
      ax - (ax - cur.x) * (nw / cur.width),
      ay - (ay - cur.y) * (nh / cur.height),
      nw,
      nh,
    )
  }

  // g'ildirak zoom kursor nuqtasiga (native listener — passive:false kerak)
  useEffect(() => {
    if (thumbnail) return
    const svg = svgRef.current
    if (!svg) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const pt = fnRef.current.svgPoint(e.clientX, e.clientY)
      if (!pt) return
      fnRef.current.zoomAt(e.deltaY < 0 ? 1 / 1.25 : 1.25, pt.x, pt.y)
    }
    svg.addEventListener("wheel", onWheel, { passive: false })
    return () => svg.removeEventListener("wheel", onWheel)
    // handler fnRef'dan o'qiydi — listener bir marta o'rnatiladi, har renderda emas
  }, [thumbnail])

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    // ATAYIN capture yo'q: setPointerCapture keyingi click'ni SVG'ga retarget
    // qilib, detal <g> onClick'ini o'ldiradi (tanlash ishlamay qoladi)
    ptsRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (ptsRef.current.size === 2) {
      cancelLP()
      panRef.current = null
      swipeRef.current = null
      const [a, c] = [...ptsRef.current.values()]
      pinchRef.current = Math.hypot(a.x - c.x, a.y - c.y)
    } else if (vb) {
      panRef.current = { x: e.clientX, y: e.clientY, vx: vb.x, vy: vb.y }
    } else {
      // To'liq ko'rinishda bir barmoq swipe = list almashtirish (zoomda pan ustun)
      swipeRef.current = { x: e.clientX, y: e.clientY, t: Date.now() }
    }
  }
  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (ptsRef.current.has(e.pointerId))
      ptsRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    // UZOQ BOSISH chidamliligi ko'rsatkich turiga qarab.
    //
    // Ilgari chegara hamma uchun 12px edi — sichqoncha uchun to'g'ri (u qo'yib
    // qo'yilsa NOL piksel qimirlaydi), barmoq uchun esa juda tor: 12px ~3mm, va
    // barmoq 600ms davomida shundan ko'proq suriladi. Natijada uzoq bosish
    // sensorli monoblokda deyarli hech qachon ishlamas, sichqoncha bilan esa
    // muammosiz ishlardi — aynan shu farq xabar qilingan edi.
    //
    // Faqat BOSHLAGAN ko'rsatkichning harakati hisobga olinadi: ikkinchi barmoq
    // yoki ekranga tekkan kaft avval har qanday harakatda bekor qilardi.
    const lp = lpRef.current
    if (lp && e.pointerId === lp.id) {
      if (Math.hypot(e.clientX - lp.x, e.clientY - lp.y) > LP_SLOP) cancelLP()
    }
    const svg = svgRef.current
    if (!svg) return
    if (ptsRef.current.size === 2 && pinchRef.current) {
      const [a, c] = [...ptsRef.current.values()]
      const d2 = Math.hypot(a.x - c.x, a.y - c.y)
      if (d2 < 20) return
      const f = pinchRef.current / d2 // AVVAL faktor, keyin yangi masofa
      pinchRef.current = d2
      const mid = svgPoint((a.x + c.x) / 2, (a.y + c.y) / 2)
      if (!mid) return
      zoomAt(f, mid.x, mid.y)
      return
    }
    const pan = panRef.current
    if (!pan) return
    const r = svg.getBoundingClientRect()
    const cur = svg.viewBox.baseVal
    const k = Math.max(cur.width / r.width, cur.height / r.height)
    applyVb(
      pan.vx - (e.clientX - pan.x) * k,
      pan.vy - (e.clientY - pan.y) * k,
      cur.width,
      cur.height,
    )
  }
  const onPointerEnd = (e: React.PointerEvent<SVGSVGElement>) => {
    cancelLP()
    const sw = swipeRef.current
    if (sw && ptsRef.current.size === 1) {
      const dx = e.clientX - sw.x
      const dy = e.clientY - sw.y
      if (Date.now() - sw.t < 600 && Math.abs(dx) > 80 && Math.abs(dy) < 60)
        onSwipe?.(dx < 0 ? "next" : "prev")
    }
    swipeRef.current = null
    ptsRef.current.delete(e.pointerId)
    if (ptsRef.current.size < 2) pinchRef.current = null
    if (!ptsRef.current.size) panRef.current = null
  }

  // Tugma zoom — qo'lqopda pinch ishonchsiz; markaz atrofida 1.5x
  const zoomBy = (f: number) => {
    const cur = svgRef.current?.viewBox.baseVal
    if (cur) zoomAt(f, cur.x + cur.width / 2, cur.y + cur.height / 2)
  }
  // Eng so'nggi funksiyalar ref'da: har renderda yangi identifikatsiya olsalar
  // ham, listener va registerZoom bir marta o'rnatiladi.
  const fnRef = useRef({ zoomAt, zoomBy, svgPoint })
  fnRef.current = { zoomAt, zoomBy, svgPoint }

  // Render paytida emas, effektda: render tanasida tashqi ref'ga yozish yon
  // ta'sir bo'lib, StrictMode va kelajakdagi concurrent render'da ikki marta
  // ishlaydi.
  useEffect(() => {
    registerZoom?.({
      zin: () => fnRef.current.zoomBy(1 / 1.5),
      zout: () => fnRef.current.zoomBy(1.5),
      reset: () => setVb(null),
    })
  }, [registerZoom])

  // Yorliqlar hamma narsadan KEYIN chiziladi (teshik/tekstura ortida qolmasin), halo bilan
  const labels: React.ReactNode[] = []

  // Yozuvlar EKRAN o'lchamida doimiy: SVG birligidagi shrift masshtabga BO'LINADI.
  //
  // Ilgari yozuv model birligida edi — yaqinlashtirilganda u ham kattayib
  // ketardi, uzoqlashtirilganda esa o'qib bo'lmasdi. 17" monoblokda to'liq list
  // ko'rinishida kichik detalning o'lchami ko'zga ilinmasdi.
  //
  // Endi CAD ko'ruvchilaridagi qoida: yozuv doim bir xil kattalikda, YAQINLASHISH
  // esa yangi yozuvlarni OCHADI — katak ekranda kattarayvergani sari unga sig'adi.
  // Bu "o'qilishi" bilan "hammasi ko'rinishi" orasidagi ziddiyatni hal qiladi:
  // ikkalasi bir vaqtda mumkin emas, chunki joy chegaralangan.
  const zoom = vb ? base.w / Math.max(1, vb.w) : 1

  const partNodes = sheet.parts.map((p) => {
    const insts = instancesByCell.get(`${sheet.no}:${p.cell}`) ?? []
    // "Kesildi" ta'rifi @/lib/mes'dagi isCut da — bitta manba
    const doneCount = insts.filter(isCut).length
    const allDone = !p.waste && insts.length > 0 && doneCount === insts.length
    const selected = selectedCell === p.cell
    // 128px balandlikdagi kartochka preview'ida teshiklar, tekstura chiziqlari,
    // o'lcham zanjiri va yozuvlar piksel ostida qoladi, lekin to'liq hisoblanib
    // SVG tugunlariga aylanardi: 12 listli materialda ~6000 ortiqcha tugun va
    // har detal uchun yozuv-to'qnashuv algoritmi. Thumbnail'da ular chizilmaydi.
    const H = thumbnail ? undefined : holes[String(p.id)]
    const custom = !p.waste && insts.length > 0 && insts.every((i) => i.custom)
    // `allDone` `custom` dan USTUN: chek chiqarilgan nostandart detal ham yashil
    // bo'ladi (arrachi uchun "kesildi" belgisi hamma detalda bir xil), bekor
    // qilinsa `allDone` yana false bo'lib o'z rangiga qaytadi.
    const fill = p.waste
      ? "url(#zebra)"
      : selected
        ? PART_SELECTED
        : allDone
          ? PART_DONE
          : custom
            ? PART_CUSTOM
            : PART_FILL

    // thumbnail'da yozuvlar umuman hisoblanmaydi — pickSpot to'qnashuv qidiruvi
    // har detal uchun bir necha nomzod joyni tekshiradi, natijasi esa 128px da
    // ko'rinmaydi.
    // ATXOT o'lchami. GibLab ro'yxatga olgan atxot (blob turi 4) foydali
    // o'lchami bilan keladi — xom kesim emas (`cutmap.py`, TZ 5.2.3). Arra haqqi
    // (tur 1, ~0.5 mm chekka kesim) esa umuman katak bo'lmaydi, ya'ni bu yerga
    // tushmaydi. O'lcham ko'rsatilmasa arrachi atxotni ko'z bilan chamalab,
    // keyingi buyurtmaga yaraydimi-yo'qmi deb bilolmasdi.
    if (p.waste && !thumbnail) {
      const wv = p.w
      const hv = p.h
      const fs = Math.max(
        10,
        Math.min(34, wv * 0.16, hv * 0.42, (wv * 0.8) / 6),
      )
      // Juda kichik atxotda yozuv o'qilmaydi — chizmaymiz
      if (wv > 70 && hv > 26)
        labels.push(
          <text
            key={`wz${p.cell}`}
            x={p.x + wv / 2}
            y={p.y + hv / 2}
            fontSize={fs}
            fill="#5a6b82"
            fontWeight="700"
            textAnchor="middle"
            dominantBaseline="central"
            pointerEvents="none"
          >
            {`${Math.round(wv)}×${Math.round(hv)}`}
          </text>,
        )
    }

    if (!p.waste && !thumbnail) {
      const wv = p.w
      const hv = p.h
      const cx = p.x + wv / 2
      const cy = p.y + hv / 2
      const eTop = (p.eH ?? []).filter(Boolean).join("")
      const eLeft = (p.eW ?? []).filter(Boolean).join("")
      // O'lcham qoidasi `dimFit` da (modul boshida)
      const oW = dimFit(wv, hv, `${wv}${eTop}`, zoom)
      const oH = dimFit(hv, wv, `${hv}${eLeft}`, zoom)
      const dW = oW.fs
      const dH = oH.fs
      const oneLine = hv < 3.6 * dW // yupqa strip: uzunlik o'lchami pastki-chap burchakda
      const showW = oW.show
      const showH = oH.show
      const topB = showW && !oneLine ? dW * 1.2 : 2
      const leftB = showH ? dH * 1.2 : 2
      const label = `№${p.num ?? p.id} ${p.name}${p.rot ? " ⟳" : ""}${
        insts.length > 1 && !allDone ? ` ${doneCount}/${insts.length}` : ""
      }`
      const availW = wv - 2 * leftB
      const availH = hv - 2 * topB
      const vert = availH > availW * 1.15
      const longA = vert ? availH : availW
      const shortA = vert ? availW : availH
      // Nom O'LCHAMDAN katta bo'lmaydi: arrachi uchun ustuvorlik o'lchamda,
      // nom faqat identifikatsiya. Ilgari qisqa nomli katta detalda nom
      // o'lchamdan yirikroq chiqib, ko'zni birinchi bo'lib o'ziga tortardi.
      const nomMax = Math.min(dW, dH) * 0.9
      let fsN = Math.min(
        shortA * 0.55,
        (longA * 0.72) / Math.max(1, label.length * 0.52),
        nomMax,
      )
      let shown = label
      if (oneLine) fsN = Math.min(fsN, dW * 1.3)
      if (fsN * zoom < 9) {
        shown = `${p.num ?? p.id}`
        fsN = Math.min(
          shortA * 0.7,
          (longA * 0.7) / Math.max(1, shown.length * 0.62),
          40,
        )
        if (fsN * zoom < 6) shown = ""
      }
      if (availW < 16 || availH < 8) shown = ""
      // tekstura yo'nalishi: 3 gorizontal chiziq matn ORQASIDA, matndan uzunroq
      if (p.txt && wv > 60 && hv > 40) {
        const lw = shown && !vert ? shown.length * fsN * 0.27 + 10 : 0
        const th = Math.min(Math.max(wv * 0.22, lw + 120), wv * 0.45)
        const gp = Math.min(hv * 0.3, Math.max(fsN * 0.55, 16))
        for (const yy of [cy - gp, cy, cy + gp])
          labels.push(
            <line
              key={`tx${p.cell}-${yy}`}
              x1={cx - th}
              y1={yy}
              x2={cx + th}
              y2={yy}
              stroke="#1a1a1a"
              strokeWidth="2.5"
            />,
          )
      }
      // O'lcham/nom yozuvlari teshiklar ustiga tushmasin: har yozuvga bir necha
      // nomzod joy, teshiksiz birinchisi tanlanadi; tanlangan joy keyingi
      // yozuvlar uchun ham to'siq — yozuvlar bir-birining ustiga chiqmaydi
      type Box = { x: number; y: number; w: number; h: number }
      const obstacles: Box[] = []
      if (H) {
        for (const b of H.bores ?? []) {
          const [bx, by] = holeXY(p, H, b.x, b.y)
          const r = Math.max(b.d / 2, 4) + 4
          obstacles.push({ x: bx - r, y: by - r, w: 2 * r, h: 2 * r })
        }
        for (const b of H.edge ?? []) {
          const [lx, ly] = edgeLocalXY(H, b.side, b.pos)
          const [bx, by] = holeXY(p, H, lx, ly)
          const r = edgeBoreRect(p, bx, by, b.d, b.dp)
          obstacles.push({ x: r.x - 4, y: r.y - 4, w: r.w + 8, h: r.h + 8 })
        }
      }
      const overlaps = (b: Box) =>
        obstacles.some(
          (o) =>
            b.x < o.x + o.w &&
            o.x < b.x + b.w &&
            b.y < o.y + o.h &&
            o.y < b.y + b.h,
        )
      const pickSpot = <T extends { box: Box }>(cands: T[]): T => {
        const c = cands.find((v) => !overlaps(v.box)) ?? cands[0]
        obstacles.push(c.box)
        return c
      }

      const wText = `${wv}${eTop ? ` ${eTop}` : ""}`
      if (showW && oneLine) {
        const wlen = wText.length * dW * 0.62
        const spot = pickSpot(
          [
            { x: p.x + leftB + 6, y: p.y + hv - dW * 0.7 },
            { x: p.x + wv - wlen - 6, y: p.y + hv - dW * 0.7 },
            { x: p.x + leftB + 6, y: p.y + dW * 0.95 },
          ].map((c) => ({
            ...c,
            box: { x: c.x, y: c.y - dW * 0.85, w: wlen, h: dW },
          })),
        )
        labels.push(
          <text
            key={`w${p.cell}`}
            x={spot.x}
            y={spot.y}
            fontSize={dW}
            fill="#1f1f1f"
            fontWeight="700"
          >
            {wText}
          </text>,
        )
      } else if (showW) {
        const wlen = wText.length * dW * 0.62
        const spot = pickSpot(
          [
            { x: cx, y: p.y + dW * 0.85 },
            { x: p.x + wv * 0.28, y: p.y + dW * 0.85 },
            { x: p.x + wv * 0.72, y: p.y + dW * 0.85 },
            { x: cx, y: p.y + hv - dW * 0.35 },
            { x: p.x + wv * 0.28, y: p.y + hv - dW * 0.35 },
            { x: p.x + wv * 0.72, y: p.y + hv - dW * 0.35 },
          ].map((c) => ({
            ...c,
            box: { x: c.x - wlen / 2, y: c.y - dW * 0.85, w: wlen, h: dW },
          })),
        )
        labels.push(
          <text
            key={`w${p.cell}`}
            x={spot.x}
            y={spot.y}
            fontSize={dW}
            fill="#1f1f1f"
            fontWeight="700"
            textAnchor="middle"
          >
            {wText}
          </text>,
        )
      }
      const hText = `${hv}${eLeft ? ` ${eLeft}` : ""}`
      if (showH) {
        const hlen = hText.length * dH * 0.62
        const spot = pickSpot(
          [
            { x: p.x + dH * 0.85, y: cy },
            { x: p.x + dH * 0.85, y: p.y + hv * 0.3 },
            { x: p.x + dH * 0.85, y: p.y + hv * 0.72 },
            { x: p.x + wv - dH * 0.35, y: cy },
            { x: p.x + wv - dH * 0.35, y: p.y + hv * 0.3 },
            { x: p.x + wv - dH * 0.35, y: p.y + hv * 0.72 },
          ].map((c) => ({
            ...c,
            box: { x: c.x - dH * 0.85, y: c.y - hlen / 2, w: dH, h: hlen },
          })),
        )
        labels.push(
          <text
            key={`h${p.cell}`}
            x={spot.x}
            y={spot.y}
            fontSize={dH}
            fill="#1f1f1f"
            fontWeight="700"
            textAnchor="middle"
            transform={`rotate(-90 ${spot.x} ${spot.y})`}
          >
            {hText}
          </text>,
        )
      }
      if (shown) {
        const nw = vert ? fsN : shown.length * fsN * 0.55
        const nh = vert ? shown.length * fsN * 0.55 : fsN
        const spot = pickSpot(
          [cy, cy + hv * 0.18, cy - hv * 0.18].map((yy) => ({
            y: yy,
            box: { x: cx - nw / 2, y: yy - nh / 2, w: nw, h: nh },
          })),
        )
        labels.push(
          <text
            key={`n${p.cell}`}
            x={cx}
            y={spot.y}
            fontSize={fsN}
            fill="#111"
            fontWeight="700"
            textAnchor="middle"
            dominantBaseline="middle"
            transform={vert ? `rotate(-90 ${cx} ${spot.y})` : undefined}
          >
            {shown}
          </text>,
        )
      }
    }

    return (
      // biome-ignore lint/a11y/noStaticElementInteractions: SVG katakcha — 17" touch target (TZ 7.1.7)
      <g
        key={p.cell}
        onClick={() => {
          // Long press otilgan bo'lsa keyingi click yutiladi — tanlash ochilmasin
          if (lpFiredRef.current) {
            lpFiredRef.current = false
            return
          }
          if (p.waste) return
          // IKKI MARTA BOSISH — detal kartochkasini ochadi.
          //
          // Eski GibSaw dasturida ham kesish xaritasida shu jest ishlatilgan,
          // ya'ni operatorlarda odat allaqachon bor — yangisini o'rgatish
          // shart emas. Uzoq bosish ham qoladi, lekin u sensor DRAYVERIGA
          // bog'liq bo'lib chiqdi: bir panelda ishlaydi, boshqasida yo'q.
          // `click` esa brauzer eng ishonchli sintez qiladigan hodisa —
          // katak tanlanayotgan ekan, ikki marta bosish ham ishlaydi.
          // Kartochka ichida chekni bekor qilish tugmasi turadi: jest
          // buzg'unchi amalni O'ZI bajarmaydi, faqat ko'rinadigan
          // boshqaruvga olib boradi.
          //
          // 450 ms — Windows ning odatdagi ikki marta bosish oynasi (500 ms)
          // dan bir oz tor: qo'lqopdagi barmoq sekinroq, lekin ikkita ALOHIDA
          // bosish ham shundan tez ketma-ket bo'lmaydi.
          const hozir = Date.now()
          const oldingi = tapRef.current
          if (
            onOpenPart &&
            oldingi &&
            oldingi.cell === p.cell &&
            hozir - oldingi.t < 450
          ) {
            tapRef.current = null
            onOpenPart(p)
            return
          }
          tapRef.current = { cell: p.cell, t: hozir }
          onSelect(p)
        }}
        onPointerDown={
          !p.waste && !thumbnail && onOpenPart
            ? (e) => {
                lpFiredRef.current = false
                cancelLP()
                setHolding(p.cell)
                lpRef.current = {
                  t: window.setTimeout(() => {
                    lpFiredRef.current = true
                    setHolding(null)
                    onOpenPart(p)
                  }, 600),
                  x: e.clientX,
                  y: e.clientY,
                  id: e.pointerId,
                  type: e.pointerType,
                }
              }
            : undefined
        }
        className={p.waste ? undefined : "cursor-pointer"}
      >
        <rect
          x={p.x}
          y={p.y}
          width={p.w}
          height={p.h}
          fill={fill}
          stroke="#242424"
          strokeWidth="3"
          strokeDasharray={p.waste ? "16 11" : undefined}
        />
        {/* Uzoq bosish JARAYONI: 600 ms davomida katak asta bo'yaladi.
            Bosish qabul qilinganini darhol ko'rsatadi va qancha ushlash
            kerakligini o'rgatadi; barmoq siljib bekor bo'lsa bo'yoq
            yo'qoladi, ya'ni sabab ham ko'rinadi. */}
        {holding === p.cell && (
          <rect
            x={p.x}
            y={p.y}
            width={p.w}
            height={p.h}
            fill="#2f496e"
            className="animate-hold"
            pointerEvents="none"
          />
        )}
        {/* yuza teshiklari — haqiqiy masshtab: katta sverlo katta doira (GibSaw) */}
        {!p.waste &&
          H?.bores?.map((b, i) => {
            const [bx, by] = holeXY(p, H, b.x, b.y)
            return (
              <circle
                key={`b${i}`}
                cx={bx}
                cy={by}
                r={Math.max(b.d / 2, 4)}
                fill="#fafafa"
                stroke="#202020"
                strokeWidth="1.8"
              />
            )
          })}
        {/* qirra teshiklari — chetdan ichkariga, uzunlik = burg'u chuqurligi */}
        {!p.waste &&
          H?.edge?.map((b, i) => {
            const [lx, ly] = edgeLocalXY(H, b.side, b.pos)
            const [bx, by] = holeXY(p, H, lx, ly)
            const r = edgeBoreRect(p, bx, by, b.d, b.dp)
            return (
              <rect
                key={`e${i}`}
                x={r.x}
                y={r.y}
                width={r.w}
                height={r.h}
                fill="#fafafa"
                stroke="#202020"
                strokeWidth="1.6"
              />
            )
          })}
      </g>
    )
  })

  // polosa o'lcham zanjiri: chetda strelka, ichki chegarada kesim davomi + ✕ (GibSaw)
  const dimNodes = (thumbnail ? [] : (sheet.dims ?? [])).map((dm, i) => {
    const mid = (dm.a + dm.b) / 2
    if (dm.ax === "X") {
      const y = -34
      return (
        <g key={`dm${i}`} stroke="#1a1a1a" strokeWidth="2" fill="none">
          <line x1={dm.a} y1={y} x2={dm.b} y2={y} />
          {dm.a <= 6 ? (
            <path d={`M${dm.a} ${y} l13 -8 M${dm.a} ${y} l13 8`} />
          ) : (
            <path
              d={`M${dm.a} -50 L${dm.a} 0 M${dm.a - 11} -45 L${dm.a + 11} -23 M${dm.a - 11} -23 L${dm.a + 11} -45`}
            />
          )}
          {dm.b >= L - 6 ? (
            <path d={`M${dm.b} ${y} l-13 -8 M${dm.b} ${y} l-13 8`} />
          ) : (
            <path
              d={`M${dm.b} -50 L${dm.b} 0 M${dm.b - 11} -45 L${dm.b + 11} -23 M${dm.b - 11} -23 L${dm.b + 11} -45`}
            />
          )}
          <text
            x={mid}
            y={y - 14}
            fontSize="44"
            fontWeight="bold"
            fill="#000"
            stroke="none"
            textAnchor="middle"
          >
            {dm.v}
          </text>
        </g>
      )
    }
    const x = -34
    return (
      <g key={`dm${i}`} stroke="#1a1a1a" strokeWidth="2" fill="none">
        <line x1={x} y1={dm.a} x2={x} y2={dm.b} />
        {dm.a <= 6 ? (
          <path d={`M${x} ${dm.a} l-8 13 M${x} ${dm.a} l8 13`} />
        ) : (
          <path
            d={`M-50 ${dm.a} L0 ${dm.a} M-45 ${dm.a - 11} L-23 ${dm.a + 11} M-45 ${dm.a + 11} L-23 ${dm.a - 11}`}
          />
        )}
        {dm.b >= W - 6 ? (
          <path d={`M${x} ${dm.b} l-8 -13 M${x} ${dm.b} l8 -13`} />
        ) : (
          <path
            d={`M-50 ${dm.b} L0 ${dm.b} M-45 ${dm.b - 11} L-23 ${dm.b + 11} M-45 ${dm.b + 11} L-23 ${dm.b - 11}`}
          />
        )}
        <text
          x={x - 14}
          y={mid}
          fontSize="44"
          fontWeight="bold"
          fill="#000"
          stroke="none"
          textAnchor="middle"
          transform={`rotate(-90 ${x - 14} ${mid})`}
        >
          {dm.v}
        </text>
      </g>
    )
  })

  const svgEl = (
    <svg
      ref={svgRef}
      viewBox={
        vb
          ? `${vb.x} ${vb.y} ${vb.w} ${vb.h}`
          : `${base.x} ${base.y} ${base.w} ${base.h}`
      }
      className={`h-full w-full touch-none select-none${thumbnail ? " pointer-events-none" : ""}`}
      preserveAspectRatio="xMidYMid meet"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerEnd}
      onPointerCancel={onPointerEnd}
      onContextMenu={(e) => onOpenPart && e.preventDefault()}
    >
      <title>Kesish xaritasi</title>
      <defs>
        <pattern
          id="zebra"
          width="36"
          height="36"
          patternTransform="rotate(45)"
          patternUnits="userSpaceOnUse"
        >
          <rect width="36" height="36" fill="#eef0f2" />
          <rect width="18" height="36" fill="#c9d2de" />
        </pattern>
      </defs>
      {/* fon zebra: detal tushmagan joy = atxot (GibSaw) */}
      <rect
        x="0"
        y="0"
        width={L}
        height={W}
        fill="url(#zebra)"
        stroke="#3a3a3a"
        strokeWidth="5"
      />
      {partNodes}
      {/* arra yo'llari — guillotine, qora uzluksiz (GibSaw) */}
      {(sheet.cuts ?? []).map((c, i) => (
        <line
          key={i}
          x1={c.x1}
          y1={c.y1}
          x2={c.x2}
          y2={c.y2}
          stroke="#242424"
          strokeWidth="3"
        />
      ))}
      {dimNodes}
      {!thumbnail && <g pointerEvents="none">{labels}</g>}
    </svg>
  )

  return svgEl
}
