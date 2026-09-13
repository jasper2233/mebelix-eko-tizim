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

/** Tanlangan detal mini-chizmasi: o'lcham strelkalari + teshiklar (GibSaw «Чертеж детали»). */
function PartPreview({
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
      {/* KROMKA — chekdagi kabi konturdan tashqarida qalin chiziq.
          Burilish hisobi SHART EMAS: backend `eW`/`eH` ni katak qanday
          joylashganiga qarab allaqachon hal qilgan (`cutmap._edge_markers`),
          ya'ni bu yerda chap/o'ng/tepa/past to'g'ridan-to'g'ri olinadi.
          Pastdagi "chap 400 (A)" yozuvi ham xuddi shu manbadan — chizma bilan
          matn hech qachon ziddiyatga tushmaydi. */}
      {[
        { bor: part.eW?.[0], x: ox - 5, y: oy, w: 3, h: rh },
        { bor: part.eW?.[1], x: ox + rw + 2, y: oy, w: 3, h: rh },
        { bor: part.eH?.[0], x: ox, y: oy - 5, w: rw, h: 3 },
        { bor: part.eH?.[1], x: ox, y: oy + rh + 2, w: rw, h: 3 },
      ].map((k, i) =>
        k.bor ? (
          <rect
            key={`k${i}`}
            x={k.x}
            y={k.y}
            width={k.w}
            height={k.h}
            fill="#111"
          />
        ) : null,
      )}
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
