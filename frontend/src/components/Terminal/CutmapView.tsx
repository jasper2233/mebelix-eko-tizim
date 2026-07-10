// ARRA kesish xaritasi (TZ 7.1.7) — GibSaw uslubidagi ekran: materiallar jadvali,
// list kartochkalari, to'liq list SVG (detallar, kesim chiziqlari, teshiklar overlay),
// detal kartochkasi (katta QR + YORLIQ CHOP ETISH). GibCut litsenziyasi o'rnini bosadi.

import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Printer,
  RotateCw,
} from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useEffect, useMemo, useRef, useState } from "react"
import { renderToStaticMarkup } from "react-dom/server"

import { OpenAPI, OrdersService, TerminalService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

/* eslint-disable @typescript-eslint/no-explicit-any */
type SheetPart = any
type Sheet = any
type Material = any

const getCutmapQueryOptions = (orderId: number, admin: boolean) =>
  queryOptions({
    queryKey: [admin ? "admin" : "terminal", "cutmap", orderId],
    queryFn: () =>
      admin
        ? OrdersService.readOrderCutmap({ orderId })
        : TerminalService.readTerminalCutmap({ orderId }),
    refetchInterval: 60_000,
  })

// Nom bo'yicha barqaror rang (TZ 7.1.7) — hue hash, past to'yinganlik
function partColor(name: string): string {
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 360
  return `hsl(${hash} 45% 88%)`
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`)
}

/** Barcha kesish xaritalarini chop etish: har xarita tepasida
 * "Material nomi | №1 — 2750 × 1830 mm × 2 list" sarlavha, har list o'z sahifasida. */
function printAllMaps(
  orderNumber: string,
  materials: Material[],
  holes: Record<string, any>,
  instancesByCell: Map<string, any[]>,
) {
  const w = window.open("", "_blank", "width=1000,height=800")
  if (!w) return
  const blocks = materials
    .flatMap((m: Material) =>
      m.sheets.map(
        (s: Sheet) => `
        <section>
          <h2>${escapeHtml(m.name)} | №${s.no} — ${s.L} × ${s.W} mm × ${s.mult || 1} list</h2>
          ${renderToStaticMarkup(
            <SheetSvg
              sheet={s}
              holes={holes}
              instancesByCell={instancesByCell}
              onSelect={() => {}}
              selectedCell={null}
            />,
          )}
        </section>`,
      ),
    )
    .join("")
  w.document.write(`<!doctype html><html lang="uz"><head><meta charset="utf-8">
    <title>${escapeHtml(orderNumber)} — kesish xaritalari</title>
    <style>
      @page{ size: A4 landscape; margin: 8mm }
      body{font-family:system-ui,sans-serif;color:#000;margin:0}
      section{page-break-after:always;page-break-inside:avoid;padding:4px 8px}
      section:last-child{page-break-after:auto}
      h2{font-size:15px;margin:0 0 4px;border-bottom:2px solid #000;padding-bottom:3px}
      svg{width:100%;height:auto;max-height:180mm;display:block}
    </style></head><body>${blocks}</body></html>`)
  w.document.close()
  w.focus()
  setTimeout(() => w.print(), 300)
}

export function CutmapView({
  orderId,
  onBack,
  admin = false,
  registerPrint,
}: {
  orderId: number
  onBack: () => void
  admin?: boolean
  /** Sahifa tepasidagi "PDF / Chop etish" tugmasi shu funksiyani chaqiradi (barcha xaritalar). */
  registerPrint?: (fn: () => void) => void
}) {
  const { data, isLoading } = useQuery(getCutmapQueryOptions(orderId, admin))
  const [materialIdx, setMaterialIdx] = useState(0)
  const [sheetIdx, setSheetIdx] = useState(0)
  const [selected, setSelected] = useState<SheetPart | null>(null)

  const instancesByCell = useMemo(() => {
    const map = new Map<
      string,
      typeof data extends undefined
        ? never
        : NonNullable<typeof data>["instances"]
    >()
    for (const inst of data?.instances ?? []) {
      if (inst.pattern_no == null) continue
      const key = `${inst.pattern_no}:${inst.cell_index}`
      const list = (map.get(key) as never[] | undefined) ?? []
      map.set(key, [...list, inst] as never)
    }
    return map
  }, [data])

  if (isLoading) return <Skeleton className="h-full w-full" />
  if (!data?.model) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <p className="max-w-md text-muted-foreground">
          Kesish xaritasi mavjud emas — fayl GibLabda optimizatsiya qilinmagan
          (TEMPLATE). Oddiy vazifalar ro'yxatidan foydalaning.
        </p>
        <Button variant="outline" onClick={onBack}>
          <ArrowLeft /> Orqaga
        </Button>
      </div>
    )
  }

  const model = data.model as any
  const materials: Material[] = model.materials ?? []
  const material = materials[materialIdx]
  const sheets: Sheet[] = material?.sheets ?? []
  const sheet = sheets[sheetIdx]
  const holes = (model.holes ?? {}) as Record<string, any>

  const sheetDone = (s: Sheet) => {
    const cells = (s.parts as SheetPart[]).filter((p) => !p.waste)
    if (!cells.length) return false
    return cells.every((p) => {
      const insts =
        (instancesByCell.get(`${s.no}:${p.cell}`) as any[] | undefined) ?? []
      return insts.length > 0 && insts.every((i) => i.done)
    })
  }

  registerPrint?.(() =>
    printAllMaps(data.order_number, materials, holes, instancesByCell as never),
  )

  return (
    <div className="flex h-full flex-col gap-3 lg:flex-row">
      {/* Materiallar + statistika paneli */}
      <div className="w-full shrink-0 space-y-3 lg:w-72">
        <Button variant="outline" size="sm" onClick={onBack}>
          <ArrowLeft /> Vazifalar ro'yxati
        </Button>
        <div className="rounded-xl border bg-card">
          <div className="border-b px-3 py-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Materiallar · {materials.length}
          </div>
          <div className="max-h-48 overflow-y-auto">
            {materials.map((m: Material, i: number) => {
              const done = m.sheets.filter(sheetDone).length
              const allDone = done === m.sheets.length && m.sheets.length > 0
              return (
                <button
                  type="button"
                  key={m.name}
                  onClick={() => {
                    setMaterialIdx(i)
                    setSheetIdx(0)
                  }}
                  className={`flex min-h-12 w-full items-center justify-between px-3 py-2.5 text-left text-base ${
                    i === materialIdx
                      ? "bg-secondary font-semibold"
                      : "hover:bg-muted"
                  } ${allDone ? "text-muted-foreground" : ""}`}
                >
                  <span className="truncate">
                    {allDone && <span className="mr-1 text-green-600">✓</span>}
                    {m.name}
                  </span>
                  <span className="num ml-2 shrink-0 text-xs text-muted-foreground">
                    {done}/{m.sheets.length}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
        {material && (
          <div className="num grid grid-cols-3 gap-px overflow-hidden rounded-xl border bg-border text-center text-xs">
            <Stat
              label="KK"
              value={(() => {
                const tot = sheets.reduce(
                  (a: number, s: Sheet) => a + (s.mult || 1),
                  0,
                )
                const dn = sheets
                  .filter(sheetDone)
                  .reduce((a: number, s: Sheet) => a + (s.mult || 1), 0)
                return `${tot}−${dn}=${tot - dn}`
              })()}
              hint="Listlar: jami − bajarilgan = qolgan"
            />
            <Stat
              label="KD"
              value={(() => {
                const tot = Number(material.kd) || 0
                const dn = sheets.reduce(
                  (a: number, s: Sheet) =>
                    a +
                    (s.parts as SheetPart[])
                      .filter((p) => !p.waste)
                      .reduce(
                        (b, p) =>
                          b +
                          (
                            (instancesByCell.get(
                              `${s.no}:${p.cell}`,
                            ) as any[]) ?? []
                          ).filter((i) => i.done).length,
                        0,
                      ),
                  0,
                )
                return `${tot}−${dn}=${tot - dn}`
              })()}
              hint="Detallar: jami − bajarilgan = qolgan"
            />
            <Stat label="KO" value={material.ko} hint="Atxot" />
            <Stat
              label="DR"
              value={material.dr?.toFixed?.(1) ?? material.dr}
              hint="Rez, m"
            />
            <Stat label="KR" value={material.kr} hint="Rezlar" />
            <Stat
              label="PZ"
              value={
                material.fill ? `${(material.fill * 100).toFixed(1)}%` : "—"
              }
              hint="To'ldirish"
            />
            <Stat
              label="TP"
              value={`${material.kerf ?? "—"}`}
              hint="Arra qalinligi, mm"
            />
            <Stat
              label="TD"
              value={`${material.trimL ?? "—"}`}
              hint="Tirim uzunlik, mm"
            />
            <Stat
              label="TSh"
              value={`${material.trimW ?? "—"}`}
              hint="Tirim en, mm"
            />
          </div>
        )}
        {/* Listlar — zich ro'yxat: ko'p listda ham sig'adi, joriy list ajralib turadi */}
        <div className="rounded-xl border bg-card">
          <div className="border-b px-3 py-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Listlar · {sheets.length} karta (
            {sheets.reduce((a: number, s: Sheet) => a + (s.mult || 1), 0)} dona)
          </div>
          <div className="max-h-64 overflow-y-auto lg:max-h-[38vh]">
            {sheets.map((s: Sheet, i: number) => {
              const done = sheetDone(s)
              return (
                <button
                  type="button"
                  key={s.no}
                  onClick={() => setSheetIdx(i)}
                  className={`flex min-h-12 w-full items-center gap-2 px-3 py-2 text-left text-base ${
                    i === sheetIdx
                      ? "bg-secondary font-semibold"
                      : "hover:bg-muted"
                  } ${done ? "text-muted-foreground" : ""}`}
                >
                  <span className="num w-9 shrink-0 font-bold">№{s.no}</span>
                  <span className="num flex-1">
                    {s.L}×{s.W}
                  </span>
                  {(s.mult || 1) > 1 && (
                    <span className="num rounded bg-primary/10 px-1.5 text-xs font-bold text-primary">
                      ×{s.mult}
                    </span>
                  )}
                  {done && <span className="text-green-600">✓</span>}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* To'liq list ko'rinishi */}
      <div className="flex min-h-0 flex-1 flex-col rounded-xl border bg-card p-3">
        {sheet ? (
          <>
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="text-sm font-bold">
                №{sheet.no} —{" "}
                <span className="num">
                  {sheet.L} × {sheet.W} mm
                </span>
                <span className="num ml-2 rounded bg-secondary px-1.5 py-0.5 text-xs">
                  × {sheet.mult} list
                </span>
              </div>
              <div className="flex gap-1.5">
                <Button
                  variant="outline"
                  className="size-12 [&_svg]:size-6"
                  disabled={sheetIdx === 0}
                  onClick={() => setSheetIdx(sheetIdx - 1)}
                >
                  <ChevronLeft />
                </Button>
                <Button
                  variant="outline"
                  className="size-12 [&_svg]:size-6"
                  disabled={sheetIdx >= sheets.length - 1}
                  onClick={() => setSheetIdx(sheetIdx + 1)}
                >
                  <ChevronRight />
                </Button>
              </div>
            </div>
            <div className="min-h-0 flex-1">
              <SheetSvg
                sheet={sheet}
                holes={holes}
                instancesByCell={instancesByCell as never}
                onSelect={setSelected}
                selectedCell={selected?.cell ?? null}
              />
            </div>
          </>
        ) : (
          <p className="m-auto text-muted-foreground">List tanlanmagan</p>
        )}
      </div>

      <PartCard
        part={selected}
        sheetNo={sheet?.no}
        instancesByCell={instancesByCell as never}
        onClose={() => setSelected(null)}
        admin={admin}
        holes={holes}
      />
    </div>
  )
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string
  value: unknown
  hint: string
}) {
  return (
    <div className="bg-card p-2" title={hint}>
      <div className="text-[10px] font-bold text-muted-foreground">{label}</div>
      <div className="text-sm font-bold">{String(value ?? "—")}</div>
    </div>
  )
}

// --- GibSaw render qoidalari (GibLabViewer'dan portlangan, foto-tekshirilgan) ---

const HALO = {
  stroke: "#fff",
  strokeWidth: 6,
  strokeLinejoin: "round" as const,
  style: { paintOrder: "stroke" as const },
}

/** Teshik koordinatasi detal lokal (l×w) o'qidan katakka: rot = o'q almashinuvi, OYNASIZ. */
function holeXY(
  p: SheetPart,
  H: any,
  bx: number,
  by: number,
): [number, number] {
  const cx = p.rot ? p.x + by * (p.w / H.w) : p.x + bx * (p.w / H.l)
  const cy = p.rot ? p.y + bx * (p.h / H.l) : p.y + by * (p.h / H.w)
  return [cx, cy]
}

/** Qirra teshigi lokal nuqtasi: side chetida, pos shu chet bo'ylab. */
function edgeLocalXY(H: any, side: string, pos: number): [number, number] {
  if (side === "t") return [pos, 0]
  if (side === "b") return [pos, H.w]
  if (side === "l") return [0, pos]
  return [H.l, pos]
}

/** Qirra teshigi: eng yaqin chetdan ichkariga to'rtburchak, uzunlik = burg'u chuqurligi. */
function edgeBoreRect(
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

function SheetSvg({
  sheet,
  holes,
  instancesByCell,
  onSelect,
  selectedCell,
}: {
  sheet: Sheet
  holes: Record<string, any>
  instancesByCell: Map<string, any[]>
  onSelect: (part: SheetPart) => void
  selectedCell: number | null
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

  const base = { x: -PAD, y: -PAD, w: L + 2 * PAD, h: W + 2 * PAD }

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

  // g'ildirak zoom kursor nuqtasiga (native listener — passive:false kerak)
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const cur = svg.viewBox.baseVal
      const pt = svgPoint(e.clientX, e.clientY)
      if (!pt) return
      const f = e.deltaY < 0 ? 1 / 1.25 : 1.25
      const nw = Math.min(base.w, Math.max(base.w / 14, cur.width * f))
      const nh = nw * (base.h / base.w)
      applyVb(
        pt.x - (pt.x - cur.x) * (nw / cur.width),
        pt.y - (pt.y - cur.y) * (nh / cur.height),
        nw,
        nh,
      )
    }
    svg.addEventListener("wheel", onWheel, { passive: false })
    return () => svg.removeEventListener("wheel", onWheel)
  })

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    ptsRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    svgRef.current?.setPointerCapture(e.pointerId)
    if (ptsRef.current.size === 2) {
      panRef.current = null
      const [a, c] = [...ptsRef.current.values()]
      pinchRef.current = Math.hypot(a.x - c.x, a.y - c.y)
    } else if (vb) {
      panRef.current = { x: e.clientX, y: e.clientY, vx: vb.x, vy: vb.y }
    }
  }
  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (ptsRef.current.has(e.pointerId))
      ptsRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    const svg = svgRef.current
    if (!svg) return
    if (ptsRef.current.size === 2 && pinchRef.current) {
      const [a, c] = [...ptsRef.current.values()]
      const d2 = Math.hypot(a.x - c.x, a.y - c.y)
      if (d2 < 20) return
      const f = pinchRef.current / d2
      pinchRef.current = d2
      const cur = svg.viewBox.baseVal
      const mid = svgPoint((a.x + c.x) / 2, (a.y + c.y) / 2)
      if (!mid) return
      const nw = Math.min(base.w, Math.max(base.w / 14, cur.width * f))
      const nh = nw * (base.h / base.w)
      applyVb(
        mid.x - (mid.x - cur.x) * (nw / cur.width),
        mid.y - (mid.y - cur.y) * (nh / cur.height),
        nw,
        nh,
      )
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
    ptsRef.current.delete(e.pointerId)
    if (ptsRef.current.size < 2) pinchRef.current = null
    if (!ptsRef.current.size) panRef.current = null
  }

  // Yorliqlar hamma narsadan KEYIN chiziladi (teshik/tekstura ortida qolmasin), halo bilan
  const labels: React.ReactNode[] = []

  const partNodes = (sheet.parts as SheetPart[]).map((p) => {
    const insts = instancesByCell.get(`${sheet.no}:${p.cell}`) ?? []
    const doneCount = insts.filter((i) => i.done).length
    const allDone = !p.waste && insts.length > 0 && doneCount === insts.length
    const selected = selectedCell === p.cell
    const H = holes[String(p.id)]
    const fill = p.waste
      ? "url(#zebra)"
      : selected
        ? "#ff7800"
        : partColor(p.name)

    if (!p.waste) {
      const wv = p.w
      const hv = p.h
      const cx = p.x + wv / 2
      const cy = p.y + hv / 2
      const eTop = (p.eH ?? []).filter(Boolean).join("")
      const eLeft = (p.eW ?? []).filter(Boolean).join("")
      // o'lcham shrifti deyarli doimiy (GibSaw pattrenPartDim), faqat tor detalda kichrayadi
      const dW = Math.max(
        12,
        Math.min(
          28,
          hv * 0.28,
          (wv * 0.9) / Math.max(3, `${wv}${eTop}`.length * 0.6),
        ),
      )
      const dH = Math.max(
        12,
        Math.min(
          28,
          wv * 0.28,
          (hv * 0.9) / Math.max(3, `${hv}${eLeft}`.length * 0.6),
        ),
      )
      const oneLine = hv < 3.6 * dW // yupqa strip: uzunlik o'lchami pastki-chap burchakda
      const showW = wv > 16
      const showH = hv > 16
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
      let fsN = Math.min(
        shortA * 0.55,
        (longA * 0.72) / Math.max(1, label.length * 0.52),
        110,
      )
      let shown = label
      if (oneLine) fsN = Math.min(fsN, dW * 1.3)
      if (fsN < 9) {
        shown = `${p.num ?? p.id}`
        fsN = Math.min(
          shortA * 0.7,
          (longA * 0.7) / Math.max(1, shown.length * 0.62),
          40,
        )
        if (fsN < 6) shown = ""
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
      if (showW && oneLine)
        labels.push(
          <text
            key={`w${p.cell}`}
            x={p.x + leftB + 6}
            y={p.y + hv - dW * 0.7}
            fontSize={dW}
            fill="#333"
            {...HALO}
          >
            {wv}
            {eTop ? ` ${eTop}` : ""}
          </text>,
        )
      else if (showW)
        labels.push(
          <text
            key={`w${p.cell}`}
            x={cx}
            y={p.y + dW * 0.85}
            fontSize={dW}
            fill="#333"
            textAnchor="middle"
            {...HALO}
          >
            {wv}
            {eTop ? ` ${eTop}` : ""}
          </text>,
        )
      if (showH)
        labels.push(
          <text
            key={`h${p.cell}`}
            x={p.x + dH * 0.85}
            y={cy}
            fontSize={dH}
            fill="#333"
            textAnchor="middle"
            transform={`rotate(-90 ${p.x + dH * 0.85} ${cy})`}
            {...HALO}
          >
            {hv}
            {eLeft ? ` ${eLeft}` : ""}
          </text>,
        )
      if (shown)
        labels.push(
          <text
            key={`n${p.cell}`}
            x={cx}
            y={cy}
            fontSize={fsN}
            fill="#111"
            fontWeight="700"
            textAnchor="middle"
            dominantBaseline="middle"
            transform={vert ? `rotate(-90 ${cx} ${cy})` : undefined}
            {...HALO}
          >
            {shown}
          </text>,
        )
      if (allDone) {
        const fs = Math.max(34, Math.min(80, Math.min(wv, hv) / 3))
        labels.push(
          <text
            key={`d${p.cell}`}
            x={p.x + wv - fs * 0.6}
            y={p.y + fs * 0.85}
            fontSize={fs}
            fill="#33aa33"
            fontWeight="700"
          >
            ✓
          </text>,
        )
      }
    }

    return (
      // biome-ignore lint/a11y/noStaticElementInteractions: SVG katakcha — 17" touch target (TZ 7.1.7)
      <g
        key={p.cell}
        onClick={() => !p.waste && onSelect(p)}
        className={p.waste ? undefined : "cursor-pointer"}
        opacity={allDone ? 0.55 : 1}
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
        {/* yuza teshiklari — haqiqiy masshtab: katta sverlo katta doira (GibSaw) */}
        {!p.waste &&
          H?.bores?.map((b: any, i: number) => {
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
          H?.edge?.map((b: any, i: number) => {
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
  const dimNodes = ((sheet.dims as any[]) ?? []).map((dm, i) => {
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

  return (
    <svg
      ref={svgRef}
      viewBox={
        vb
          ? `${vb.x} ${vb.y} ${vb.w} ${vb.h}`
          : `${base.x} ${base.y} ${base.w} ${base.h}`
      }
      className="h-full w-full touch-none"
      preserveAspectRatio="xMidYMid meet"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerEnd}
      onPointerCancel={onPointerEnd}
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
      {(sheet.cuts as any[]).map((c, i) => (
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
      <g pointerEvents="none">{labels}</g>
    </svg>
  )
}

/** Tanlangan detal mini-chizmasi: o'lcham strelkalari + teshiklar (GibSaw «Чертеж детали»). */
function PartPreview({
  part,
  holes,
}: {
  part: SheetPart
  holes: Record<string, any>
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
  const local = { ...part, x: ox, y: oy, w: rw, h: rh } as SheetPart
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
      {H?.bores?.map((b: any, i: number) => {
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
      {H?.edge?.map((b: any, i: number) => {
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

function PartCard({
  part,
  sheetNo,
  instancesByCell,
  onClose,
  admin = false,
  holes,
}: {
  part: SheetPart | null
  sheetNo?: number
  instancesByCell: Map<string, any[]>
  onClose: () => void
  admin?: boolean
  holes: Record<string, any>
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const printMutation = useMutation({
    mutationFn: (instanceId: number) =>
      TerminalService.printInstanceLabel({ instanceId }),
    onSuccess: (r) => showSuccessToast(r.message),
    onError: handleError(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["terminal", "cutmap"] }),
  })

  if (!part || part.waste) return null
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
              <div className="num mt-1 text-center text-[10px] text-muted-foreground">
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
            <div>
              Kromka:{" "}
              {[part.eW?.[0], part.eW?.[1], part.eH?.[0], part.eH?.[1]]
                .filter(Boolean)
                .join(", ") || "yo'q"}
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
                {inst.done && (
                  <span className="font-bold text-green-700">✓ kesildi</span>
                )}
              </span>
              {!admin && (
                <LoadingButton
                  className="h-12 px-4 text-base font-bold"
                  loading={printMutation.isPending}
                  onClick={() => {
                    // PNG yangi tabda — brauzerdan istalgan printerga chop etiladi;
                    // parallel ravishda GoDEX navbatiga ham yuboriladi (bridge ulangan bo'lsa)
                    window.open(
                      `${OpenAPI.BASE}/api/v1/terminal/labels/${inst.instance_id}.png`,
                      "_blank",
                    )
                    printMutation.mutate(inst.instance_id)
                  }}
                >
                  <Printer /> YORLIQ CHOP ETISH
                </LoadingButton>
              )}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
