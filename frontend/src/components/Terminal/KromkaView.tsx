// KROMKA post sahifasi — bitta to'liq kenglikdagi jadval: arradan chiqqan
// kromkali detallar, har skan darhol yoziladi. Jarayondagi (2+ tomonli, bir
// tomoni skan qilingan, tugamagan) qatorlar TEPADA sariq fonda, tugaganlari
// pastda yashil; sarlavhada «Jarayonda N». Xato skan BEKOR QILISH (60s) bilan
// qaytariladi.

import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { type KromkaPartRow, TerminalService } from "@/client"
import { OperationChips } from "@/components/Common/OperationChips"
import { QueryError } from "@/components/Common/QueryError"
import { PartPreview } from "@/components/Terminal/PartCard"
import { PostHeader } from "@/components/Terminal/PostHeader"
import { PostProgress } from "@/components/Terminal/PostProgress"
import type { SheetPart } from "@/components/Terminal/SheetSvg"
import { useDragScroll } from "@/components/Terminal/useDragScroll"
import { Skeleton } from "@/components/ui/skeleton"
import { useScanFlash } from "@/hooks/useScanFlash"
import {
  formatSize,
  KROMKA_VERDICT_LABELS,
  KROMKA_VERDICT_STYLE,
} from "@/lib/mes"
import { cn } from "@/lib/utils"

/** Qaysi tomonlarga kromka — CHEKDAGI eskiz bilan bir xil konvensiya
 *  (labels.py `burilgan`): uzun tomon `length` bo'lsa eskiz 90° burilgan,
 *  ya'ni t→chap, b→o'ng, l→past, r→tepa; aks holda tabiiy (l→chap, r→o'ng,
 *  t→tepa, b→past). Kromkachi chekdagi rasm bilan solishtiradi — bu yerda
 *  boshqa yo'nalish chalg'itardi. */
function EdgeGlyph({
  edges,
  length,
  width,
  paz = [],
  frez = [],
  className = "size-16",
  band = 3,
  minW = 8,
}: {
  edges: Record<string, unknown>
  length: number | null | undefined
  width: number | null | undefined
  /** Paz (ariq) ketadigan qirralar — chekdagi UZUQ chiziq bilan bir xil manba */
  paz?: string[]
  /** Freza (kesib o'tadi) ketadigan qirralar — chekdagi TUTASH chiziq */
  frez?: string[]
  /** Jadvalda `size-16`, luppa qatlamida katta o'lcham */
  className?: string
  /** Kromka chizig'i, viewBox birligida. Luppada KICHIK bo'lishi kerak:
   *  strokeWidth viewBox birligida, ya'ni eskiz bilan birga kattalashadi —
   *  jadvaldagi 3 birlik (6.4 px) luppada 35 px = 9.2 mm plitaga aylanardi. */
  band?: number
  /** Eskiz enining PASTKI chegarasi, viewBox birligida.
   *  Jadvalda 8 kerak: sokl (100x1775) haqiqiy nisbatda 1.46 birlik = 3 px
   *  bo'lib, 64 px eskizda ko'rinmasdi. Luppada esa 352 px — o'sha 1.46
   *  birlik 17 px, ya'ni HAQIQIY nisbatni ko'rsatish mumkin (klamp detalni
   *  5.5 barobar kengaytirib yuborardi — o'lchangan). Luppada 4: haqiqiy
   *  1.46 birlikda panel 17.6 px bo'lib, 11.7 px lik kromka belgisi uni
   *  deyarli to'ldirardi — qaysi qirra ishlanishi ko'rinmasdi. */
  minW?: number
}) {
  const burilgan = (length ?? 0) > (width ?? 0)
  const has = (k: string) => !!edges[k]
  // Xarita BITTA joyda: kromka ham, paz ham shundan o'qiydi (ilgari ikki shaklda
  // yozilgan edi — biri tomon->joy, ikkinchisi joy->bormi).
  const joy: Record<string, string> = burilgan
    ? { t: "chap", b: "ong", l: "past", r: "tepa" }
    : { l: "chap", r: "ong", t: "tepa", b: "past" }
  const side = Object.fromEntries(
    Object.entries(joy).map(([tomon, j]) => [j, has(tomon)]),
  ) as Record<string, boolean>
  const pazJoy = new Set(paz.map((t) => joy[t]))
  const frezJoy = new Set(frez.map((t) => joy[t]))
  // Chekdagi kabi eskiz DOIM tik: uzun tomon vertikal, eni nisbatga qarab
  // (labels.py: `bh = area_h; bw = bh * short/long`). `burilgan` faqat qaysi
  // qirra qaysi tomonga tushishini hal qiladi, shaklni emas.
  const long = Math.max(length ?? 0, width ?? 0)
  const short = Math.min(length ?? 0, width ?? 0)
  const h = 26
  const w = long > 0 ? Math.max(minW, Math.round((h * short) / long)) : 18
  // Kromka chizig'i panel enining CHORAGIDAN oshmasin: tor detalda (sokl)
  // belgi panelni to'ldirib, qaysi qirra ishlanishi ko'rinmay qolardi.
  const bandW = Math.min(band, w / 4)
  const x = (30 - w) / 2
  const y = (30 - h) / 2
  // Kromka chizig'i — loyihaning siyoh rangi (`--foreground: #1c2b42`), SOF
  // QORA emas: eskiz UI elementi, ya'ni qolgan jadval matni bilan bir xil
  // token'da bo'lishi kerak. Chekdagi `#111` dan farqi 1.33x — 2px chiziqda
  // ko'zga bilinmaydi, shuning uchun kromkachi uchun ikkalasi bir xil qora.
  // Ilgari amber edi va uch sababdan yaramasdi:
  // (1) kontrast chegarada — amber-600 oq qatorda 3.19x, `bg-amber-50/70`
  //     (jarayonda) da 3.10x, `bg-green-50` (bajarildi) da 3.04x; WCAG SC
  //     1.4.11 minimumi 3.0x, `foreground` esa 13.6-14.3x. 17" monoblokda
  //     kontrast birinchi yo'qoladi (docs/06);
  // (2) bu jadvalda amber HOLAT rangi — qator foni, "Jarayonda N" belgisi va
  //     chek chiqarilgan nusxa chipi amber; bitta rang ikki ma'noda edi;
  // (3) chekda qora, luppada (`PartPreview`) qora — faqat jadval farq qilardi.
  // Luppa xom `#111` da QOLADI: u UI emas, termal chekning nusxasi —
  // `PartPreview` butunlay bosma ranglarda ishlaydi (`#d2d2d2`, `#242424`).
  const line = "stroke-foreground"
  // Qalinligi 2: standart 1 px chiziq 17" monoblokda 0.25 mm bo'lib xira ko'rinardi.
  const pazLine = "stroke-sky-700 [stroke-dasharray:4_2]"
  const frezLine = "stroke-sky-700"
  const ichki: Record<string, [number, number, number, number]> = {
    tepa: [x + 2, y + 3, x + w - 2, y + 3],
    past: [x + 2, y + h - 3, x + w - 2, y + h - 3],
    chap: [x + 3, y + 2, x + 3, y + h - 2],
    ong: [x + w - 3, y + 2, x + w - 3, y + h - 2],
  }
  // Jadvalda size-16 = 64 px = 17" monoblokda 16.8 mm. Ilgari size-12 (12.6 mm)
  // edi va tsexda kichik deb topildi; size-8 (8.4 mm) da uzuq/tutash farqi
  // umuman bilinmasdi. NARXI o'lchangan (haqiqiy ilovada): qator 82 -> 95 px.
  // Kattalashtirish ENDI JADVAL ICHIDA EMAS (`EdgeZoom` qatlamida) — ilgari
  // `active:scale-[2.2]` ishlatilardi va u ikki sababdan yetarli emas edi:
  // (1) `thead` `sticky z-10`, eskiz esa `position:static; z-index:auto` —
  //     tepadagi qatorda kattalashgan eskizning 71 px i sarlavha ORQASIDA
  //     qolardi (o'lchangan); scroller ham uni kesardi;
  // (2) 2.2x = 141 px (37 mm) da qaysi tomon ishlanishi baribir aniq emasdi.
  return (
    <svg
      viewBox="0 0 30 30"
      className={`${className} shrink-0`}
      aria-hidden="true"
    >
      <title>Kromka tomonlari</title>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        className="fill-muted stroke-muted-foreground/50"
        strokeWidth="1"
      />
      {/* Chiziq qirraning ICHIGA suriladi (`bandW / 2`): markazda tursa yarmi
          tashqarida qolib, tor detalni (sokl: panel 8 birlik, chiziq 3) ko'zga
          kengroq ko'rsatardi — panel nisbati buzilardi. */}
      {side.tepa && (
        <line
          x1={x}
          y1={y + bandW / 2}
          x2={x + w}
          y2={y + bandW / 2}
          className={line}
          strokeWidth={bandW}
        />
      )}
      {side.past && (
        <line
          x1={x}
          y1={y + h - bandW / 2}
          x2={x + w}
          y2={y + h - bandW / 2}
          className={line}
          strokeWidth={bandW}
        />
      )}
      {side.chap && (
        <line
          x1={x + bandW / 2}
          y1={y}
          x2={x + bandW / 2}
          y2={y + h}
          className={line}
          strokeWidth={bandW}
        />
      )}
      {side.ong && (
        <line
          x1={x + w - bandW / 2}
          y1={y}
          x2={x + w - bandW / 2}
          y2={y + h}
          className={line}
          strokeWidth={bandW}
        />
      )}
      {/* Paz/freza — chekdagidek kontur ICHIDA (kromka esa chekkada, tutash va
          qalin). Tomon nomi yozilmaydi: eskiz o'lchamga qarab buriladi. */}
      {Object.entries(ichki).map(([j, [x1, y1, x2, y2]]) =>
        pazJoy.has(j) || frezJoy.has(j) ? (
          <line
            key={j}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            /* Bir qirrada ikkalasi bo'lsa PAZ g'olib — chek bilan bir xil
               (`labels.py`: `ishlangan_tomonlari`). */
            className={pazJoy.has(j) ? pazLine : frezLine}
            strokeWidth="2"
          />
        ) : null,
      )}
    </svg>
  )
}

// Kromka lentalari — yorliqdagi GibLab EL harfi VA lenta nomi: "A — 1-19 kashmir".
// Yolg'iz harf tsexda tushunarsiz edi (operator uni tomonlar TARTIBI deb o'ylagan,
// 2026-09-12) — harf lenta TURINI bildiradi, tartibni emas: tomonlar istalgan
// ketma-ketlikda skanlanadi. Tomon NOMI ("Chap") ataylab yo'q: eskiz uzun tomonni
// vertikal chizadi, l/r/t/b joyi o'lchamga qarab almashadi (labels.py `burilgan`).
const edgeBands = (edges: Record<string, unknown>): string => {
  const juft = new Map<string, string>()
  for (const e of Object.values(edges)) {
    const q = e as { symbol?: string | null; mat?: string | null } | null
    if (!q) continue
    const sym = q.symbol || "\u2022"
    if (!juft.has(sym)) juft.set(sym, (q.mat || "").trim())
  }
  return [...juft]
    .map(([sym, mat]) => (mat ? `${sym} — ${mat}` : sym))
    .join(" · ")
}

/** KROMKA qatoridan `PartPreview` uchun sintetik katak.
 *
 *  Chek va kesish xaritasi bilan BITTA konvensiya (`labels.py` `burilgan`):
 *  eskiz uzun tomonni doim vertikal chizadi, `rot` esa teshik koordinatasini
 *  (x,y)->(y, l-x) o'giradi. `eW`/`eH` — kromka chiziqlari: xaritada ularni
 *  backend hisoblaydi (`cutmap._edge_markers`), bu yerda esa `edges` dan o'sha
 *  qoida bo'yicha yig'iladi.
 */
function zoomCell(row: KromkaPartRow): SheetPart {
  const L = row.length ?? 0
  const W = row.width ?? 0
  const burilgan = L > W
  const e = (row.edges ?? {}) as Record<string, unknown>
  const bor = (k: string) => (e[k] ? "1" : null)
  // burilgan: t->chap, b->ong, l->past, r->tepa; aks holda tabiiy
  const eW = burilgan ? [bor("t"), bor("b")] : [bor("l"), bor("r")]
  const eH = burilgan ? [bor("r"), bor("l")] : [bor("t"), bor("b")]
  return {
    cell: 0,
    id: row.part_id,
    name: row.name,
    waste: false,
    x: 0,
    y: 0,
    // Chizma maydoni: uzun tomon vertikal
    w: burilgan ? W : L,
    h: burilgan ? L : W,
    rot: burilgan,
    eW,
    eH,
  }
}

/** Luppa qatlami — eskizni KATTA ko'rsatadi.
 *
 *  Nega jadval ichida emas: `thead` `sticky z-10`, eskiz esa oddiy oqimda —
 *  tepadagi qatorda `scale()` bilan kattalashgan eskizning yarmi sarlavha
 *  ORQASIDA qolardi (o'lchangan: 141 px dan 71 px i yashirin), scroller ham
 *  kesardi. `fixed` qatlam ikkala to'siqdan ham chiqadi.
 *
 *  Nega Dialog EMAS: `routes/terminal.tsx` dagi `dialogOpen` skan fokusini
 *  o'chiradi (`useScanFocus`), ya'ni eskizni ochib qo'ygan kromkachining skani
 *  yo'qolardi. Bu shunchaki ustiga chizilgan qatlam — holat o'zgarmaydi,
 *  `pointer-events-none` bilan hech qanday hodisani ham yutmaydi. */
function EdgeZoom({ row }: { row: KromkaPartRow }) {
  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60">
      <div className="flex items-center gap-8 rounded-2xl border bg-white px-10 py-8 shadow-2xl">
        {/* Teshigi bor detalda CHEKDAGI chizmaning o'zi (`PartPreview`) —
            teshik o'rinlari yo'nalishni bir ma'noli qiladi: simmetrik detalda
            (ikkala uzun qirra bir xil) qaysi qirra lentalanishini faqat shu
            ajratadi, detal teskari ushlansa chizma ham teskari bo'ladi.
            Prodda o'lchangan: kromkali detallarning 67% i shunday, ularning
            89% ida teshik bor. Teshiksiz detalda sodda eskiz qoladi. */}
        <div className="w-[26rem] shrink-0">
          {row.holes ? (
            <PartPreview
              part={zoomCell(row)}
              holes={{ [row.part_id]: row.holes }}
            />
          ) : (
            <EdgeGlyph
              edges={row.edges ?? {}}
              length={row.length}
              width={row.width}
              paz={row.paz_sides ?? []}
              frez={row.frez_sides ?? []}
              className="size-[22rem]"
              band={1}
              minW={4}
            />
          )}
        </div>
        <div className="min-w-0 max-w-[26rem]">
          <div className="truncate text-3xl font-black">{row.name}</div>
          <div className="num mt-1 text-xl text-muted-foreground">
            {formatSize(row.length, row.width, row.thickness)}
          </div>
          <div className="mt-4 text-2xl font-bold">{row.sides} tomon</div>
          <div className="mt-1 text-lg text-muted-foreground">
            {edgeBands(row.edges ?? {})}
          </div>
          {((row.paz_sides ?? []).length > 0 ||
            (row.frez_sides ?? []).length > 0) && (
            <div className="mt-3 text-lg font-semibold text-sky-700">
              {[
                (row.paz_sides ?? []).length > 0 && "paz",
                (row.frez_sides ?? []).length > 0 && "freza",
              ]
                .filter(Boolean)
                .join(" + ")}{" "}
              — eskizdagi ichki chiziq
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}

/** Kromka stansiyasi o'lchagan oxirgi detallar — HUKMI bilan.
 *
 *  O'lchov o'sha ish markazidagi oxirgi skanga bog'lanadi (`services/kromka.py`),
 *  shuning uchun tasmada raqam yonida kutilgan o'lcham va qolgan tomonlar turadi:
 *  «520 mm — 2/2 · 430 mm — 1/2». Tartib ahamiyatsiz — operator qaysi tomonni
 *  oldin qo'ysa, o'sha guruhdan bitta joy yopiladi. Mos kelmagan o'lchovda brak
 *  oynasi o'zi ochiladi (`routes/terminal.tsx`), bu tasma faqat ko'rsatadi.
 *  Stansiya ulanmagan postda tasma umuman chizilmaydi. */
function StationStrip() {
  const { data } = useQuery({
    queryKey: ["terminal", "kromka", "measurements"],
    queryFn: async () => (await TerminalService.readKromkaMeasurements()).data,
    // WS har o'lchovda ro'yxatni yangilaydi; poll — soket uzilgan holat uchun zaxira
    refetchInterval: 30_000,
  })
  const rows = data ?? []
  if (!rows.length) return null
  const [last, ...prev] = rows
  return (
    <div className="flex items-center gap-3 border-b bg-sky-50/70 px-4 py-2">
      <span className="text-xs font-bold uppercase tracking-wider text-sky-900">
        Stansiya o'lchovi
      </span>
      <span className="num text-2xl font-black text-sky-900">
        {last.length_mm?.toFixed(1) ?? "—"}
        <span className="ml-1 text-sm font-bold">mm</span>
      </span>
      <span
        className={cn(
          "rounded-md px-2 py-0.5 text-xs font-black",
          KROMKA_VERDICT_STYLE[last.verdict] ?? "bg-muted",
        )}
      >
        {KROMKA_VERDICT_LABELS[last.verdict] ?? last.verdict}
      </span>
      {/* Pico kodi: OK — ikkala datchik mos; FARQ/FAQAT1/FAQAT2 — datchik muammosi */}
      {last.code !== "OK" && (
        <span className="rounded-md bg-amber-200 px-2 py-0.5 text-xs font-black text-amber-900">
          {last.code}
        </span>
      )}
      <span className="num text-xs text-sky-800">
        {last.expected_mm != null
          ? `kutilgan ${last.expected_mm.toFixed(0)} mm`
          : "kutilgan o'lcham yo'q"}
        {last.part_name ? ` · ${last.part_name}` : ""}
      </span>
      <span className="num ml-auto truncate text-xs text-sky-700/70">
        {prev.map((r) => r.length_mm?.toFixed(0) ?? "—").join(" · ")}
      </span>
    </div>
  )
}

export function KromkaView({
  orderId,
  onBack,
  registerScan,
  oval = false,
}: {
  orderId: number
  onBack: () => void
  /** Skan oldidan tekshiruv: null = yozish mumkin, "NOTFOUND" = bu proyektda
   * yo'q, boshqa string = foydalanuvchiga ko'rsatiladigan xato. */
  registerScan?: (fn: ((qr: string) => string | null) | null) => void
  /** OVAL post: har detal 1 skan — Jarayonda paneli va tomonlar ustuni ortiqcha */
  oval?: boolean
}) {
  // Monoblokda barmoq bilan surib aylantirish — scrollbar qo'lqopda tortilmaydi
  const listScroll = useDragScroll()
  // Luppa: eskiz BIR MARTA bosilsa ochiladi, qayta bosilsa yopiladi.
  const [zoom, setZoom] = useState<KromkaPartRow | null>(null)
  const tap = useRef<{ x: number; y: number; id: number | null } | null>(null)
  // Luppa boshqaruvi BITTA joyda: hujjat darajasidagi tap.
  //
  // `pointerdown` da nuqta va nishon eslab qolinadi, `pointerup` da 8 px dan
  // kam surilgan bo'lsa BOSISH deb hisoblanadi. Surilgan bo'lsa — bu ro'yxatni
  // aylantirish (`useDragScroll`), luppaga tegilmaydi.
  //
  // Qoida: o'sha eskiz bosilsa yopiladi, boshqasi bosilsa o'shanga almashadi,
  // eskizdan tashqari joy bosilsa yopiladi. Alohida "X" tugmasi kerak emas —
  // 17" monoblokda har qanday bosish allaqachon yopadi.
  useEffect(() => {
    const down = (e: PointerEvent) => {
      const el = (e.target as HTMLElement | null)?.closest?.("[data-glyph]")
      const id = el ? Number((el as HTMLElement).dataset.glyph) : null
      tap.current = { x: e.clientX, y: e.clientY, id }
    }
    const up = (e: PointerEvent) => {
      const t = tap.current
      tap.current = null
      if (!t) return
      if (Math.abs(e.clientX - t.x) > 8 || Math.abs(e.clientY - t.y) > 8) return
      setZoom((cur) => {
        if (t.id === null) return null
        if (cur && cur.route_id === t.id) return null
        return rowsRef.current.find((r) => r.route_id === t.id) ?? null
      })
    }
    document.addEventListener("pointerdown", down, true)
    document.addEventListener("pointerup", up, true)
    return () => {
      document.removeEventListener("pointerdown", down, true)
      document.removeEventListener("pointerup", up, true)
    }
  }, [])

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["terminal", "kromka", orderId],
    queryFn: async () =>
      (
        await TerminalService.readTerminalKromka({
          path: { order_id: orderId },
        })
      ).data,
    refetchInterval: 30_000,
  })
  // Luppa effekti bo'sh deps bilan ishlaydi (listener bir marta qo'yiladi),
  // shuning uchun joriy qatorlarga ref orqali murojaat qiladi.
  const rowsRef = useRef<KromkaPartRow[]>([])
  rowsRef.current = data?.parts ?? []

  // KromkaPartRow'da edges/instances sxemada ixtiyoriy — bir joyda normallashtiramiz,
  // quyida hamma joyda oddiy massiv/obyekt sifatida ishlatiladi
  const parts = (data?.parts ?? []).map((p) => ({
    ...p,
    edges: p.edges ?? {},
    instances: p.instances ?? [],
  }))

  // Tekshiruv har renderda yangi data ko'radi, terminal esa bir marta ro'yxatga oladi
  const checkRef = useRef<(qr: string) => string | null>(() => "NOTFOUND")
  checkRef.current = (qr: string): string | null => {
    // Aynan moslik — eski `_1` fallback olib tashlandi (backend bilan bir).
    // Detal KROMKA'dan ikki marta o'tishi mumkin ([3,6,3]) — har qadamga alohida qator. Qadamlardan
    // bittasi ochiq bo'lsa skan haqli; birinchi topilgan qatorga qarab hukm chiqarib bo'lmaydi.
    const rows = parts.flatMap((p) => {
      const inst = p.instances.find((i) => i.qr_text === qr)
      return inst ? [{ p, inst }] : []
    })
    if (!rows.length) return "NOTFOUND"
    if (!rows.some(({ inst }) => inst.arra_passed))
      return "Bu detal hali arradan chiqmagan."
    if (rows.some(({ p, inst }) => inst.done < p.sides)) return null
    return oval
      ? "Bu detalning oval kromkasi allaqachon tugagan."
      : "Bu detalning kromkasi allaqachon tugagan."
  }
  useEffect(() => {
    registerScan?.((qr) => checkRef.current(qr))
    return () => registerScan?.(null)
  }, [registerScan])

  // Oxirgi skan bo'lgan detal qatori keyingi skangacha ajralib turadi + avto-scroll
  const flashId = useScanFlash(
    parts,
    (p) => p.route_id,
    (p) => p.instances.reduce((s, i) => s + i.done, 0),
    "kv-row-",
  )

  if (isLoading) return <Skeleton className="h-full w-full" />
  // Xato JIM yutilmasin: busiz `data` undefined qolib, ro'yxat "Arradan kelgan
  // detal yo'q" bo'lib ko'rinardi va kromkachi yo'q detallarni kutib turardi.
  if (isError) return <QueryError onRetry={() => refetch()} />

  // Arradan chiqqan nusxalar, uch pog'ona: JARAYONDA (bir tomoni skan
  // qilingan, tugamagan — kromkachi shuni davom ettiradi) tepada, keyin
  // boshlanmaganlar, tugaganlari yashil bo'lib PASTDA. Ilgari o'ng tomonda
  // alohida «Jarayonda» paneli bor edi — u jadvalning «Holat» ustunini
  // takrorlar va jadvalni yarim kenglikka siqib, nusxa chiplarini ustma-ust
  // (qatorni 4 barobar baland) qilib yuborardi. Endi jadval to'liq kenglikda,
  // jarayondagi qator tepada va sariq fonda.
  const tier = (p: { sides: number; instances: { done: number }[] }) => {
    const started = p.instances.some((i) => i.done > 0 && i.done < p.sides)
    if (started) return 0
    return p.instances.every((i) => i.done >= p.sides) ? 2 : 1
  }
  const leftParts = parts
    .map((p) => ({
      ...p,
      instances: p.instances.filter((i) => i.arra_passed),
    }))
    .filter((p) => p.instances.length > 0)
    .sort((a, b) => tier(a) - tier(b) || a.code.localeCompare(b.code))
  // Sarlavhadagi hisob: nechta nusxa yarim yo'lda (2+ tomonli, boshlangan)
  const inProgressCount = parts.reduce(
    (n, p) =>
      n +
      p.instances.filter((i) => p.sides >= 2 && i.done > 0 && i.done < p.sides)
        .length,
    0,
  )
  const totDone = parts.reduce((s, p) => s + p.total_done, 0)
  const totReq = parts.reduce((s, p) => s + p.total_required, 0)

  return (
    <div className="flex h-full min-h-0 gap-3">
      {zoom && <EdgeZoom row={zoom} />}
      {/* CHAP: arradan kelgan detallar, progress joyida ko'rinadi */}
      <div className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
        <PostHeader
          className="flex-wrap"
          onBack={onBack}
          orderNumber={data?.order_number}
          projectName={data?.project_name}
        >
          {/* Qaysi lentadan qancha kerak — kromkachi ishni boshlashdan OLDIN
              skladdan aynan shu rulonlarni olib keladi. Son GibLab'ning O'Z
              hisobi (qirqim zaxirasi bilan), ya'ni texnolog ko'radigan raqam.
              SARLAVHA qatorida, alohida qator emas: tsex paneli 1366×768 va
              BALANDLIK tanqis — 40 px lik qator jadvalning yana bir qatoriga
              teng. Eni yetadi (o'lchandi: sarlavha 473 + lentalar 473 = 934,
              panelda 1366). Beshta lentadan ko'p bo'lsa `flex-wrap` ikkinchi
              qatorga tushiradi — ya'ni eng yomon holat avvalgi ko'rinish. */}
          {!!data?.bands?.length && (
            /* BITTA guruh, ajratuvchi chiziq bilan. Ilgari har lenta sarlavhaning
               alohida bolasi edi va hamma oraliq bir xil (`gap-3`) bo'lgani uchun
               ular sarlavha blokining DAVOMI bo'lib o'qilardi — qatorning vertikal
               markazida turib, loyiha nomi bilan buyurtma raqami ORASIGA
               kirib qolardi (o'lchandi: sarlavha bloki y 88..132, lentalar
               markazi y≈110 — aynan nom bilan raqam chegarasi).
               TO'LDIRILGAN blok, ingichka chiziq emas: chiziq oraliqqa va
               vertikal joylashuvga bog'liq, fon esa alohida OBYEKT bo'lib
               o'qiladi va sarlavhadagi «Jarayonda N» belgisi bilan bir tilda.
               O'rash `flex-wrap` uchun ham to'g'ri — lentalar uzilib qolmaydi. */
            <div className="ml-1 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg bg-muted px-3 py-1">
              {data.bands.map((b) => (
                <span key={b.name} className="flex items-baseline gap-1.5">
                  <span className="text-sm font-semibold">{b.name}</span>
                  <span className="num text-lg font-black">
                    {Math.round(b.metres)} m
                  </span>
                </span>
              ))}
            </div>
          )}
          {/* Yarim yo'ldagi nusxalar soni — ular jadval tepasida sariq */}
          {!oval && inProgressCount > 0 && (
            <span className="num ml-auto rounded-md bg-amber-100 px-2.5 py-1 text-sm font-bold text-amber-800">
              Jarayonda {inProgressCount}
            </span>
          )}
          <PostProgress
            className={oval || !inProgressCount ? "ml-auto" : "ml-3"}
            done={totDone}
            total={totReq}
          />
        </PostHeader>
        <StationStrip />
        <div
          className="min-h-0 flex-1 overflow-y-auto"
          ref={listScroll.ref}
          {...listScroll.props}
        >
          <table className="w-full text-base">
            <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <th className="px-4 py-2.5">Kod</th>
                <th className="px-4 py-2.5">Nomi</th>
                <th className="px-4 py-2.5">O'lchami</th>
                <th className="px-4 py-2.5">
                  {oval ? "Qirralar" : "Kromka"}
                  {/* `whitespace-nowrap` YO'Q: bu izoh bir qatorda 400 px dan oshib,
                      jadval avto-layoutida ustunni ikki barobar kengaytirib yuborardi
                      va Nomi/Nusxalar siqilardi (o'lchangan). Ikki qatorga bo'linadi. */}
                  <span className="block max-w-[230px] text-2xs font-medium normal-case leading-tight tracking-normal">
                    qalin = lenta · uzuq = paz · tutash = freza · harf = lenta
                    turi (tartib emas)
                  </span>
                </th>
                <th className="px-4 py-2.5 text-right">
                  {/* Terminalda hover yo'q — izoh sarlavhaning o'zida: chip
                      nusxa, raqam qilingan/jami tomon */}
                  Nusxalar
                  <span className="block whitespace-nowrap text-2xs font-medium normal-case tracking-normal">
                    qilingan / tomon · ✓ bajarildi
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {leftParts.map((p) => {
                const finished = p.instances.every((i) => i.done >= p.sides)
                const started = !finished && tier(p) === 0
                const pazBor = (p.paz_sides ?? []).length > 0
                const frezBor = (p.frez_sides ?? []).length > 0
                return (
                  <tr
                    key={p.route_id}
                    id={`kv-row-${p.route_id}`}
                    className={cn(
                      "border-b last:border-0",
                      finished && "bg-green-50",
                      started && "bg-amber-50/70",
                      // Xatcho'p: holat rangini bosmaydi, chap chetda turadi
                      flashId === p.route_id && "border-l-4 border-l-primary",
                    )}
                  >
                    <td className="num whitespace-nowrap px-4 py-3 font-semibold">
                      {p.code}
                    </td>
                    <td className="max-w-[240px] px-4 py-3">
                      <div className="truncate">{p.name}</div>
                      <OperationChips
                        processCode={p.process_code}
                        postCode={oval ? "OVAL" : "KROMKA"}
                        defaultCode={oval ? 5 : 3}
                      />
                    </td>
                    <td className="num whitespace-nowrap px-4 py-3 text-sm">
                      {formatSize(p.length, p.width, p.thickness)}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className="inline-flex items-center gap-2">
                        {/* Eskiz — BIR MARTA bosilsa luppa ochiladi, qayta
                            bosilsa yopiladi. Bosib turish EMAS: qo'lqopda
                            uzluksiz tegib turish ishonchsiz va qo'l band
                            bo'ladi. Mantiq bitta joyda — quyidagi effektda. */}
                        <span
                          className="cursor-zoom-in"
                          data-glyph={p.route_id}
                        >
                          <EdgeGlyph
                            edges={p.edges}
                            length={p.length}
                            width={p.width}
                            paz={p.paz_sides ?? []}
                            frez={p.frez_sides ?? []}
                          />
                        </span>
                        <span className="min-w-0">
                          {/* `text-xl` (20 px = 5.2 mm) TEKIN: eskiz 64 px
                              bo'lgach qator balandligini o'sha belgilaydi, matn
                              ustuni esa 64 px gacha bemalol o'sadi — o'lchangan,
                              qator 94 px da qoladi. */}
                          {!oval && <b className="text-xl">{p.sides} tomon</b>}
                          <span className="block max-w-[240px] truncate text-sm text-muted-foreground">
                            {edgeBands(p.edges)}
                          </span>
                          {(pazBor || frezBor) && (
                            <span className="block text-xs font-semibold text-sky-700">
                              {[pazBor && "paz", frezBor && "freza"]
                                .filter(Boolean)
                                .join(" + ")}{" "}
                              — eskizdagi ichki chiziq
                            </span>
                          )}
                        </span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {/* Ish TUGAGANDA bitta aniq belgi — prisadkadagi bilan
                          bir xil. Ilgari bu yerda faqat nusxa chiplari turardi
                          va tugagan qatorda ular hammasi "✓" bo'lib, "tayyor"
                          degan yagona ishorani berolmasdi: kromkachi 2 metrdan
                          qarab qaysi qator tugaganini darrov ajrata olmasdi.
                          Tugamagan qatorda chiplar qoladi — u yerda qaysi nusxa
                          nechta tomondan o'tgani muhim. */}
                      {finished ? (
                        <span className="rounded-md bg-green-600 px-2.5 py-1 text-sm font-bold text-white">
                          ✓ Bajarildi
                        </span>
                      ) : (
                        <div className="flex flex-wrap items-center justify-end gap-1.5">
                          {p.instances.map((i) => (
                            <span
                              key={i.instance_id}
                              title={i.qr_text}
                              className={cn(
                                "num rounded-md px-2.5 py-1 text-lg font-black",
                                i.done >= p.sides
                                  ? "bg-green-600 text-white"
                                  : i.done > 0
                                    ? "bg-amber-100 text-amber-700"
                                    : "bg-muted text-muted-foreground",
                              )}
                            >
                              {p.instances.length > 1 && (
                                <span className="mr-1 text-xs font-bold opacity-70">
                                  №{i.instance_no}
                                </span>
                              )}
                              {i.done >= p.sides
                                ? "✓"
                                : oval
                                  ? "–"
                                  : `${i.done}/${p.sides}`}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
              {!leftParts.length && (
                <tr>
                  <td
                    colSpan={5}
                    className="h-32 text-center text-muted-foreground"
                  >
                    Arradan kelgan detal yo'q
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
