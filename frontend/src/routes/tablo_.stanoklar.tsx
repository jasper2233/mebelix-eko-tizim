// STANOK TAXTASI: tsex zalidagi TV ekran — Pico ulangan stanoklarning jonli holati
// va BUGUNGI OEE si. Buyurtma taxtasidan (`/tablo`) alohida sahifa: bitta ekranda
// ikkalasini siqish kartalarni o'qib bo'lmas darajada kichraytirardi.
//
// Raqamlar «Stanok vaqti» hisobotidan keladi (server o'sha handlerni bugungi kun
// uchun chaqiradi) — devordagi taxta va hisobot hech qachon ikki xil raqam
// ko'rsatmaydi.

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { type TabloMachineRow, TabloService } from "@/client"
import { BrandLoader } from "@/components/Common/BrandLoader"
import { useMesWs } from "@/hooks/useMesWs"
import { requireAuth } from "@/lib/guards"
import { ANDON_STATE_LABELS, KROMKA_VERDICT_LABELS } from "@/lib/mes"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/tablo_/stanoklar")({
  component: StanoklarPage,
  head: () => ({ meta: [{ title: "Stanoklar | MebeliX" }] }),
  beforeLoad: async () => {
    await requireAuth()
  },
})

/** Holat rangi. `null` — Pico yoki agentdan 90 soniyadan beri xabar yo'q:
 *  bu «o'chiq» EMAS va o'chiq bilan bir xil ko'rinmasligi kerak — nosozlik
 *  aynan shu farqda bilinadi (chiziqli fon + «ALOQA YO'Q» yozuvi). */
const TONE: Record<string, { band: string; dot: string; label: string }> = {
  PROCESSING: {
    band: "bg-emerald-500",
    dot: "bg-emerald-300",
    label: "text-emerald-50",
  },
  AWAIT_PART: {
    band: "bg-emerald-600",
    dot: "bg-emerald-300",
    label: "text-emerald-50",
  },
  IDLE: { band: "bg-amber-500", dot: "bg-amber-200", label: "text-amber-950" },
  STOPPED: {
    band: "bg-orange-600",
    dot: "bg-orange-200",
    label: "text-orange-50",
  },
  FAULT: { band: "bg-red-600", dot: "bg-red-200", label: "text-red-50" },
  OFF: { band: "bg-slate-600", dot: "bg-slate-300", label: "text-slate-100" },
  BOOT: { band: "bg-sky-600", dot: "bg-sky-200", label: "text-sky-50" },
}
const LINK_LOST = {
  band: "bg-slate-700 [background-image:repeating-linear-gradient(45deg,transparent,transparent_10px,rgba(255,255,255,.08)_10px,rgba(255,255,255,.08)_20px)]",
  dot: "bg-slate-400",
  label: "text-slate-200",
}

/** "12 daq" / "2 soat 5 daq" — devor ekranida soniya keraksiz, sana esa o'qilmaydi. */
function davomiyligi(iso: string | null | undefined): string {
  if (!iso) return ""
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  const d = Math.floor(s / 60)
  if (d < 60) return `${d} daq`
  return `${Math.floor(d / 60)} soat ${d % 60} daq`
}

const soat = (s: number) =>
  `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}`
const foiz = (v: number | null | undefined) => (v == null ? "—" : `${v}%`)

/** OEE ning bitta ko'rsatkichi: katta raqam + ostida yorliq va ustun.
 *  Ustun uzoqdan o'qiladi — raqamni ko'rmasdan ham «past/baland» bilinadi. */
function Metric({
  label,
  value,
  tone,
}: {
  label: string
  value: number | null | undefined
  tone: string
}) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value))
  return (
    <div className="min-w-0 flex-1">
      <div className="num text-3xl font-black leading-none text-white">
        {foiz(value)}
      </div>
      <div className="mt-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-700">
        <div className={cn("h-full", tone)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function MachineCard({ row }: { row: TabloMachineRow }) {
  const tone = row.state ? (TONE[row.state] ?? TONE.OFF) : LINK_LOST
  const holat = row.state
    ? (ANDON_STATE_LABELS[row.state] ?? row.state)
    : "ALOQA YO'Q"
  return (
    <article className="flex min-w-0 flex-col overflow-hidden rounded-2xl bg-slate-900 ring-1 ring-slate-700/70">
      {/* Holat lentasi — kartaning eng katta va eng uzoqdan ko'rinadigan qismi */}
      <div
        className={cn(
          "flex items-baseline gap-3 px-5 py-3",
          tone.band,
          tone.label,
        )}
      >
        <span className="truncate text-2xl font-black uppercase">
          {row.machine_name}
        </span>
        <span className="ml-auto whitespace-nowrap text-2xl font-black uppercase">
          {holat}
        </span>
        <span className="num whitespace-nowrap text-xl font-bold opacity-90">
          {davomiyligi(row.since)}
        </span>
      </div>

      <div className="flex min-w-0 flex-col gap-3 p-5">
        {/* Smena: bo'sh bo'lsa QIZIL — smenasiz sabab so'ralmaydi va hisobot buziladi */}
        <div
          className={cn(
            "truncate text-lg font-bold",
            row.crew.length ? "text-slate-200" : "text-red-400",
          )}
        >
          {row.crew.length ? row.crew.join(" · ") : "Smena ochilmagan"}
        </div>

        <div className="num text-base text-slate-400">
          Bugun ish {soat(row.run_s)} · to'xtash {soat(row.stop_s)} ·{" "}
          {row.parts} detal
          {row.defects > 0 ? ` · ${row.defects} brak` : ""}
        </div>

        {/* OEE to'rtligi: A · P · Q va ko'paytmasi */}
        <div className="flex gap-4 border-t border-slate-800 pt-3">
          <Metric
            label="Availability"
            value={row.availability_pct}
            tone="bg-sky-400"
          />
          <Metric
            label="Performance"
            value={row.performance_pct}
            tone="bg-violet-400"
          />
          <Metric label="Quality" value={row.quality_pct} tone="bg-teal-400" />
          <div className="min-w-0 flex-1 border-l border-slate-800 pl-4">
            <div className="num text-4xl font-black leading-none text-amber-300">
              {foiz(row.oee_pct)}
            </div>
            <div className="mt-1 text-[11px] font-bold uppercase tracking-wider text-amber-500/80">
              OEE
            </div>
          </div>
        </div>

        {/* Postga xos qator: kromkada oxirgi o'lchov */}
        {row.last_mm != null && (
          <div className="num truncate text-base text-sky-300">
            Oxirgi o'lchov {row.last_mm.toFixed(0)} mm
            {row.last_verdict
              ? ` · ${KROMKA_VERDICT_LABELS[row.last_verdict] ?? row.last_verdict}`
              : ""}
          </div>
        )}

        {/* Sababsiz to'xtashlar — operator oynani yopib ketgani shu yerda ko'rinadi */}
        {row.pending_reasons > 0 && (
          <div className="truncate rounded-lg bg-red-500/15 px-3 py-2 text-base font-bold text-red-300">
            ⚠ {row.pending_reasons} to'xtashga sabab kiritilmagan
          </div>
        )}
      </div>
    </article>
  )
}

const QUERY_KEY = ["tablo", "machines"]

function StanoklarPage() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async () => (await TabloService.readTabloMachines()).data,
    // Devor ekrani soatlab ochiq turadi: WS asosiy manba, poll — soket uzilgani uchun
    refetchInterval: 60_000,
  })

  // WS har hodisada so'rov yubormaydi: hisob bir kunlik oraliqni qayta yuritadi,
  // kromkada esa har detalda xabar keladi. Eng tez 15 soniyada bir marta.
  const oxirgi = useRef(0)
  const [, tik] = useState(0)
  useMesWs(
    useCallback(
      (event) => {
        if (
          !["andon.state", "kromka.measure", "scan.recorded"].includes(
            event.type,
          )
        )
          return
        const endi = Date.now()
        if (endi - oxirgi.current < 15_000) return
        oxirgi.current = endi
        queryClient.invalidateQueries({ queryKey: QUERY_KEY })
      },
      [queryClient],
    ),
  )
  // Holat davomiyligi («12 daq») o'zi sanab tursin — usiz raqam qotib qolardi
  useEffect(() => {
    const t = setInterval(() => tik((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [])

  const rows = data ?? []
  return (
    <div className="min-h-screen bg-slate-950 p-6 text-slate-100">
      <header className="mb-5 flex items-baseline gap-4">
        <Link
          to="/tablo"
          className="flex items-center gap-2 text-slate-400 hover:text-slate-200"
        >
          <ArrowLeft className="size-5" /> TABLO
        </Link>
        <h1 className="text-3xl font-black uppercase tracking-wide">
          Stanoklar
        </h1>
        <span className="text-base text-slate-500">
          Pico ulangan ish markazlari · bugungi OEE
        </span>
      </header>

      {isLoading ? (
        <BrandLoader />
      ) : rows.length === 0 ? (
        <p className="text-xl text-slate-400">
          Signal ustuni ulangan ish markazi yo'q — agent va Pico ulangach bu
          yerda paydo bo'ladi.
        </p>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
          {rows.map((row) => (
            <MachineCard key={row.machine_id} row={row} />
          ))}
        </div>
      )}
    </div>
  )
}
