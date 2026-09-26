// Tizim holati (admin-only): serverning o'zi o'lchaydigan ko'rsatkichlar —
// qaysi endpoint qancha vaqt oladi, event loop qachon va KIM tufayli bloklangan,
// chek agentga qancha vaqtda yetadi, bazada qaysi so'rov og'ir (`GET /system/perf`,
// backend `core/perf.py`). 2026-09-26 da tsexdagi 5-10 soniyalik kutish sababi
// loglardan soatlab qidirilgan edi — shu sahifa birinchi daqiqada ko'rsatardi.
//
// Tuzilishi "golden signals" bo'yicha: tepada XULOSA (eng jiddiy topilma —
// sarlavha), keyin kechikish/trafik/xato (endpointlar), to'yinish (muzlashlar),
// eng oxirida baza. Holat rang bilan birga IKONKA va so'z bilan ham beriladi
// (rangni ajratmaydigan ko'z uchun). Chegaralar tinch holatda sahifa ham tinch
// turishi uchun tanlangan: tuzatishdan keyingi normal soatda (p95 ≤ 0,9 s)
// hech narsa bo'yalmaydi, 2026-09-26 dagi muammo esa qizil chiqadi.

import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  CircleCheck,
  OctagonAlert,
  RefreshCw,
  TriangleAlert,
} from "lucide-react"
import { type ReactNode, useState } from "react"

import { type SystemPerf, SystemService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
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

export const Route = createFileRoute("/_layout/system-health")({
  component: SystemHealthPage,
  beforeLoad: requireAccess(isAdmin),
  head: () => ({ meta: [{ title: "Tizim holati | MebeliX" }] }),
})

const WINDOWS = [15, 60, 180] as const

/** Eng sekin 5% (p95): shundan oshsa operator kutishni sezadi */
const P95_WARN_MS = 1000
/** ...shundan oshsa ishi to'xtaydi */
const P95_BAD_MS = 3000
/** Odatiy so'rov (p50) shundan sekin bo'lsa — endpoint O'ZI og'ir */
const P50_WARN_MS = 500
const P50_BAD_MS = 1000
/** Server muzlashi shundan uzun bo'lsa — jiddiy */
const LAG_BAD_MS = 1000
/** Oynada shuncha qisqa (200-999 ms) muzlash bo'lsa — e'tibor */
const LAG_WARN_COUNT = 5
/** Chek navbatdan agentgacha (p95): normalda ~0,3 s */
const LABEL_WARN_S = 2
const LABEL_BAD_S = 5
/** Bitta endpoint server vaqtining shuncha qismidan ko'pini olsa — e'tibor */
const SHARE_WARN = 0.5
/** Kam chaqirilgan endpointning p95 i tasodif bo'lishi mumkin — xulosaga kirmaydi */
const MIN_COUNT = 5

type Level = "ok" | "warn" | "bad"
const RANK: Record<Level, number> = { bad: 0, warn: 1, ok: 2 }

// Ilovaning holat rangi uslubi (brak sahifasidagi pillalar bilan bir xil):
// och fon + to'q matn — kontrast WCAG AA dan yuqori (sariq-600 matn oq fonda 2,9:1 edi)
const TONE: Record<
  Level,
  { text: string; box: string; icon: typeof CircleCheck; word: string }
> = {
  ok: {
    text: "text-emerald-800",
    box: "border-emerald-200 bg-emerald-50",
    icon: CircleCheck,
    word: "Hammasi joyida",
  },
  warn: {
    text: "text-amber-900",
    box: "border-amber-300 bg-amber-50",
    icon: TriangleAlert,
    word: "E'tibor bering",
  },
  bad: {
    text: "text-red-800",
    box: "border-red-300 bg-red-50",
    icon: OctagonAlert,
    word: "Muammo bor",
  },
}

function level(value: number, warn: number, bad: number): Level {
  return value >= bad ? "bad" : value >= warn ? "warn" : "ok"
}

/** 702 -> "702 ms", 16535 -> "16.5 s": katta ms sonini o'qish qiyin */
function dur(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`
}

/** Hamma yo'l `/api/v1` bilan boshlanadi — har qatorda takrorlash shovqin */
function short(route: string): string {
  return route.replace(/^\/api\/v1/, "")
}

function clock(iso: string | number): string {
  return new Date(iso).toLocaleTimeString("uz-UZ", { hour12: false })
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
  return (
    <div
      className={cn("rounded-xl border bg-card p-4", l !== "ok" && TONE[l].box)}
    >
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        {l !== "ok" && <LevelIcon l={l} />}
        {label}
      </div>
      <div
        className={cn(
          "num mt-1 text-2xl font-semibold",
          l !== "ok" && TONE[l].text,
        )}
      >
        {value}
        {l !== "ok" && <span className="sr-only"> — {TONE[l].word}</span>}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  )
}

function Section({
  title,
  note,
  children,
}: {
  title: string
  note: ReactNode
  children: ReactNode
}) {
  return (
    <section>
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-0.5 mb-2 max-w-3xl text-sm text-muted-foreground">
        {note}
      </p>
      {children}
    </section>
  )
}

function SystemHealthPage() {
  const [minutes, setMinutes] = useState<number>(60)
  const { data, isLoading, isError, isFetching, dataUpdatedAt, refetch } =
    useQuery({
      queryKey: ["system", "perf", minutes],
      queryFn: async () =>
        (await SystemService.readSystemPerf({ query: { minutes } })).data,
      refetchInterval: 30_000,
    })

  return (
    <div>
      <PageHeader
        title="Tizim holati"
        description="Server o'z tezligini o'zi o'lchaydi. Har 30 soniyada yangilanadi."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {dataUpdatedAt > 0 && (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
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
        <Body data={data} />
      )}
    </div>
  )
}

type Finding = { l: Level; text: string }

/** Xulosa: nima yomon va nega — raqamlarni o'qimasdan ham ko'rinsin. Jiddiysi birinchi. */
function findings(data: SystemPerf): Finding[] {
  const out: Finding[] = []
  const total = data.endpoints.reduce((s, e) => s + e.total_s, 0)

  const uzun = data.lag_incidents.filter((i) => i.lag_ms >= LAG_BAD_MS)
  if (uzun.length) {
    // Aybdor — muzlash paytida eng uzoq ishlagan so'rov; eng ko'p uchragani
    const soni = new Map<string, number>()
    for (const i of uzun) {
      const p = i.inflight[0]?.path
      if (p) soni.set(p, (soni.get(p) ?? 0) + 1)
    }
    const aybdor = [...soni.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
    out.push({
      l: "bad",
      text: `Server ${uzun.length} marta 1 soniyadan ko'p muzladi${aybdor ? ` — ko'pincha ${short(aybdor)} ishlab turgan` : ""}. Shu paytda boshqa postlarning chek va skani ham kutgan`,
    })
  } else if (data.lag_incidents.length >= LAG_WARN_COUNT)
    out.push({
      l: "warn",
      text: `Server ${data.lag_incidents.length} marta qisqa muzladi (0,2–1 s) — «Server muzlashlari» jadvalida kim ishlaganini ko'ring`,
    })

  // Resurs yeyuvchi: server vaqtining yarmidan ko'pi bitta endpointga ketsa
  const top = data.endpoints[0]
  if (top && total > 0 && top.total_s / total >= SHARE_WARN)
    out.push({
      l: top.p50_ms >= P50_BAD_MS ? "bad" : "warn",
      text: `${short(top.route)} server vaqtining ${Math.round((top.total_s / total) * 100)}% ini oladi: daqiqasiga ${(top.count / data.minutes).toFixed(1)} marta, odatiy so'rovi ${dur(top.p50_ms)}`,
    })

  // SABAB va OQIBAT (2026-09-26 saboq'i): odatiy so'rovi sekin endpoint — o'zi og'ir;
  // odatiy so'rovi tez, lekin sekin 5% i uzun — boshqa so'rov serverni muzlatganda KUTGAN
  const ishonchli = data.endpoints.filter((e) => e.count >= MIN_COUNT)
  const ozi = ishonchli.filter((e) => e.p50_ms >= P50_WARN_MS && e !== top)
  for (const e of ozi.slice(0, 3))
    out.push({
      l: level(e.p50_ms, P50_WARN_MS, P50_BAD_MS),
      text: `${short(e.route)} o'zi sekin: odatiy so'rovi ${dur(e.p50_ms)}, sekin 5% i ${dur(e.p95_ms)}`,
    })
  if (ozi.length > 3)
    out.push({
      l: "warn",
      text: `Yana ${ozi.length - 3} ta endpoint o'zi sekin — jadvalda`,
    })
  const kutgan = ishonchli.filter(
    (e) => e.p50_ms < P50_WARN_MS && e.p95_ms >= P95_WARN_MS,
  )
  if (kutgan.length)
    out.push({
      l: "warn",
      text: `${kutgan.length} ta endpoint odatda tez, lekin ba'zan ${P95_WARN_MS / 1000} s dan ko'p kutgan (${kutgan
        .slice(0, 3)
        .map((e) => short(e.route))
        .join(
          ", ",
        )}${kutgan.length > 3 ? " va boshq." : ""}). Bu odatda BOSHQA so'rov serverni muzlatganining belgisi`,
    })

  const l = data.labels
  if (l.p95_s != null && l.p95_s >= LABEL_WARN_S)
    out.push({
      l: level(l.p95_s, LABEL_WARN_S, LABEL_BAD_S),
      text: `Chek agentga kech yetyapti: sekin 5% i ${l.p95_s.toFixed(1)} s`,
    })
  const xato = data.endpoints.reduce((s, e) => s + e.errors, 0)
  if (xato)
    out.push({
      l: "warn",
      text: `${xato} ta server xatosi (5xx) — jadvaldagi «Xato» ustunida`,
    })
  if (!data.db_available)
    out.push({
      l: "warn",
      text: "Baza statistikasi yoqilmagan — og'ir SQL ko'rinmaydi",
    })
  return out.sort((a, b) => RANK[a.l] - RANK[b.l])
}

function Verdict({ data }: { data: SystemPerf }) {
  const f = findings(data)
  const l: Level = f[0]?.l ?? "ok"
  const [bosh, ...qolgan] = f
  return (
    <div className={cn("rounded-xl border p-4", TONE[l].box)}>
      <div className={cn("flex items-start gap-2", TONE[l].text)}>
        <LevelIcon l={l} className="mt-0.5 size-5" />
        <div>
          <div className="text-xs font-medium">{TONE[l].word}</div>
          <div className="font-semibold">
            {bosh
              ? bosh.text
              : `Oxirgi ${data.minutes} daqiqada sekinlik ham, muzlash ham, xato ham yo'q`}
          </div>
        </div>
      </div>
      {qolgan.length > 0 && (
        <ul className="mt-2 space-y-1 pl-7 text-sm">
          {qolgan.map((x) => (
            <li
              key={x.text}
              className={cn("flex items-start gap-2", TONE[x.l].text)}
            >
              <LevelIcon l={x.l} className="mt-0.5" />
              <span>
                <span className="sr-only">{TONE[x.l].word}: </span>
                {x.text}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Body({ data }: { data: SystemPerf }) {
  const eng = data.lag_incidents.reduce((m, i) => Math.max(m, i.lag_ms), 0)
  const l = data.labels
  const total = data.endpoints.reduce((s, e) => s + e.total_s, 0)
  const xato = data.endpoints.reduce((s, e) => s + e.errors, 0)
  return (
    <div className="space-y-6">
      <Verdict data={data} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="So'rovlar"
          value={String(data.requests)}
          hint={`daqiqasiga ${(data.requests / data.minutes).toFixed(1)}, xato ${xato}`}
          l={xato ? "warn" : "ok"}
        />
        <Tile
          label="Server muzlashlari"
          value={String(data.lag_incidents.length)}
          hint={eng ? `eng uzuni ${dur(eng)}` : "0,2 s dan uzun muzlash yo'q"}
          l={
            eng >= LAG_BAD_MS
              ? "bad"
              : data.lag_incidents.length >= LAG_WARN_COUNT
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
          l={l.p95_s == null ? "ok" : level(l.p95_s, LABEL_WARN_S, LABEL_BAD_S)}
        />
        <Tile
          label="Baza statistikasi"
          value={data.db_available ? "Yoqilgan" : "Yoqilmagan"}
          hint={
            data.db_since
              ? `${formatDateTime(data.db_since)} dan beri`
              : undefined
          }
          l={data.db_available ? "ok" : "warn"}
        />
      </div>

      <Section
        title="Endpointlar — server vaqtini kim yeyapti"
        note={`Server vaqtidan olgan ulushi bo'yicha. "Sekin 5%" (p95) ${P95_WARN_MS / 1000} s dan sariq, ${P95_BAD_MS / 1000} s dan qizil.`}
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
              <TableHead className="md:w-44">
                <span className="md:hidden">Ulush</span>
                <span className="hidden md:inline">Server vaqtidan</span>
              </TableHead>
              <TableHead className="hidden text-right md:table-cell">
                Xato
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.endpoints.length ? (
              data.endpoints.slice(0, 25).map((e) => {
                const ulush = total > 0 ? e.total_s / total : 0
                const p95 = level(e.p95_ms, P95_WARN_MS, P95_BAD_MS)
                return (
                  <TableRow key={`${e.method} ${e.route}`}>
                    <TableCell className="max-w-52 font-mono text-xs break-all md:max-w-72">
                      <span className="mr-1.5 text-muted-foreground">
                        {e.method}
                      </span>
                      {short(e.route)}
                    </TableCell>
                    <TableCell className="num hidden text-right md:table-cell">
                      {(e.count / data.minutes).toFixed(1)}
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
                            className={cn(
                              "h-full",
                              ulush >= SHARE_WARN
                                ? "bg-amber-500"
                                : "bg-primary/60",
                            )}
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
                        e.errors > 0 && "font-semibold text-red-800",
                      )}
                    >
                      {e.errors || ""}
                    </TableCell>
                  </TableRow>
                )
              })
            ) : (
              <EmptyRow colSpan={7}>
                Bu oraliqda so'rov bo'lmagan — kattaroq oraliqni tanlang
              </EmptyRow>
            )}
          </TableBody>
        </Table>
      </Section>

      <Section
        title="Server muzlashlari"
        note="Server ishchisi shuncha vaqt hech kimga javob bermagan — boshqa postlarning chek va skani ham kutgan. Birinchi turgan so'rov odatda aybdor. Serverda ikkita ishchi bor (pid)."
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Vaqt</TableHead>
              <TableHead className="text-right">Davomiyligi</TableHead>
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
                const li = level(i.lag_ms, LAG_BAD_MS / 2, LAG_BAD_MS)
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
              <EmptyRow colSpan={4}>Bu oraliqda server muzlamagan</EmptyRow>
            )}
          </TableBody>
        </Table>
      </Section>

      <Section
        title="Bazadagi eng og'ir so'rovlar"
        note={
          <>
            Jami vaqt bo'yicha.{" "}
            <b>
              Tanlangan oraliq emas — baza oxirgi marta ishga tushgandan beri
              {data.db_since ? ` (${formatDateTime(data.db_since)})` : ""}.
            </b>{" "}
            So'rov matni ustiga bosilsa to'liq ochiladi.
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
              {data.db_top.map((q) => (
                <DbRow key={q.query} q={q} />
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">
            Postgres'da `pg_stat_statements` yuklanmagan. Uni
            docker-compose'dagi `shared_preload_libraries` bilan yoqing
            (docs/07).
          </p>
        )}
      </Section>
    </div>
  )
}

function DbRow({ q }: { q: SystemPerf["db_top"][number] }) {
  const [ochiq, setOchiq] = useState(false)
  const lm = level(q.mean_ms, P50_WARN_MS, P50_BAD_MS)
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
