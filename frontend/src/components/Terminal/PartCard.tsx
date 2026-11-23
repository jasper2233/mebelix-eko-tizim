// Tanlangan detal kartochkasi: katta QR, mini chizma (kromka + teshiklar) va
// chekni bekor qilish. Kesish xaritasidan ALOHIDA fayl — CutmapView holatiga
// tegmaydi, faqat prop oladi.

import { RotateCw } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"

import type { CutmapHole, CutmapInstanceState, CutmapMachining } from "@/client"
import { Serial } from "@/components/Terminal/Serial"
import {
  edgeBoreRect,
  edgeLocalXY,
  holeXY,
  type SheetPart,
} from "@/components/Terminal/SheetSvg"
import { useCancelLabel } from "@/components/Terminal/usePrintLabel"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"

/** Tanlangan detal mini-chizmasi: o'lcham strelkalari + teshiklar (GibSaw «Чертеж детали»).
 *  KROMKA luppasi ham shuni chizadi (`KromkaView`) — kromkachi qo'lidagi detalni
 *  ayni shu chizmaga moslaydi, ya'ni ikkala joyda BIR XIL bo'lishi shart. */
export function PartPreview({
  part,
  holes,
  ishlov,
}: {
  part: SheetPart
  holes: Record<string, CutmapHole>
  ishlov?: CutmapMachining
}) {
  const w = part.w
  const h = part.h
  const boxW = 276
  const boxH = 190
  const m = 34
  const scale = Math.min((boxW - 2 * m) / w, (boxH - 2 * m) / h)
  const rw = w * scale
  const rh = h * scale
  const ox = (boxW - rw) / 2
  const oy = (boxH - rh) / 2
  const H = holes[String(part.id)]
  const local: SheetPart = { ...part, x: ox, y: oy, w: rw, h: rh }
  // Ishlov yo'llari detal koordinatasida (x uzunlik, y en) — teshik bilan BIR XIL
  // fazoda, shuning uchun `holeXY` ishlatiladi: u burilgan katakni ham to'g'ri
  // o'giradi. O'lchamni `ishlov` o'zi olib keladi, chunki teshigi yo'q detalda
  // `H` umuman bo'lmaydi.
  const yol = (yollar: number[][][] | undefined) =>
    (yollar ?? []).map((y) =>
      y
        .map((n) =>
          holeXY(local, { l: ishlov?.l, w: ishlov?.w }, n[0], n[1]).join(","),
        )
        .join(" "),
    )
  // FIGURALI detal (MX paketi `parts[].figure`): arra to'rtburchak kesadi, figura
  // keyin kesiladi — olib tashlanadigan qism shtrix, yangi qirra chiziq, kromkali
  // yangi qirra qalin chiziq. Chek (`labels.py: _figura_chiz`) bilan bir xil til.
  const fig = ishlov?.figure
  const figXY = (x: number, y: number) =>
    holeXY(local, { l: fig?.size?.[0], w: fig?.size?.[1] }, x, y)
  const figRings = (fig?.removed ?? [])
    .filter((h) => h.length >= 3)
    .map((h) => h.map((q) => figXY(q[0], q[1])))
  const figD = figRings
    .map((h) => `M ${h.map((q) => q.join(" ")).join(" L ")} Z`)
    .join(" ")
  // evenodd: nuqta nechta halqa ichida — toq bo'lsa olib tashlanadi
  const olibTashlangan = (x: number, y: number) =>
    figRings.reduce((n, h) => {
      let ichida = false
      for (let i = 0, j = h.length - 1; i < h.length; j = i++) {
        const [xi, yi] = h[i]
        const [xj, yj] = h[j]
        if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)
          ichida = !ichida
      }
      return n + (ichida ? 1 : 0)
    }, 0) %
      2 ===
    1
  // Tomonning kesilgandan keyin QOLADIGAN qismlari (0..1 ulushda): to'g'ri kromka
  // chizig'i faqat shu yerda — yoy / burchak kesigi ustidan emas (chek bilan bir xil)
  const tomonOraliq = (
    nuqta: (k: number) => [number, number],
  ): [number, number][] => {
    if (figRings.length === 0) return [[0, 1]]
    const n = 240
    const out: [number, number][] = []
    let bosh: number | null = null
    for (let i = 0; i <= n; i++) {
      const k = i / n
      const qoladi = !olibTashlangan(...nuqta(k))
      if (qoladi && bosh === null) bosh = k
      if ((!qoladi || i === n) && bosh !== null) {
        if (k - bosh > 0.01) out.push([bosh, k])
        bosh = null
      }
    }
    return out
  }
  // Bir xil kromkali ketma-ket qirralar — bitta zanjir, harf bitta (o'rtasida)
  const zanjirlar: { sym: string; pts: [number, number][] }[] = []
  {
    let oxirgi: number[] | null = null
    for (const c of fig?.cuts ?? []) {
      const yo = (c.path ?? []).map((q) => figXY(q[0], q[1]))
      if (yo.length < 2 || !c.edge) {
        oxirgi = null
        continue
      }
      const sym = c.edge.symbol ?? ""
      const b0 = c.path?.[0] ?? [0, 0]
      const z = zanjirlar[zanjirlar.length - 1]
      if (
        z &&
        oxirgi &&
        z.sym === sym &&
        Math.abs(b0[0] - oxirgi[0]) + Math.abs(b0[1] - oxirgi[1]) < 0.5
      )
        z.pts.push(...yo.slice(1))
      else zanjirlar.push({ sym, pts: yo })
      oxirgi = c.path?.[c.path.length - 1] ?? null
    }
  }
  const ty = oy - 13
  const lx = ox - 13
  // Balandlik chegarasi: chizma dialog kengligiga cho'zilib ~370px olar,
  // dialog (chizma + QR + tugmalar) 17" monoblokning 768px ekraniga sig'may
  // sarlavha kesilardi. 38dvh — 768 da ~290px, dialog ~710px bo'ladi.
  return (
    <svg
      viewBox={`0 0 ${boxW} ${boxH}`}
      className="block h-auto max-h-[38dvh] w-full"
    >
      <title>Detal chizmasi</title>
      <rect
        x={ox}
        y={oy}
        width={rw}
        height={rh}
        fill="#d2d2d2"
        stroke="#242424"
        strokeWidth="1.5"
      />
      {fig && figD && (
        <g>
          <defs>
            <pattern
              id={`shtrix-${part.id}`}
              width="6"
              height="6"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="6" height="6" fill="#fafafa" />
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="6"
                stroke="#444"
                strokeWidth="1.4"
              />
            </pattern>
          </defs>
          <path
            d={figD}
            fill={`url(#shtrix-${part.id})`}
            fillRule="evenodd"
            stroke="none"
          />
          <clipPath id={`olingan-${part.id}`}>
            <path d={figD} clipRule="evenodd" />
          </clipPath>
          {/* kromkali qirra atrofida shtrixsiz bo'shliq — chiziq shtrixga ulanmaydi */}
          <g clipPath={`url(#olingan-${part.id})`}>
            {fig.cuts
              ?.filter((c) => c.edge)
              .map((c, i) => (
                <polyline
                  key={`bo${i}`}
                  points={(c.path ?? [])
                    .map((q) => figXY(q[0], q[1]).join(","))
                    .join(" ")}
                  fill="none"
                  stroke="#fafafa"
                  strokeWidth={12}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              ))}
          </g>
          {/* Kichik kesik (tsokol / burchak kesigi) chizmada 1-2 px bo'lib
              ko'rinmay qoladi — chekdagi kabi aylana bilan belgilanadi */}
          {figRings.map((h, i) => {
            const xs = h.map((q) => q[0])
            const ys = h.map((q) => q[1])
            const w = Math.max(...xs) - Math.min(...xs)
            const hh = Math.max(...ys) - Math.min(...ys)
            if (w >= 10 || hh >= 10) return null
            return (
              <circle
                key={`kk${i}`}
                cx={(Math.max(...xs) + Math.min(...xs)) / 2}
                cy={(Math.max(...ys) + Math.min(...ys)) / 2}
                r={8}
                fill="none"
                stroke="#dc2626"
                strokeWidth="1.5"
              />
            )
          })}
        </g>
      )}
      {fig?.cuts?.map((c, i) => {
        const pts = (c.path ?? [])
          .map((q) => figXY(q[0], q[1]).join(","))
          .join(" ")
        const kromka = !!c.edge
        return (
          <g key={`fc${i}`}>
            <polyline
              points={pts}
              fill="none"
              stroke={kromka ? "#111" : "#242424"}
              strokeWidth={kromka ? 4 : 1.5}
              strokeLinejoin="round"
            />
          </g>
        )
      })}
      {zanjirlar.map((z, i) => {
        if (!z.sym) return null
        const uz = z.pts
          .slice(1)
          .map((q, j) => Math.hypot(q[0] - z.pts[j][0], q[1] - z.pts[j][1]))
        const jami = uz.reduce((a, b) => a + b, 0)
        if (jami < 8) return null // kichik burchak — tomon harfi yetadi
        let [mx, my] = z.pts[Math.floor(z.pts.length / 2)]
        let t0 = 0
        const p0 = z.pts[0]
        const pn = z.pts[z.pts.length - 1]
        const yopiq =
          z.pts.length > 2 &&
          Math.abs(p0[0] - pn[0]) + Math.abs(p0[1] - pn[1]) <= 2
        if (yopiq) {
          // yopiq kontur (oyna) — eng uzun kesmaning chorak nuqtasi (chek bilan bir xil)
          const j = uz.indexOf(Math.max(...uz))
          mx = z.pts[j][0] + (z.pts[j + 1][0] - z.pts[j][0]) / 4
          my = z.pts[j][1] + (z.pts[j + 1][1] - z.pts[j][1]) / 4
        }
        for (let j = 0; j < uz.length && !yopiq; j++) {
          if (t0 + uz[j] >= jami / 2 && uz[j] > 0) {
            const k = (jami / 2 - t0) / uz[j]
            mx = z.pts[j][0] + (z.pts[j + 1][0] - z.pts[j][0]) * k
            my = z.pts[j][1] + (z.pts[j + 1][1] - z.pts[j][1]) * k
            break
          }
          t0 += uz[j]
        }
        const dx = ox + rw / 2 - mx
        const dy = oy + rh / 2 - my
        const n = Math.max(1, Math.hypot(dx, dy))
        // harf detalning qoladigan qismiga — shtrixga tushsa teskari tomonga
        let s = 11
        if (olibTashlangan(mx + (dx / n) * s, my + (dy / n) * s)) s = -11
        return (
          <text
            key={`zh${i}`}
            x={mx + (dx / n) * s}
            y={my + (dy / n) * s}
            fontSize="11"
            fontWeight="700"
            textAnchor="middle"
            dominantBaseline="middle"
          >
            {z.sym}
          </text>
        )
      })}
      {/* KROMKA — chekdagi kabi konturdan tashqarida qalin chiziq.
          Burilish hisobi SHART EMAS: backend `eW`/`eH` ni katak qanday
          joylashganiga qarab allaqachon hal qilgan (`cutmap._edge_markers`),
          ya'ni bu yerda chap/o'ng/tepa/past to'g'ridan-to'g'ri olinadi.
          Pastdagi "chap 400 (A)" yozuvi ham xuddi shu manbadan — chizma bilan
          matn hech qachon ziddiyatga tushmaydi. */}
      {[
        {
          bor: part.eW?.[0],
          x: ox - 5,
          y: oy,
          w: 3,
          h: rh,
          o: tomonOraliq((k) => [ox + 2, oy + rh * k]),
          tik: true,
        },
        {
          bor: part.eW?.[1],
          x: ox + rw + 2,
          y: oy,
          w: 3,
          h: rh,
          o: tomonOraliq((k) => [ox + rw - 2, oy + rh * k]),
          tik: true,
        },
        {
          bor: part.eH?.[0],
          x: ox,
          y: oy - 5,
          w: rw,
          h: 3,
          o: tomonOraliq((k) => [ox + rw * k, oy + 2]),
          tik: false,
        },
        {
          bor: part.eH?.[1],
          x: ox,
          y: oy + rh + 2,
          w: rw,
          h: 3,
          o: tomonOraliq((k) => [ox + rw * k, oy + rh - 2]),
          tik: false,
        },
      ].map((k, i) =>
        k.bor
          ? k.o.map(([a, b], j) => (
              <rect
                key={`k${i}-${j}`}
                x={k.tik ? k.x : k.x + k.w * a}
                y={k.tik ? k.y + k.h * a : k.y}
                width={k.tik ? k.w : k.w * (b - a)}
                height={k.tik ? k.h * (b - a) : k.h}
                fill="#111"
              />
            ))
          : null,
      )}
      {/* Tekstura — xaritadagi varaq bilan bir xil qoida: `rot` bo'lsa tik, aks
          holda yotiq 3 chiziq (uzunlik o'qi bo'ylab). KULRANG va ishlovdan OLDIN:
          qora chiziq ko'k uzuq chiziqning bo'shliqlarini to'ldirib, pazni freza
          qilib ko'rsatardi — chekda aynan shu o'lchab topilgan. */}
      {part.txt &&
        (() => {
          const cx = ox + rw / 2
          const cy = oy + rh / 2
          // Nisbatlar CHEKDAN olingan (`labels.py`: chiziq uzunligi 0.32,
          // oraliq to'rtdan bir) — ishchi qo'lidagi chek bilan yonma-yon
          // solishtiradi. Qat'iy piksel yo'q: karta o'lchami detal nisbatiga
          // qarab o'zgaradi va chiziqlar u bilan birga kichrayadi.
          const uz = (((part.rot ? rh : rw) * 0.32) / 2) | 0
          const or_ = Math.max(3, ((part.rot ? rw : rh) / 4) | 0)
          return [-or_, 0, or_].map((d) => (
            <line
              key={`tx${d}`}
              x1={part.rot ? cx + d : cx - uz}
              y1={part.rot ? cy - uz : cy + d}
              x2={part.rot ? cx + d : cx + uz}
              y2={part.rot ? cy + uz : cy + d}
              stroke="#9ca3af"
              strokeWidth="2"
            />
          ))
        })()}
      {H?.bores?.map((b, i) => {
        const [cx, cy] = holeXY(local, H, b.x, b.y)
        return (
          <circle
            key={`b${i}`}
            cx={cx}
            cy={cy}
            r={Math.max((b.d / 2) * scale, 2.4)}
            fill="#fafafa"
            stroke="#202020"
            strokeWidth="1"
          />
        )
      })}
      {H?.edge?.map((b, i) => {
        const [px, py] = edgeLocalXY(H, b.side, b.pos)
        const [cx, cy] = holeXY(local, H, px, py)
        const r = edgeBoreRect(
          local,
          cx,
          cy,
          Math.max(b.d * scale, 2),
          Math.max((b.dp || 12) * scale, 4),
        )
        return (
          <rect
            key={`e${i}`}
            x={r.x}
            y={r.y}
            width={r.w}
            height={r.h}
            fill="#fafafa"
            stroke="#202020"
            strokeWidth="1"
          />
        )
      })}
      {/* Ishlov — chek eskizidagi bilan bir xil til: paz UZUQ, freza TUTASH.
          Teshiklardan KEYIN, chunki teshik oq to'ldiriladi va chiziqni o'chirardi.
          Detal chegarasida QIRQILADI: asbob kirish yo'li detaldan tashqarida
          bo'lishi normal (x=-30), lekin chizmada u xatodek ko'rinardi. */}
      <clipPath id={`ish-${part.id}`}>
        <rect x={ox} y={oy} width={rw} height={rh} />
      </clipPath>
      <g clipPath={`url(#ish-${part.id})`}>
        {yol(ishlov?.frez_paths).map((pts) => (
          <polyline
            key={`f${pts}`}
            points={pts}
            fill="none"
            stroke="#0369a1"
            strokeWidth="2"
          />
        ))}
        {yol(ishlov?.paz_paths).map((pts) => (
          <polyline
            key={`p${pts}`}
            points={pts}
            fill="none"
            stroke="#0369a1"
            strokeWidth="2"
            strokeDasharray="5 3"
          />
        ))}
      </g>
      <line
        x1={ox}
        y1={ty}
        x2={ox + rw}
        y2={ty}
        stroke="#333"
        strokeWidth="1"
      />
      <path
        d={`M${ox} ${ty}l6 -3M${ox} ${ty}l6 3M${ox + rw} ${ty}l-6 -3M${ox + rw} ${ty}l-6 3`}
        stroke="#333"
        strokeWidth="1"
        fill="none"
      />
      <text
        x={ox + rw / 2}
        y={ty - 5}
        fontSize="14"
        fontWeight="bold"
        textAnchor="middle"
        fill="#111"
      >
        {w}
      </text>
      <line
        x1={lx}
        y1={oy}
        x2={lx}
        y2={oy + rh}
        stroke="#333"
        strokeWidth="1"
      />
      <path
        d={`M${lx} ${oy}l-3 6M${lx} ${oy}l3 6M${lx} ${oy + rh}l-3 -6M${lx} ${oy + rh}l3 -6`}
        stroke="#333"
        strokeWidth="1"
        fill="none"
      />
      <text
        x={lx - 5}
        y={oy + rh / 2}
        fontSize="14"
        fontWeight="bold"
        textAnchor="middle"
        fill="#111"
        transform={`rotate(-90 ${lx - 5} ${oy + rh / 2})`}
      >
        {h}
      </text>
      {part.rot && (
        <text
          x={ox + rw - 4}
          y={oy + 16}
          fontSize="15"
          textAnchor="end"
          fill="#a94b05"
        >
          ⟳
        </text>
      )}
    </svg>
  )
}

export function PartCard({
  part,
  sheetNo,
  instancesByCell,
  onClose,
  holes,
  machining,
  onCancelRequest,
  wasteItem,
  onCancelWaste,
  wasteCancelling = false,
}: {
  part: SheetPart | null
  sheetNo?: number | string
  instancesByCell: Map<string, CutmapInstanceState[]>
  onClose: () => void
  holes: Record<string, CutmapHole>
  /** Paz/freza — `CutmapState.machining`, kalit `part.id` (teshiklar bilan bir xil) */
  machining?: Record<string, CutmapMachining>
  /** QOLDIQ katagi ochilganda — unga mos `waste_item`. Kartochka ATAYLAB
   *  bitta: qoldiq ham detal kabi belgilanadi, chap qatordagi "Chop etish"
   *  bilan chiqariladi va ikki marta bosishda shu kartochkada bekor qilinadi.
   *  Alohida dialog bo'lganda operator bitta xaritada ikki xil qoidani
   *  eslab qolishi kerak edi. */
  wasteItem?: {
    id: number
    qr_text: string
    label_printed_at?: string | null
  } | null
  onCancelWaste?: (wasteId: number) => void
  wasteCancelling?: boolean
  /** Berilsa — bekor qilish TO'G'RIDAN-TO'G'RI bajarilmaydi, chaqiruvchiga
   *  uzatiladi (terminalda tasdiq oynasi ochiladi). Berilmasa — adminning
   *  avvalgi xatti-harakati: darhol bekor qilinadi. */
  onCancelRequest?: (inst: CutmapInstanceState) => void
}) {
  // Kartochka adminda bir marta bosishda, terminalda esa ikki marta bosish
  // yoki uzoq bosishda ochiladi. Chop etish terminalda chap toolbar orqali,
  // shuning uchun bu yerda print mutatsiyasi yo'q.
  const cancelMutation = useCancelLabel()

  if (!part) return null
  // Ro'yxatga olinmagan atxot (atx yo'q) kartochka ochmaydi — unda ko'rsatadigan
  // ham, qiladigan ham narsa yo'q.
  if (part.waste && !part.atx) return null
  // QOLDIQ VA DETAL BIR XIL KARTOCHKADA. Qoldiqda nusxalar yo'q — uning
  // yagona cheki qatorlar ro'yxatida detal nusxasi bilan BIR XIL shaklda
  // ko'rsatiladi, ya'ni "chekni bekor qilish" ikkalasida ham ID yonida turadi.
  // Ilgari qoldiq alohida bloк edi: tugma "Yopish" ustida, o'lcham sarlavhada,
  // ID esa umuman yo'q — bitta xaritada ikki xil kartochka.
  const waste = !!part.waste
  const insts = waste
    ? []
    : (instancesByCell.get(`${sheetNo}:${part.cell}`) ?? [])
  // Qoldiq va detal cheki BIR SHAKLGA keltiriladi — pastda yagona render yo'li.
  const cheklar = waste
    ? wasteItem
      ? [
          {
            key: `w${wasteItem.id}`,
            qr: wasteItem.qr_text,
            printed: !!wasteItem.label_printed_at,
            done: false,
            loading: wasteCancelling,
            cancel: onCancelWaste
              ? () => onCancelWaste(wasteItem.id)
              : undefined,
          },
        ]
      : []
    : insts.map((inst) => ({
        key: `i${inst.instance_id}`,
        qr: inst.qr_text,
        printed: !!inst.label_printed_at,
        done: !!inst.done,
        loading: cancelMutation.isPending,
        // Texnolog xato chekni shu yerdan tuzatadi — proyekt ARRA ro'yxatidan
        // tushib bo'lgach arrachi xaritani ocholmaydi. Arrachi ham SHU tugmadan
        // foydalanadi (kartochka ikki marta bosishda ochiladi) — faqat unda
        // tasdiq oynasi orqali.
        cancel: () =>
          onCancelRequest
            ? onCancelRequest(inst)
            : cancelMutation.mutate(inst.instance_id),
      }))
  // HAR KATAK = BITTA JISMONIY DETAL = BITTA CHEK. `count>1` detalning nusxalari
  // xaritada alohida kataklarda turadi, `mult>1` list esa render paytida alohida
  // kartalarga yoyiladi (`CutmapView` `slice(k, k+1)`) — shuning uchun `cheklar`
  // amalda doim bitta. Ro'yxat shakli faqat kutilmagan ma'lumotda ishlaydi:
  // ikkinchi chek yashirilib qolgandan ko'ra ko'rinib tursin.
  const chek = cheklar.find((c) => !c.done) ?? cheklar[0]
  const qr = chek?.qr
  const nomer = waste ? part.atx : part.num
  const ishlov = machining?.[String(part.id)]

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          {/* ID SARLAVHA QATORIDA va kattaroq: kartochkaning eng ko'p
              solishtiriladigan qiymati — chekdagi raqam bilan. Qoldiqda
              yonida QOLDIQ bayrog'i turadi, boshqa hammasi bir xil. */}
          <DialogTitle className="flex items-center gap-2 pr-8">
            <span className="num text-2xl font-black">№{nomer}</span>
            <span className="truncate text-base font-semibold">
              {waste
                ? `${Math.round(part.w)} × ${Math.round(part.h)} mm`
                : part.name}
            </span>
            {waste && (
              <span className="shrink-0 rounded bg-amber-100 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-amber-800">
                Qoldiq
              </span>
            )}
            {part.rot && <RotateCw className="inline size-4 shrink-0" />}
          </DialogTitle>
          {/* CHEK ID SI SARLAVHA OSTIDA — kartochkaning eng ko'p
              solishtiriladigan qiymati: qo'ldagi chekdagi matn bilan. Ilgari u
              QR ostida `text-2xs` kulrang bo'lib, yana bekor qilish qatorida
              takrorlanardi. */}
          {chek && (
            <div className="num flex flex-wrap items-center gap-2 text-left text-base font-bold">
              <Serial code={chek.qr} />
              {chek.done ? (
                <span className="text-green-700">✓ kesildi</span>
              ) : chek.printed ? (
                <span className="text-green-600">✓ chek chiqarilgan</span>
              ) : null}
            </div>
          )}
        </DialogHeader>
        <div className="rounded-lg border bg-white p-2">
          <PartPreview part={part} holes={holes} ishlov={ishlov} />
        </div>
        <div className="flex items-start gap-4">
          {qr && (
            <div className="shrink-0 rounded-lg border p-2">
              <QRCodeSVG value={qr} size={170} />
            </div>
          )}
          <div className="num space-y-1 text-sm">
            <div>
              O'lcham:{" "}
              <b>
                {part.w} × {part.h} mm
              </b>
            </div>
            {/* Qoldiqda kromka ham, yorliq raqami ham yo'q — u material,
                ishlov berilmaydi. */}
            {!waste && (
              <>
                {/* Kromka QAYSI TOMONDA — belgi o'zi yetarli emas edi. Tomon
                nomlari yonidagi eskiz bilan bir xil yo'nalishda: eW = chap/o'ng
                (vertikal qirralar, uzunligi = balandlik), eH = tepa/past
                (gorizontal, uzunligi = kenglik). O'lcham ham yoziladi —
                kromkachi qaysi qirrani lentalashini shundan biladi. */}
                <div>
                  Kromka: {(() => {
                    const tomonlar = [
                      { nom: "chap", sym: part.eW?.[0], boyi: part.h },
                      { nom: "o'ng", sym: part.eW?.[1], boyi: part.h },
                      { nom: "tepa", sym: part.eH?.[0], boyi: part.w },
                      { nom: "past", sym: part.eH?.[1], boyi: part.w },
                    ].filter((t) => t.sym)
                    if (!tomonlar.length) return <b>yo'q</b>
                    return tomonlar.map((t, i) => (
                      <span key={t.nom}>
                        {i > 0 && " · "}
                        <b>
                          {t.nom} {Math.round(t.boyi)}
                        </b>
                        {t.sym !== "•" && ` (${t.sym})`}
                      </span>
                    ))
                  })()}
                </div>
                {ishlov && (
                  // Tomon NOMI ataylab yozilmaydi: katak burilgan bo'lishi mumkin
                  // (`rot`), ya'ni `l/r/t/b` chizmadagi joyga to'g'ri kelmasligi
                  // mumkin edi. Chizmada esa yo'l o'z joyida turadi.
                  <div>
                    Ishlov:{" "}
                    {[
                      ishlov.paz_paths?.length &&
                        `paz ${ishlov.paz_paths.length} ta`,
                      ishlov.frez_paths?.length &&
                        `freza ${ishlov.frez_paths.length} ta`,
                    ]
                      .filter(Boolean)
                      .join(" · ")}{" "}
                    <span className="text-muted-foreground">
                      — chizmada uzuq = paz, tutash = freza
                    </span>
                  </div>
                )}
              </>
            )}
            {waste && !wasteItem && (
              <div className="text-muted-foreground">
                Bu qoldiq ro'yxatda yo'q — texnolog project faylni qayta
                yuklashi kerak.
              </div>
            )}
          </div>
        </div>
        {/* Bekor qilish TO'LIQ KENGLIKDA: kartochkada bitta chek bo'lgani uchun
            uni siqilgan qatorga tiqishning ma'nosi yo'q — qo'lqopdagi barmoq
            uchun eng katta nishon. */}
        <div className="space-y-1.5">
          {cheklar.map((c) =>
            c.printed && c.cancel ? (
              <LoadingButton
                key={c.key}
                variant="destructive"
                className="h-14 w-full text-lg font-bold"
                loading={c.loading}
                onClick={c.cancel}
              >
                Chekni bekor qilish
                {cheklar.length > 1 && (
                  <Serial code={c.qr} className="ml-2 text-sm font-normal" />
                )}
              </LoadingButton>
            ) : null,
          )}
        </div>
        {/* Radix X 16px — qo'lqopga kichik; katta yopish tugmasi */}
        <Button
          variant="outline"
          className="h-12 w-full text-base font-bold"
          onClick={onClose}
        >
          Yopish
        </Button>
      </DialogContent>
    </Dialog>
  )
}
