// Tizim holati (admin-only): serverning o'zi o'lchaydigan ko'rsatkichlar —
// qaysi endpoint qancha vaqt oladi, event loop qachon va nima ishlayotganda
// bloklangan, chek agentga qancha vaqtda yetadi va navbatda nechtasi turibdi,
// bazada qaysi so'rov og'ir (`GET /system/perf`, backend `core/perf.py`).
// 2026-09-26 da tsexdagi 5-10 soniyalik kutish sababi loglardan soatlab
// qidirilgan edi — shu sahifa birinchi daqiqada ko'rsatardi.
//
// XULOSA jumlalari va chegaralar backenddan keladi (`services/system_health.py`):
// yon menyudagi belgi ham o'sha manbadan o'qiydi, ya'ni ikki joyda ikki xil
// hukm bo'lmaydi. Bu fayl faqat ko'rsatadi. Tuzilishi "golden signals" bo'yicha:
// xulosa, keyin kechikish/trafik/xato (endpointlar), to'yinish (muzlashlar,
// chek navbati), eng oxirida baza. Holat rang bilan birga IKONKA va so'z bilan
// ham beriladi (rangni ajratmaydigan ko'z uchun). Tinch holatda sahifa ham tinch:
// normal qiymat bo'yalmaydi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  CircleCheck,
  CircleDashed,
  Info,
  OctagonAlert,
  RefreshCw,
  TriangleAlert,
} from "lucide-react"
import { type ReactNode, useState } from "react"

import {
  type EndpointDetail,
  type Finding,
  type SystemPerf,
  SystemService,
  type Thresholds,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { RowOpenCell } from "@/components/Common/RowOpen"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { requireAccess } from "@/lib/guards"
import { formatDateTime, isAdmin } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { crudCallbacks } from "@/queries/mes"

export const Route = createFileRoute("/_layout/system-health")({
  component: SystemHealthPage,
  beforeLoad: requireAccess(isAdmin),
  head: () => ({ meta: [{ title: "Tizim holati | MebeliX" }] }),
})

/** Oraliqlar Redis'dagi o'lchov hajmiga mos (`perf.REQ_KEEP` ≈ 12 soat eng band
 * kunda ham) — ixtiyoriy sana tanlash bo'lsa, saqlanmagan davrni so'rab bo'lardi */
const WINDOWS = [15, 60, 180, 720] as const
/** Endpoint jadvalida avval shuncha qator — qolgani tugma bilan */
const TOP_ROWS = 25

type Level = SystemPerf["level"]
type Target = { method: string; route: string }

// Ilovaning holat ranglari: yashil = joyida (`green`, `emerald` emas — ilovada
// shu ko'p), sariq-900 och sariq fonda, qizil-700 (brak/rad etilgan belgilari
// bilan bir xil). Och fon + to'q matn — kontrast WCAG AA dan yuqori.
const TONE: Record<
  Level,
  { text: string; box: string; icon: typeof CircleCheck; word: string }
> = {
  ok: {
    text: "text-green-800",
    box: "border-green-200 bg-green-50",
    icon: CircleCheck,
    word: "Muammo topilmadi",
  },
  warn: {
    text: "text-amber-900",
    box: "border-amber-300 bg-amber-50",
    icon: TriangleAlert,
    word: "E'tibor bering",
  },
  bad: {
    text: "text-red-700",
    box: "border-red-200 bg-red-50",
    icon: OctagonAlert,
    word: "Muammo bor",
  },
  nodata: {
    text: "text-muted-foreground",
    box: "border-border bg-muted/40",
    icon: CircleDashed,
    word: "Ma'lumot yo'q",
  },
}

function level(value: number, warn: number, bad: number): Level {
  return value >= bad ? "bad" : value >= warn ? "warn" : "ok"
}

/** 702 -> "702 ms", 16535 -> "16.5 s" (backend `system_health.dur` bilan bir xil) */
function dur(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`
}

/** Hamma yo'l `/api/v1` bilan boshlanadi — har qatorda takrorlash shovqin. Muzlash
 * yozuvidagi nom metod bilan keladi ("GET /api/v1/..."), shuning uchun birinchi uchragan joydan */
function short(route: string): string {
  return route.replace("/api/v1", "")
}

function clock(iso: string | number): string {
  return new Date(iso).toLocaleTimeString("uz-UZ", { hour12: false })
}

/** Bugun bo'lsa soat, aks holda sana bilan (12 soatlik oyna yarim tundan o'tadi) */
function when(iso: string): string {
  const d = new Date(iso)
  return d.toDateString() === new Date().toDateString()
    ? clock(iso).slice(0, 5)
    : formatDateTime(iso)
}

/** 0.5 -> "30 soniya", 15 -> "15 daqiqa", 60 -> "1 soat", 190 -> "3 soat 10 daqiqa" */
function span(minutes: number): string {
  if (minutes < 1) return `${Math.max(1, Math.round(minutes * 60))} soniya`
  const m = Math.round(minutes)
  const h = Math.floor(m / 60)
  const r = m % 60
  if (!h) return `${m} daqiqa`
  return r ? `${h} soat ${r} daqiqa` : `${h} soat`
}

function LevelIcon({ l, className }: { l: Level; className?: string }) {
  const Icon = TONE[l].icon
  return (
    <Icon
      aria-hidden
      className={cn("size-4 shrink-0", TONE[l].text, className)}
    />
  )
}

function Tile({
  label,
  value,
  hint,
  l = "ok",
}: {
  label: string
  value: string
  hint?: string
  l?: Level
}) {
  const alarm = l === "warn" || l === "bad"
  return (
    <div className={cn("rounded-xl border bg-card p-4", alarm && TONE[l].box)}>
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        {alarm && <LevelIcon l={l} />}
        {label}
      </div>
      <div
        className={cn("num mt-1 text-2xl font-semibold", alarm && TONE[l].text)}
      >
        {value}
        {alarm && <span className="sr-only"> — {TONE[l].word}</span>}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  )
}

function Section({
  title,
  note,
  action,
  children,
}: {
  title: string
  note: ReactNode
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        {action}
      </div>
      <p className="mt-0.5 mb-2 max-w-3xl text-sm text-muted-foreground">
        {note}
      </p>
      {children}
    </section>
  )
}

function SystemHealthPage() {
  const [minutes, setMinutes] = useState<number>(60)
  const [target, setTarget] = useState<Target | null>(null)
  const { data, isLoading, isError, isFetching, dataUpdatedAt, refetch } =
    useQuery({
      queryKey: ["system", "perf", minutes],
      queryFn: async () =>
        (await SystemService.readSystemPerf({ query: { minutes } })).data,
      // 12 soatlik oynani o'qish ~0,2 s (100 ming yozuv) — tez-tez so'ralmaydi
      refetchInterval: minutes <= 60 ? 30_000 : 120_000,
    })

  return (
    <div>
      <PageHeader
        title="Tizim holati"
        description="Server o'z tezligini o'zi o'lchaydi: so'rovni qabul qilgandan javob berguncha. Tarmoq va brauzer vaqti bunga kirmaydi."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {dataUpdatedAt > 0 && (
              <span
                className="flex items-center gap-1.5 text-xs text-muted-foreground"
                title={`Har ${minutes <= 60 ? 30 : 120} soniyada yangilanadi`}
              >
                <RefreshCw
                  aria-hidden
                  className={cn(
                    "size-3.5",
                    isFetching && "motion-safe:animate-spin",
                  )}
                />
                Yangilandi {clock(dataUpdatedAt)}
              </span>
            )}
            <fieldset className="flex gap-1">
              <legend className="sr-only">Qaysi oraliq ko'rsatilsin</legend>
              {WINDOWS.map((m) => (
                <Button
                  key={m}
                  size="sm"
                  variant={m === minutes ? "default" : "outline"}
                  aria-pressed={m === minutes}
                  onClick={() => setMinutes(m)}
                >
                  {m < 60 ? `${m} daq` : `${m / 60} soat`}
                </Button>
              ))}
            </fieldset>
          </div>
        }
      />
      {isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : isError || !data ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <Body data={data} onOpen={setTarget} />
      )}
      {data && (
        <EndpointSheet
          target={target}
          minutes={minutes}
          t={data.thresholds}
          onClose={() => setTarget(null)}
        />
      )}
    </div>
  )
}

function FindingText({
  f,
  onOpen,
}: {
  f: Finding
  onOpen: (t: Target) => void
}) {
  const { method, route } = f
  return (
    <>
      {f.text}
      {method && route && (
        <>
          {" "}
          <button
            type="button"
            onClick={() => onOpen({ method, route })}
            className="cursor-pointer rounded-sm font-medium whitespace-nowrap underline underline-offset-2 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            Batafsil
          </button>
        </>
      )}
    </>
  )
}

function Verdict({
  data,
  onOpen,
}: {
  data: SystemPerf
  onOpen: (t: Target) => void
}) {
  const l = data.level
  const [bosh, ...qolgan] = data.findings
  const oraliq = span(data.covered_from ? data.covered_minutes : data.minutes)
  return (
    <div className={cn("rounded-xl border p-4", TONE[l].box)}>
      <div className={cn("flex items-start gap-2", TONE[l].text)}>
        <LevelIcon l={l} className="mt-0.5 size-5" />
        <div className="min-w-0">
          <div className="text-xs font-medium">{TONE[l].word}</div>
          <div className="font-semibold">
            {bosh ? (
              <FindingText f={bosh} onOpen={onOpen} />
            ) : l === "nodata" ? (
              `Oxirgi ${oraliq}da bironta so'rov yozilmagan`
            ) : (
              `Oxirgi ${oraliq}da muammo topilmadi`
            )}
          </div>
          {!bosh && (
            <div className="mt-1 text-sm">
              {l === "nodata"
                ? "Server bu vaqtda so'rov olmagan yoki o'lchov endi boshlangan — kattaroq oraliqni tanlang."
                : `Tekshirildi: sekin endpointlar, server muzlashi, server xatolari, chek kechikishi va chek navbati. ${data.thresholds.min_count} martadan kam chaqirilgan endpoint xulosaga kirmaydi (tasodif bo'lishi mumkin) — u faqat jadvalda bo'yaladi.`}
            </div>
          )}
        </div>
      </div>
      {qolgan.length > 0 && (
        <ul className="mt-2 space-y-1 pl-7 text-sm">
          {qolgan.map((x) => (
            <li
              key={x.text}
              className={cn("flex items-start gap-2", TONE[x.level].text)}
            >
              <LevelIcon l={x.level} className="mt-0.5" />
              <span>
                <span className="sr-only">{TONE[x.level].word}: </span>
                <FindingText f={x} onOpen={onOpen} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Body({
  data,
  onOpen,
}: {
  data: SystemPerf
  onOpen: (t: Target) => void
}) {
  const t = data.thresholds
  const [hammasi, setHammasi] = useState(false)
  // Daqiqaga nisbat — ma'lumot BOR vaqtga: qisman qamrovda tanlangan oraliqqa bo'lish kamaytirib ko'rsatardi
  const daq = data.covered_minutes || data.minutes
  const qisman =
    data.covered_from != null && data.covered_minutes < data.minutes - 1
  const l = data.labels
  const total = data.endpoints.reduce((s, e) => s + e.total_s, 0)
  const xato = data.endpoints.reduce((s, e) => s + e.errors, 0)
  const kutyapti = data.queues.reduce((s, q) => s + q.pending, 0)
  const tiqilgan = data.queues.find(
    (q) => q.pending > 0 && q.oldest_s != null && q.oldest_s >= t.queue_stuck_s,
  )
  const qatorlar = hammasi ? data.endpoints : data.endpoints.slice(0, TOP_ROWS)
  return (
    <div className="space-y-6">
      {qisman && data.covered_from && (
        <p className="flex items-start gap-2 rounded-lg border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>
            Tanlangan {span(data.minutes)}dan faqat oxirgi{" "}
            {span(data.covered_minutes)} bor — yozuvlar{" "}
            {when(data.covered_from)} dan boshlanadi. Hamma raqam shu vaqt
            bo'yicha.
          </span>
        </p>
      )}

      <Verdict data={data} onOpen={onOpen} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="So'rovlar"
          value={String(data.requests)}
          hint={`daqiqasiga ${(data.requests / daq).toFixed(1)}, server xatosi ${xato}`}
          l={xato ? "warn" : "ok"}
        />
        <Tile
          label="Server muzlashlari"
          value={String(data.lag_count)}
          hint={
            data.lag_count
              ? `${data.lag_long_count} tasi ${t.lag_bad_ms / 1000} s dan uzun; eng uzuni ${dur(data.lag_longest_ms)}, jami ${dur(data.lag_total_ms)}`
              : "0.2 s dan uzun muzlash yo'q"
          }
          l={
            data.lag_longest_ms >= t.lag_bad_ms
              ? "bad"
              : data.lag_count >= t.lag_warn_count
                ? "warn"
                : "ok"
          }
        />
        <Tile
          label="Chek: sekin 5%"
          value={l.p95_s == null ? "—" : `${l.p95_s.toFixed(2)} s`}
          hint={
            l.count && l.p50_s != null && l.max_s != null
              ? `navbatdan agentgacha; odatiy ${l.p50_s.toFixed(2)} s, eng sekini ${l.max_s.toFixed(2)} s (${l.count} ta)`
              : "bu oraliqda chek chiqmagan"
          }
          l={
            l.p95_s == null
              ? "ok"
              : level(l.p95_s, t.label_warn_s, t.label_bad_s)
          }
        />
        <Tile
          label="Chek navbati — hozir"
          value={data.queues.length ? String(kutyapti) : "—"}
          hint={
            !data.queues.length
              ? "chek chiqaradigan agent yo'q"
              : tiqilgan?.oldest_s != null
                ? `${tiqilgan.name}: eng eskisi ${dur(tiqilgan.oldest_s * 1000)} oldin so'ralgan`
                : kutyapti
                  ? `eng eskisi ${t.queue_stuck_s} s dan yangi`
                  : `bo'sh — ${data.queues.length} ta agent`
          }
          l={tiqilgan ? "bad" : "ok"}
        />
      </div>

      <Section
        title="Endpointlar — qayerda eng ko'p kutilgan"
        note={`So'rovlar davomiyligi yig'indisi bo'yicha: bazani yoki muzlagan serverni kutgan vaqt ham kiradi (bu CPU emas). Server muzlagan paytda KELGAN so'rovning kutishi esa kirmaydi — server uni muzlash tugagach qabul qiladi; u «Server muzlashlari»da. "Sekin 5%" (p95) ${t.p95_warn_ms / 1000} s dan sariq, ${t.p95_bad_ms / 1000} s dan qizil. Qatorni bosing — qachon sekinlashgani va nega.`}
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>So'rov</TableHead>
              <TableHead className="hidden text-right md:table-cell">
                Daqiqasiga
              </TableHead>
              <TableHead className="hidden text-right md:table-cell">
                Odatiy
              </TableHead>
              <TableHead className="text-right">Sekin 5%</TableHead>
              <TableHead className="hidden text-right lg:table-cell">
                Eng sekini
              </TableHead>
              <TableHead className="md:w-44">Vaqt ulushi</TableHead>
              <TableHead className="hidden text-right md:table-cell">
                Xato
              </TableHead>
              <TableHead className="w-6 md:w-8">
                <span className="sr-only">Tafsilot</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {qatorlar.length ? (
              qatorlar.map((e) => {
                const ulush = total > 0 ? e.total_s / total : 0
                const p95 = level(e.p95_ms, t.p95_warn_ms, t.p95_bad_ms)
                const open = () => onOpen({ method: e.method, route: e.route })
                return (
                  <TableRow
                    key={`${e.method} ${e.route}`}
                    className="cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                    tabIndex={0}
                    aria-label={`${e.method} ${short(e.route)} — tafsilot`}
                    onClick={open}
                    onKeyDown={(ev) => {
                      if (ev.key === "Enter" || ev.key === " ") {
                        ev.preventDefault()
                        open()
                      }
                    }}
                  >
                    <TableCell className="max-w-52 font-mono text-xs break-all md:max-w-72">
                      <span className="mr-1.5 text-muted-foreground">
                        {e.method}
                      </span>
                      {short(e.route)}
                    </TableCell>
                    <TableCell className="num hidden text-right md:table-cell">
                      {(e.count / daq).toFixed(1)}
                    </TableCell>
                    <TableCell className="num hidden text-right md:table-cell">
                      {dur(e.p50_ms)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "num text-right",
                        p95 !== "ok" && cn("font-semibold", TONE[p95].text),
                      )}
                    >
                      <span className="inline-flex items-center justify-end gap-1">
                        {p95 !== "ok" && <LevelIcon l={p95} />}
                        {dur(e.p95_ms)}
                        {p95 !== "ok" && (
                          <span className="sr-only">
                            {" "}
                            —{" "}
                            {(p95 === "bad" ? t.p95_bad_ms : t.p95_warn_ms) /
                              1000}{" "}
                            s dan sekin
                          </span>
                        )}
                      </span>
                    </TableCell>
                    <TableCell className="num hidden text-right lg:table-cell">
                      {dur(e.max_ms)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div
                          className="hidden h-2 w-16 overflow-hidden rounded-full bg-muted sm:block"
                          aria-hidden
                        >
                          <div
                            className="h-full bg-primary/60"
                            style={{ width: `${Math.round(ulush * 100)}%` }}
                          />
                        </div>
                        <span className="num text-xs">
                          {Math.round(ulush * 100)}%{" "}
                          <span className="hidden text-muted-foreground md:inline">
                            ({Math.round(e.total_s)} s)
                          </span>
                        </span>
                      </div>
                    </TableCell>
                    <TableCell
                      className={cn(
                        "num hidden text-right md:table-cell",
                        e.errors > 0 && "font-semibold text-red-700",
                      )}
                    >
                      {e.errors || ""}
                    </TableCell>
                    <RowOpenCell />
                  </TableRow>
                )
              })
            ) : (
              <EmptyRow colSpan={8}>
                Bu oraliqda so'rov bo'lmagan — kattaroq oraliqni tanlang
              </EmptyRow>
            )}
          </TableBody>
        </Table>
        {data.endpoints.length > TOP_ROWS && (
          <Button
            variant="ghost"
            size="sm"
            className="mt-1"
            onClick={() => setHammasi((v) => !v)}
          >
            {hammasi
              ? `Faqat birinchi ${TOP_ROWS} tasi`
              : `Hammasini ko'rsatish — ${data.endpoints.length} ta`}
          </Button>
        )}
      </Section>

      <Section
        title="Server muzlashlari"
        note={
          <>
            Server ishchisining (jarayon, pid) event loop'i shuncha kech
            uyg'ongan — bitta uzun hisob yoki ketma-ket ko'p qisqa ishlar sabab.
            Shu vaqt ichida o'sha ishchidagi so'rovlar, yangi kelganlari ham,
            navbatda turgan. Qatordagi birinchi so'rov o'sha paytda eng uzoq
            ishlayotgani — ehtimoliy sabab; eng uzoq 8 tasi ko'rsatiladi. «GC» —
            shu vaqtning qanchasini Python'ning xotira tozalagichi olgani: u
            ishlaganda ham loop to'xtaydi. «—» — yozuv bu o'lchov qo'shilishidan
            oldingi.
            {data.lag_count > data.lag_incidents.length &&
              ` ${data.lag_count} tadan oxirgi ${data.lag_incidents.length} tasi ko'rsatilgan.`}
          </>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Vaqt</TableHead>
              <TableHead className="text-right">Davomiyligi</TableHead>
              <TableHead className="hidden text-right md:table-cell">
                Shundan GC
              </TableHead>
              <TableHead className="hidden text-right md:table-cell">
                pid
              </TableHead>
              <TableHead>
                <span className="md:hidden">So'rovlar</span>
                <span className="hidden md:inline">
                  O'sha paytda ishlagan so'rovlar
                </span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.lag_incidents.length ? (
              data.lag_incidents.map((i) => {
                const li = level(i.lag_ms, t.lag_bad_ms / 2, t.lag_bad_ms)
                return (
                  <TableRow key={`${i.at}-${i.pid}`}>
                    <TableCell className="num">{clock(i.at)}</TableCell>
                    <TableCell
                      className={cn(
                        "num text-right",
                        li !== "ok" && cn("font-semibold", TONE[li].text),
                      )}
                    >
                      {dur(i.lag_ms)}
                      {/* Telefonda alohida ustun jadvalni yana 77 px kengaytirardi */}
                      <div className="text-xs font-normal text-muted-foreground md:hidden">
                        GC {i.gc_ms == null ? "—" : dur(i.gc_ms)}
                      </div>
                    </TableCell>
                    <TableCell className="num hidden text-right text-muted-foreground md:table-cell">
                      {i.gc_ms == null ? "—" : dur(i.gc_ms)}
                    </TableCell>
                    <TableCell className="num hidden text-right md:table-cell">
                      {i.pid}
                    </TableCell>
                    <TableCell className="font-mono text-xs break-all">
                      {i.inflight.length ? (
                        <>
                          <span className="font-semibold">
                            {short(i.inflight[0].path)} (
                            {dur(i.inflight[0].elapsed_ms)})
                          </span>
                          {i.inflight
                            .slice(1)
                            .map(
                              (f) =>
                                `, ${short(f.path)} (${dur(f.elapsed_ms)})`,
                            )
                            .join("")}
                        </>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                )
              })
            ) : (
              <EmptyRow colSpan={5}>Bu oraliqda server muzlamagan</EmptyRow>
            )}
          </TableBody>
        </Table>
      </Section>

      {data.queues.length > 0 && (
        <Section
          title="Chek navbati — hozir"
          note={`Har agentning navbatida nechta chek turibdi. Odatda chek bir soniyaga yetmay agentga yetadi: eng eskisi so'ralganiga ${t.queue_stuck_s} s dan ko'p bo'lsa, cheklar yetib bormayapti — kompyuter o'chiq, agent uzilgan, printer topilmagan yoki agent ulangan server ishchisi band.`}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent</TableHead>
                <TableHead className="hidden md:table-cell">
                  Oxirgi aloqa
                </TableHead>
                <TableHead className="text-right">Navbatda</TableHead>
                <TableHead className="text-right">
                  Eng eskisi so'ralganiga
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.queues.map((q) => {
                const stuck =
                  q.pending > 0 &&
                  q.oldest_s != null &&
                  q.oldest_s >= t.queue_stuck_s
                return (
                  <TableRow key={q.agent_id}>
                    <TableCell>
                      <div className="font-medium">{q.name}</div>
                      {q.machine_name && (
                        <div className="text-xs text-muted-foreground">
                          {q.machine_name}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="num hidden md:table-cell">
                      {q.last_seen_at ? formatDateTime(q.last_seen_at) : "—"}
                    </TableCell>
                    <TableCell className="num text-right">
                      {q.pending}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "num text-right",
                        stuck && cn("font-semibold", TONE.bad.text),
                      )}
                    >
                      <span className="inline-flex items-center justify-end gap-1">
                        {stuck && <LevelIcon l="bad" />}
                        {q.oldest_s != null
                          ? dur(q.oldest_s * 1000)
                          : q.pending
                            ? "noma'lum"
                            : "—"}
                        {stuck && <span className="sr-only"> — tiqilgan</span>}
                      </span>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Section>
      )}

      <DbSection data={data} />
    </div>
  )
}

function DbSection({ data }: { data: SystemPerf }) {
  const queryClient = useQueryClient()
  const [ochiq, setOchiq] = useState(false)
  const cb = crudCallbacks(
    queryClient,
    ["system", "perf"],
    "Baza statistikasi nollandi",
  )
  const reset = useMutation({
    mutationFn: () => SystemService.resetSystemDbStats(),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      setOchiq(false)
    },
  })
  return (
    <Section
      title="Bazadagi eng og'ir so'rovlar"
      action={
        data.db_available && (
          <Button variant="outline" size="sm" onClick={() => setOchiq(true)}>
            Nollash
          </Button>
        )
      }
      note={
        <>
          Jami vaqt bo'yicha.{" "}
          <b>
            Tanlangan oraliq emas —{" "}
            {data.db_since
              ? `${formatDateTime(data.db_since)} dan (oxirgi nollashdan) beri yig'ilgan`
              : "oxirgi nollashdan beri yig'ilgan"}
            .
          </b>{" "}
          O'zgarishdan keyin (deploy, indeks) nollang — shunda faqat yangi yuk
          ko'rinadi. So'rov matni ustiga bosilsa to'liq ochiladi.
        </>
      }
    >
      {data.db_available ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-right">Chaqiruv</TableHead>
              <TableHead className="hidden text-right md:table-cell">
                Jami
              </TableHead>
              <TableHead className="text-right">O'rtacha</TableHead>
              <TableHead className="hidden text-right md:table-cell">
                Qator
              </TableHead>
              <TableHead>So'rov</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.db_top.length ? (
              data.db_top.map((q) => (
                <DbRow key={q.query} q={q} t={data.thresholds} />
              ))
            ) : (
              <EmptyRow colSpan={5}>
                Nollangandan beri so'rov yozilmagan
              </EmptyRow>
            )}
          </TableBody>
        </Table>
      ) : (
        <p className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">
          Postgres'da `pg_stat_statements` yuklanmagan. Uni docker-compose'dagi
          `shared_preload_libraries` bilan yoqing (docs/07).
        </p>
      )}
      <ConfirmDialog
        open={ochiq}
        onOpenChange={setOchiq}
        title="Baza statistikasini nollaysizmi?"
        description="Yig'ilgan SQL statistikasi o'chadi va hisob hozirdan boshlanadi. Ilova ma'lumotiga tegmaydi. Amal loglarga yoziladi."
        confirmText="Nollash"
        destructive
        loading={reset.isPending}
        onConfirm={() => reset.mutate()}
      />
    </Section>
  )
}

function DbRow({ q, t }: { q: SystemPerf["db_top"][number]; t: Thresholds }) {
  const [ochiq, setOchiq] = useState(false)
  const lm = level(q.mean_ms, t.p50_warn_ms, t.p50_bad_ms)
  return (
    <TableRow>
      <TableCell className="num text-right">{q.calls}</TableCell>
      <TableCell className="num hidden text-right md:table-cell">
        {dur(q.total_ms)}
      </TableCell>
      <TableCell
        className={cn(
          "num text-right",
          lm !== "ok" && cn("font-semibold", TONE[lm].text),
        )}
      >
        {dur(q.mean_ms)}
      </TableCell>
      <TableCell className="num hidden text-right md:table-cell">
        {q.rows}
      </TableCell>
      <TableCell className="max-w-48 font-mono text-xs md:max-w-xl">
        <button
          type="button"
          aria-expanded={ochiq}
          onClick={() => setOchiq((v) => !v)}
          className={cn(
            "w-full cursor-pointer rounded-sm text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
            ochiq ? "break-all whitespace-pre-wrap" : "truncate",
          )}
        >
          {q.query}
        </button>
      </TableCell>
    </TableRow>
  )
}

function EndpointSheet({
  target,
  minutes,
  t,
  onClose,
}: {
  target: Target | null
  minutes: number
  t: Thresholds
  onClose: () => void
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system", "perf", "endpoint", target, minutes],
    queryFn: async () =>
      (
        await SystemService.readSystemPerfEndpoint({
          query: {
            method: target?.method ?? "",
            route: target?.route ?? "",
            minutes,
          },
        })
      ).data,
    enabled: target !== null,
  })
  return (
    <Sheet open={target !== null} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {target && (
          <>
            <SheetHeader>
              <SheetTitle className="font-mono text-sm leading-snug break-all">
                <span className="mr-1.5 text-muted-foreground">
                  {target.method}
                </span>
                {short(target.route)}
              </SheetTitle>
              <SheetDescription>
                Oxirgi {span(minutes)}
                {data?.covered_from &&
                new Date(data.covered_from).getTime() >
                  Date.now() - minutes * 60_000 + 60_000
                  ? ` (yozuvlar ${when(data.covered_from)} dan)`
                  : ""}
                {data ? ` — ${data.count} ta so'rov` : ""}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-6 px-4 pb-6">
              {isLoading ? (
                <Skeleton className="h-72 w-full" />
              ) : isError || !data ? (
                <QueryError onRetry={() => refetch()} />
              ) : (
                <Detail d={data} t={t} />
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function Stat({
  label,
  value,
  l = "ok",
}: {
  label: string
  value: string
  l?: Level
}) {
  const alarm = l === "warn" || l === "bad"
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "num flex items-center gap-1 text-lg font-semibold",
          alarm && TONE[l].text,
        )}
      >
        {alarm && <LevelIcon l={l} />}
        {value}
        {alarm && <span className="sr-only"> — {TONE[l].word}</span>}
      </dd>
    </div>
  )
}

function Detail({ d, t }: { d: EndpointDetail; t: Thresholds }) {
  if (!d.count || d.p50_ms == null || d.p95_ms == null || d.max_ms == null)
    return (
      <p className="text-sm text-muted-foreground">
        Bu oraliqda bu so'rov bo'lmagan.
      </p>
    )
  const chegara = t.p95_warn_ms / 1000
  return (
    <>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Odatiy" value={dur(d.p50_ms)} />
        <Stat
          label="Sekin 5%"
          value={dur(d.p95_ms)}
          l={level(d.p95_ms, t.p95_warn_ms, t.p95_bad_ms)}
        />
        <Stat label="Eng sekini" value={dur(d.max_ms)} />
        <Stat
          label="Server xatosi"
          value={String(d.errors)}
          l={d.errors ? "warn" : "ok"}
        />
      </dl>

      <section>
        <h3 className="text-sm font-semibold">Nega sekin</h3>
        <p className="mt-1 text-sm">
          {d.cause || `${chegara} s dan sekin so'rov bo'lmagan.`}
        </p>
      </section>

      <section>
        <h3 className="text-sm font-semibold">Vaqt bo'yicha</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Har ustun — {d.bucket_minutes} daqiqa, balandligi — o'sha paytdagi eng
          sekin so'rov. Chiziq — {chegara} s. Kompyuterda ustun ustiga olib
          borsangiz — so'rovlar soni va odatiy vaqti.
        </p>
        <Chart d={d} t={t} />
      </section>

      <section>
        <h3 className="text-sm font-semibold">
          Eng sekin {d.slowest.length} ta so'rov
        </h3>
        <ul className="mt-2 divide-y text-sm">
          {d.slowest.map((s) => (
            <li key={`${s.at}-${s.ms}`} className="py-2">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <span className="num text-muted-foreground">{clock(s.at)}</span>
                <SlowMs ms={s.ms} t={t} />
                {s.status >= 500 && (
                  <span className="font-semibold text-red-700">
                    xato {s.status}
                  </span>
                )}
                {s.pid != null && (
                  <span className="num text-xs text-muted-foreground">
                    pid {s.pid}
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                <SlowWhy s={s} />
              </div>
            </li>
          ))}
        </ul>
      </section>

      {d.error_times.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold">
            Server xatolari (5xx) — oxirgilari
          </h3>
          <p className="num mt-1 text-sm">
            {d.error_times.map((x) => clock(x)).join(", ")}
          </p>
        </section>
      )}
    </>
  )
}

/** Faqat chegaradan oshgani bo'yaladi — tinch qiymat tinch turadi */
function SlowMs({ ms, t }: { ms: number; t: Thresholds }) {
  const l = level(ms, t.p95_warn_ms, t.p95_bad_ms)
  return (
    <span className={cn("num font-semibold", l !== "ok" && TONE[l].text)}>
      {dur(ms)}
      {l !== "ok" && <span className="sr-only"> — {TONE[l].word}</span>}
    </span>
  )
}

function SlowWhy({ s }: { s: EndpointDetail["slowest"][number] }) {
  if (s.frozen_ms == null)
    return (
      <>
        pid qo'shilishidan oldin yozilgan — ishchi raqami yo'q, muzlash bilan
        solishtirib bo'lmaydi.
      </>
    )
  if (!s.freeze || s.frozen_ms <= 0)
    return (
      <>
        Bu so'rov davomida o'sha ishchida 0.2 s dan uzun loop kechikishi
        yozilmagan — vaqt bazani yoki Redisni kutishga, yoki qisqaroq
        kechikishlarga ketgan.
      </>
    )
  const eng = s.freeze.inflight[0]
  return (
    <>
      Vaqtining {Math.round((s.frozen_ms / s.ms) * 100)}% i ishchi muzlagan
      paytga to'g'ri keladi (muzlash {dur(s.freeze.lag_ms)}
      {s.freeze.gc_ms ? `, shundan GC ${dur(s.freeze.gc_ms)}` : ""}).
      {eng && (
        <>
          {" "}
          O'shanda eng uzoq ishlayotgani:{" "}
          <span className="font-mono">{short(eng.path)}</span> (
          {dur(eng.elapsed_ms)}).
        </>
      )}
    </>
  )
}

function Chart({ d, t }: { d: EndpointDetail; t: Thresholds }) {
  const top = Math.max(
    t.p95_warn_ms * 1.25,
    ...d.buckets.map((b) => b.max_ms ?? 0),
  )
  const sekin = d.buckets.filter((b) => b.slow > 0).length
  const first = d.buckets[0]
  const last = d.buckets[d.buckets.length - 1]
  return (
    <figure className="mt-2">
      <div
        role="img"
        aria-label={`${d.buckets.length} ta oraliqdan ${sekin} tasida ${t.p95_warn_ms / 1000} s dan sekin so'rov bo'lgan`}
        className="relative flex h-32 items-end gap-px border-b"
      >
        <div
          aria-hidden
          className="absolute inset-x-0 border-t border-dashed border-amber-500"
          style={{ bottom: `${(t.p95_warn_ms / top) * 100}%` }}
        />
        {d.buckets.map((b) => {
          const bl =
            b.max_ms == null
              ? "ok"
              : level(b.max_ms, t.p95_warn_ms, t.p95_bad_ms)
          return (
            <div
              key={b.at}
              className="flex h-full min-w-0 flex-1 items-end"
              title={
                b.count
                  ? `${clock(b.at).slice(0, 5)}: ${b.count} ta, odatiy ${dur(b.p50_ms ?? 0)}, eng sekini ${dur(b.max_ms ?? 0)}${b.errors ? `, xato ${b.errors}` : ""}`
                  : `${clock(b.at).slice(0, 5)}: so'rov yo'q`
              }
            >
              <div
                className={cn(
                  "w-full rounded-t-sm",
                  bl === "bad"
                    ? "bg-red-500"
                    : bl === "warn"
                      ? "bg-amber-500"
                      : "bg-primary/50",
                )}
                style={{
                  height: b.max_ms
                    ? `${Math.max(2, (b.max_ms / top) * 100)}%`
                    : 0,
                }}
              />
            </div>
          )
        })}
      </div>
      {first && last && (
        <figcaption className="num mt-1 flex justify-between text-xs text-muted-foreground">
          <span>{clock(first.at).slice(0, 5)}</span>
          <span>{clock(last.at).slice(0, 5)}</span>
        </figcaption>
      )}
    </figure>
  )
}
