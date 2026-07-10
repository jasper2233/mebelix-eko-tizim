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
import { useMemo, useState } from "react"

import { OrdersService, TerminalService } from "@/client"
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
function partStroke(name: string): string {
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 360
  return `hsl(${hash} 45% 45%)`
}

export function CutmapView({
  orderId,
  onBack,
  admin = false,
}: {
  orderId: number
  onBack: () => void
  admin?: boolean
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

  return (
    <div className="flex h-full flex-col gap-3 lg:flex-row">
      {/* Materiallar + statistika paneli */}
      <div className="w-full shrink-0 space-y-3 lg:w-72">
        <Button variant="outline" size="sm" onClick={onBack}>
          <ArrowLeft /> Vazifalar ro'yxati
        </Button>
        <div className="rounded-xl border bg-card">
          <div className="border-b px-3 py-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Materiallar
          </div>
          {materials.map((m: Material, i: number) => {
            const done = m.sheets.filter(sheetDone).length
            return (
              <button
                type="button"
                key={m.name}
                onClick={() => {
                  setMaterialIdx(i)
                  setSheetIdx(0)
                }}
                className={`flex w-full items-center justify-between px-3 py-2.5 text-left text-sm ${
                  i === materialIdx
                    ? "bg-secondary font-semibold"
                    : "hover:bg-muted"
                }`}
              >
                <span className="truncate">{m.name}</span>
                <span className="num ml-2 shrink-0 text-xs text-muted-foreground">
                  {done}/{m.sheets.length} list
                </span>
              </button>
            )
          })}
        </div>
        {material && (
          <div className="num grid grid-cols-3 gap-px overflow-hidden rounded-xl border bg-border text-center text-xs">
            <Stat label="KK" value={material.kk} hint="Listlar" />
            <Stat label="KD" value={material.kd} hint="Detallar" />
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
          </div>
        )}
        {/* List kartochkalari */}
        <div className="grid max-h-64 grid-cols-3 gap-2 overflow-y-auto lg:grid-cols-2">
          {sheets.map((s: Sheet, i: number) => (
            <button
              type="button"
              key={s.no}
              onClick={() => setSheetIdx(i)}
              className={`rounded-lg border p-2 text-left text-xs ${
                i === sheetIdx ? "border-primary ring-2 ring-primary/30" : ""
              } ${sheetDone(s) ? "opacity-50" : ""}`}
            >
              <div className="font-bold">
                №{s.no} {sheetDone(s) && "✓"}
              </div>
              <div className="num text-muted-foreground">
                {s.L}×{s.W}
              </div>
              <div className="num font-semibold text-primary">
                × {s.mult} list
              </div>
            </button>
          ))}
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
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  size="icon-sm"
                  disabled={sheetIdx === 0}
                  onClick={() => setSheetIdx(sheetIdx - 1)}
                >
                  <ChevronLeft />
                </Button>
                <Button
                  variant="outline"
                  size="icon-sm"
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

function SheetSvg({
  sheet,
  holes,
  instancesByCell,
  onSelect,
}: {
  sheet: Sheet
  holes: Record<string, any>
  instancesByCell: Map<string, any[]>
  onSelect: (part: SheetPart) => void
}) {
  const { L, W } = sheet
  return (
    <svg
      viewBox={`-8 -8 ${L + 16} ${W + 16}`}
      className="h-full w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      <title>Kesish xaritasi</title>
      <defs>
        <pattern
          id="zebra"
          width="18"
          height="18"
          patternTransform="rotate(45)"
          patternUnits="userSpaceOnUse"
        >
          <rect width="18" height="18" fill="#f1f5f9" />
          <line x1="0" y1="0" x2="0" y2="18" stroke="#cbd5e1" strokeWidth="7" />
        </pattern>
      </defs>
      <rect
        x="0"
        y="0"
        width={L}
        height={W}
        fill="#fafafa"
        stroke="#334155"
        strokeWidth="2"
      />
      {(sheet.parts as SheetPart[]).map((p) => {
        if (p.waste) {
          return (
            <g key={`w${p.cell}`}>
              <rect
                x={p.x}
                y={p.y}
                width={p.w}
                height={p.h}
                fill="url(#zebra)"
                stroke="#94a3b8"
                strokeWidth="1"
              />
              <text
                x={p.x + p.w / 2}
                y={p.y + p.h / 2}
                textAnchor="middle"
                fontSize={Math.min(28, p.h / 3)}
                fill="#64748b"
              >
                atxot
              </text>
            </g>
          )
        }
        const insts = instancesByCell.get(`${sheet.no}:${p.cell}`) ?? []
        const doneCount = insts.filter((i) => i.done).length
        const allDone = insts.length > 0 && doneCount === insts.length
        const hole = holes[String(p.id)]
        const fs = Math.max(16, Math.min(34, p.h / 5))
        return (
          // biome-ignore lint/a11y/noStaticElementInteractions: SVG katakcha — 17" touch target (TZ 7.1.7)
          <g
            key={p.cell}
            onClick={() => onSelect(p)}
            className="cursor-pointer"
            opacity={allDone ? 0.35 : 1}
          >
            <rect
              x={p.x}
              y={p.y}
              width={p.w}
              height={p.h}
              fill={partColor(p.name)}
              stroke={partStroke(p.name)}
              strokeWidth="1.5"
            />
            {/* tekstura quluf (txt): 3 gorizontal chiziq — GibSaw uslubi */}
            {p.txt &&
              [0.3, 0.5, 0.7].map((f) => (
                <line
                  key={f}
                  x1={p.x + p.w * 0.35}
                  y1={p.y + p.h * f}
                  x2={p.x + p.w * 0.65}
                  y2={p.y + p.h * f}
                  stroke={partStroke(p.name)}
                  strokeWidth="1"
                  opacity="0.5"
                />
              ))}
            <text
              x={p.x + 8}
              y={p.y + fs + 4}
              fontSize={fs}
              fontWeight="700"
              fill="#1e293b"
            >
              №{p.num} {p.rot ? "⟳" : ""}{" "}
              {allDone
                ? "✓"
                : insts.length > 1
                  ? `${doneCount}/${insts.length}`
                  : ""}
            </text>
            <text
              x={p.x + 8}
              y={p.y + fs * 2 + 6}
              fontSize={fs * 0.62}
              fill="#475569"
            >
              {p.name}
            </text>
            {/* o'lchamlar qirralarda + kromka belgilari */}
            <text
              x={p.x + p.w / 2}
              y={p.y + p.h - 6}
              textAnchor="middle"
              fontSize={fs * 0.6}
              fill="#334155"
              className="num"
            >
              {p.w}
              {p.eH?.[1] ? ` · ${p.eH[1]}` : ""}
            </text>
            <text
              x={p.x + 12}
              y={p.y + p.h / 2}
              textAnchor="middle"
              fontSize={fs * 0.6}
              fill="#334155"
              transform={`rotate(-90 ${p.x + 12} ${p.y + p.h / 2})`}
              className="num"
            >
              {p.h}
              {p.eW?.[0] ? ` · ${p.eW[0]}` : ""}
            </text>
            {/* teshiklar overlay (TZ 7.1.7): yuza — haqiqiy masshtab doiralar; qirra — chuqurlik belgilari */}
            {hole?.bores?.map((b: any, i: number) => {
              const bx = p.rot ? p.x + (hole.w - b.y) : p.x + b.x
              const by = p.rot ? p.y + b.x : p.y + b.y
              return (
                <circle
                  key={`b${i}`}
                  cx={bx}
                  cy={by}
                  r={Math.max(b.d / 2, 2)}
                  fill={b.thru ? "#0f172a" : "none"}
                  stroke="#0f172a"
                  strokeWidth="1.2"
                />
              )
            })}
          </g>
        )
      })}
      {(sheet.cuts as any[]).map((c, i) => (
        <line
          key={i}
          x1={c.x1}
          y1={c.y1}
          x2={c.x2}
          y2={c.y2}
          stroke="#dc2626"
          strokeWidth="1"
          strokeDasharray="6 4"
        />
      ))}
    </svg>
  )
}

function PartCard({
  part,
  sheetNo,
  instancesByCell,
  onClose,
  admin = false,
}: {
  part: SheetPart | null
  sheetNo?: number
  instancesByCell: Map<string, any[]>
  onClose: () => void
  admin?: boolean
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
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>
            №{part.num} — {part.name}{" "}
            {part.rot && <RotateCw className="inline size-4" />}
          </DialogTitle>
        </DialogHeader>
        <div className="flex items-start gap-4">
          {next && (
            <div className="shrink-0 rounded-lg border p-2">
              <QRCodeSVG value={next.qr_text} size={140} />
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
              className="flex items-center justify-between rounded-lg border px-3 py-1.5 text-sm"
            >
              <span className="num">
                {inst.qr_text}{" "}
                {inst.done && (
                  <span className="font-bold text-green-700">✓ kesildi</span>
                )}
              </span>
              {!admin && (
                <LoadingButton
                  size="sm"
                  loading={printMutation.isPending}
                  onClick={() => printMutation.mutate(inst.instance_id)}
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
