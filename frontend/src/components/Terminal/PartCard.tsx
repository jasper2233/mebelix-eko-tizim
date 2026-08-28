// Tanlangan detal kartochkasi: katta QR, mini chizma (kromka + teshiklar) va
// chekni bekor qilish. Kesish xaritasidan ALOHIDA fayl — CutmapView holatiga
// tegmaydi, faqat prop oladi.

import { RotateCw } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"

import type { CutmapHole, CutmapInstanceState } from "@/client"
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
}: {
  part: SheetPart
  holes: Record<string, CutmapHole>
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
  const ty = oy - 13
  const lx = ox - 13
  return (
    <svg viewBox={`0 0 ${boxW} ${boxH}`} className="block h-auto w-full">
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
  if (part.waste) {
    return (
      <Dialog open={!!part} onOpenChange={(v) => !v && onClose()}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              Qoldiq — {Math.round(part.w)} × {Math.round(part.h)} mm
            </DialogTitle>
          </DialogHeader>
          <div className="rounded-lg border bg-white p-2">
            <PartPreview part={part} holes={holes} />
          </div>
          {wasteItem ? (
            <div className="flex items-start gap-4">
              <div className="shrink-0 rounded-lg border p-2">
                <QRCodeSVG value={wasteItem.qr_text} size={170} />
                <div className="num mt-1 text-center text-2xs text-muted-foreground">
                  {wasteItem.qr_text}
                </div>
              </div>
              <div className="num space-y-1 text-sm">
                <div>
                  O'lcham:{" "}
                  <b>
                    {Math.round(part.w)} × {Math.round(part.h)} mm
                  </b>
                </div>
                <div>
                  Chek:{" "}
                  {wasteItem.label_printed_at ? (
                    <b className="text-green-700">✓ chiqarilgan</b>
                  ) : (
                    <b>chiqarilmagan</b>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground">
              Bu qoldiq ro'yxatga olinmagan (eski yuklama) — project faylni
              qayta yuklang.
            </p>
          )}
          {wasteItem?.label_printed_at && onCancelWaste && (
            <LoadingButton
              variant="destructive"
              className="h-12 w-full px-4 text-base font-bold"
              loading={wasteCancelling}
              onClick={() => onCancelWaste(wasteItem.id)}
            >
              Chekni bekor qilish
            </LoadingButton>
          )}
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
  const insts = instancesByCell.get(`${sheetNo}:${part.cell}`) ?? []
  const next = insts.find((i) => !i.done) ?? insts[0]

  return (
    <Dialog open={!!part} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            №{part.num} — {part.name}{" "}
            {part.rot && <RotateCw className="inline size-4" />}
          </DialogTitle>
        </DialogHeader>
        <div className="rounded-lg border bg-white p-2">
          <PartPreview part={part} holes={holes} />
        </div>
        <div className="flex items-start gap-4">
          {next && (
            <div className="shrink-0 rounded-lg border p-2">
              <QRCodeSVG value={next.qr_text} size={170} />
              <div className="num mt-1 text-center text-2xs text-muted-foreground">
                {next.qr_text}
              </div>
            </div>
          )}
          <div className="num space-y-1 text-sm">
            <div>
              O'lcham:{" "}
              <b>
                {part.w} × {part.h} mm
              </b>
            </div>
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
            <div>
              Yorliq raqami: <b>№{part.num}</b>
            </div>
          </div>
        </div>
        <div className="space-y-1.5">
          {insts.map((inst) => (
            <div
              key={inst.instance_id}
              className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm"
            >
              <span className="num">
                {inst.qr_text}{" "}
                {inst.done ? (
                  <span className="font-bold text-green-700">✓ kesildi</span>
                ) : inst.label_printed_at ? (
                  <span className="font-bold text-green-600">
                    ✓ chek chiqarilgan
                  </span>
                ) : null}
              </span>
              {/* Texnolog xato chekni shu yerdan tuzatadi — proyekt ARRA
                  ro'yxatidan tushib bo'lgach arrachi xaritani ocholmaydi.
                  Arrachi ham SHU tugmadan foydalanadi (kartochka ikki marta
                  bosishda ochiladi) — faqat unda tasdiq oynasi orqali. */}
              {inst.label_printed_at && (
                <LoadingButton
                  variant="destructive"
                  // Qoldiq kartochkasidagi bekor qilish bilan BIR XIL balandlik:
                  // qo'lqopdagi barmoq uchun `sm` (32px) juda kichik edi va bir
                  // xil amal ikki kartochkada ikki xil o'lchamda turardi.
                  className="h-12 px-4 text-base font-bold"
                  loading={cancelMutation.isPending}
                  onClick={() =>
                    onCancelRequest
                      ? onCancelRequest(inst)
                      : cancelMutation.mutate(inst.instance_id)
                  }
                >
                  Chekni bekor qilish
                </LoadingButton>
              )}
            </div>
          ))}
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
