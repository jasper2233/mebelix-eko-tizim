// GibSaw uslubidagi to'liq list SVG renderi (GibLabViewer'dan portlangan,
// foto-tekshirilgan): detallar, kesim chiziqlari, teshiklar, dims zanjiri,
// zoom/pan/swipe. CutmapView va print oqimi shu komponentni ishlatadi.

import { useEffect, useRef, useState } from "react"

/* eslint-disable @typescript-eslint/no-explicit-any */
type SheetPart = any
type Sheet = any

// Barcha detallar bir xil to'q apelsin; tanlangani moviy bo'lib ajraladi.
// Xarita paneli kulrang (oq emas) — yorug' sexda ko'z qamashtirmaydi, detallar ajralib turadi
const PART_FILL = "#e88b00"
const PART_SELECTED = "#2596be"

// --- GibSaw render qoidalari (GibLabViewer'dan portlangan, foto-tekshirilgan) ---

// O'lcham/nom yozuvlari toza qora, oq halo'siz (to'q apelsin fonda halo shart emas)
const HALO = {}

/** Teshik koordinatasi detal lokal (l×w) o'qidan katakka: rot = o'q almashinuvi, OYNASIZ. */
export function holeXY(
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
export function edgeLocalXY(
  H: any,
  side: string,
  pos: number,
): [number, number] {
  if (side === "t") return [pos, 0]
  if (side === "b") return [pos, H.w]
  if (side === "l") return [0, pos]
  return [H.l, pos]
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
  selectedCell,
  thumbnail = false,
  registerZoom,
  onSwipe,
}: {
  sheet: Sheet
  holes: Record<string, any>
  instancesByCell: Map<string, any[]>
  onSelect: (part: SheetPart) => void
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

  // g'ildirak zoom kursor nuqtasiga (native listener — passive:false kerak)
  useEffect(() => {
    if (thumbnail) return
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
    // ATAYIN capture yo'q: setPointerCapture keyingi click'ni SVG'ga retarget
    // qilib, detal <g> onClick'ini o'ldiradi (tanlash ishlamay qoladi)
    ptsRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (ptsRef.current.size === 2) {
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
    if (!cur) return
    const nw = Math.min(base.w, Math.max(base.w / 14, cur.width * f))
    const nh = nw * (base.h / base.w)
    applyVb(
      cur.x + cur.width / 2 - nw / 2,
      cur.y + cur.height / 2 - nh / 2,
      nw,
      nh,
    )
  }
  registerZoom?.({
    zin: () => zoomBy(1 / 1.5),
    zout: () => zoomBy(1.5),
    reset: () => setVb(null),
  })

  // Yorliqlar hamma narsadan KEYIN chiziladi (teshik/tekstura ortida qolmasin), halo bilan
  const labels: React.ReactNode[] = []

  const partNodes = (sheet.parts as SheetPart[]).map((p) => {
    const insts = instancesByCell.get(`${sheet.no}:${p.cell}`) ?? []
    const doneCount = insts.filter((i) => i.done).length
    const allDone = !p.waste && insts.length > 0 && doneCount === insts.length
    const selected = selectedCell === p.cell
    const H = holes[String(p.id)]
    const fill = p.waste ? "url(#zebra)" : selected ? PART_SELECTED : PART_FILL

    if (!p.waste) {
      const wv = p.w
      const hv = p.h
      const cx = p.x + wv / 2
      const cy = p.y + hv / 2
      const eTop = (p.eH ?? []).filter(Boolean).join("")
      const eLeft = (p.eW ?? []).filter(Boolean).join("")
      // o'lcham shrifti deyarli doimiy (GibSaw pattrenPartDim), faqat tor detalda kichrayadi.
      // 17" da to'liq ko'rinishda o'qilsin: cap 42 (~ekranda 18px); kichik detalda formula
      // o'zi qisqartiradi — u yerda yechim zoom yoki detal kartochkasi
      const dW = Math.max(
        16,
        Math.min(
          42,
          hv * 0.28,
          (wv * 0.9) / Math.max(3, `${wv}${eTop}`.length * 0.6),
        ),
      )
      const dH = Math.max(
        16,
        Math.min(
          42,
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
            {...HALO}
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
            {...HALO}
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
            {...HALO}
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
            {...HALO}
          >
            {shown}
          </text>,
        )
      }
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

  return svgEl
}
