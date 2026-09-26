// Tizim holati (admin-only): serverning o'zi o'lchaydigan ko'rsatkichlar —
// qaysi endpoint qancha vaqt oladi, event loop qachon va KIM tufayli bloklangan,
// chek agentga qancha vaqtda yetadi, bazada qaysi so'rov og'ir (`GET /system/perf`,
// backend `core/perf.py`). 2026-09-26 da tsexdagi 5-10 soniyalik kutish sababi
// loglardan soatlab qidirilgan edi — shu sahifa birinchi daqiqada ko'rsatardi.
//
// Tuzilishi "golden signals" bo'yicha: tepada XULOSA (nima yomon va nega),
// keyin kechikish/trafik/xato (endpointlar), to'yinish (event loop bloklari),
// eng oxirida baza. Chegaralar odam sezgisidan: 300 ms gacha — darhol, 1 s dan
// ortig'i — operator kutib qoladi.

import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
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

/** Shundan tez — odam uchun "darhol" (sariq chegara) */
const WARN_MS = 300
/** Shundan sekin — operator kutib qoladi (qizil chegara) */
const SLOW_MS = 1000
/** Chek navbatdan agentgacha: odatda < 1 s (2026-09-26 da mediana 0,25–1,1 s) */
const LABEL_WARN_S = 1
const LABEL_BAD_S = 2
/** Bitta endpoint server vaqtining shuncha qismidan ko'pini olsa — e'tibor */
const SHARE_WARN = 0.5
/** Kam chaqirilgan endpointning p95 i tasodif bo'lishi mumkin — xulosaga kirmaydi */
const MIN_COUNT = 5

type Level = "ok" | "warn" | "bad"

const LEVEL_TEXT: Record<Level, string> = {
  ok: "text-emerald-700",
  warn: "text-amber-600",
  bad: "text-red-600",
}

function msLevel(ms: number): Level {
  return ms >= SLOW_MS ? "bad" : ms >= WARN_MS ? "warn" : "ok"
}

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString("uz-UZ", { hour12: false })
}

function Tile({
  label,
  value,
  hint,
  level = "ok",
}: {
  label: string
  value: string
  hint?: string
  level?: Level
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div
        className={cn(
          "num mt-1 text-2xl font-semibold",
          level !== "ok" && LEVEL_TEXT[level],
        )}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  )
}

function Legend({ children }: { children: ReactNode }) {
  return <p className="mb-2 text-sm text-muted-foreground">{children}</p>
}

function SystemHealthPage() {
  const [minutes, setMinutes] = useState<number>(60)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system", "perf", minutes],
    queryFn: async () =>
      (await SystemService.readSystemPerf({ query: { minutes } })).data,
    refetchInterval: 30_000,
  })

  return (
    <div>
      <PageHeader
        title="Tizim holati"
        description="Server o'zi o'lchaydi: qaysi so'rov qancha vaqt oladi, server qachon muzlagan va kim tufayli, chek agentga qancha vaqtda yetadi, bazada nima og'ir. Har 30 soniyada yangilanadi."
        actions={
          <div className="flex gap-1">
            {WINDOWS.map((m) => (
              <Button
                key={m}
                size="sm"
                variant={m === minutes ? "default" : "outline"}
                onClick={() => setMinutes(m)}
              >
                {m < 60 ? `${m} daq` : `${m / 60} soat`}
              </Button>
            ))}
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

/** Tepadagi xulosa: nima yomon va nega — raqamlarni o'qimasdan ham ko'rinsin */
function findings(data: SystemPerf): { level: Level; text: string }[] {
  const out: { level: Level; text: string }[] = []
  const total = data.endpoints.reduce((s, e) => s + e.total_s, 0)

  const muzlash = data.lag_incidents.filter((i) => i.lag_ms >= SLOW_MS)
  if (muzlash.length) {
    // Aybdor — blok paytida eng uzoq ishlagan so'rov; eng ko'p uchragani ko'rsatiladi
    const soni = new Map<string, number>()
    for (const i of muzlash) {
      const p = i.inflight[0]?.path
      if (p) soni.set(p, (soni.get(p) ?? 0) + 1)
    }
    const aybdor = [...soni.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
    out.push({
      level: "bad",
      text: `Server ${muzlash.length} marta 1 soniyadan ko'p muzladi — o'sha paytda shu ishchidagi hamma so'rov (chek, skan) kutgan${aybdor ? `. Ko'pincha ishlab turgan: ${aybdor}` : ""}`,
    })
  }
  // Resurs yeyuvchi: server vaqtining yarmidan ko'pi bitta endpointga ketsa
  const top = data.endpoints[0]
  if (top && total > 0 && top.total_s / total >= SHARE_WARN)
    out.push({
      level: top.p50_ms >= SLOW_MS ? "bad" : "warn",
      text: `${top.method} ${top.route} server vaqtining ${Math.round((top.total_s / total) * 100)}% ini oladi — daqiqasiga ${(top.count / data.minutes).toFixed(1)} marta, odatiy so'rovi ${Math.round(top.p50_ms)} ms`,
    })
  // SABAB va OQIBATni ajratamiz (2026-09-26 saboq'i): odatiy so'rovi (p50) sekin endpoint —
  // o'zi og'ir; p50 tez, lekin p95 sekin — o'zi emas, boshqa so'rov serverni muzlatganda KUTGAN
  const ishonchli = data.endpoints.filter((e) => e.count >= MIN_COUNT)
  const ozi = ishonchli.filter((e) => e.p50_ms >= WARN_MS && e !== top)
  for (const e of ozi.slice(0, 3))
    out.push({
      level: e.p50_ms >= SLOW_MS ? "bad" : "warn",
      text: `${e.method} ${e.route} o'zi sekin: odatiy so'rovi ${Math.round(e.p50_ms)} ms, p95 ${Math.round(e.p95_ms)} ms`,
    })
  if (ozi.length > 3)
    out.push({
      level: "warn",
      text: `yana ${ozi.length - 3} ta endpoint o'zi sekin — jadvalda`,
    })
  const kutgan = ishonchli.filter(
    (e) => e.p50_ms < WARN_MS && e.p95_ms >= SLOW_MS,
  )
  if (kutgan.length)
    out.push({
      level: "warn",
      text: `${kutgan.length} ta endpoint odatda tez, lekin ba'zan ${SLOW_MS / 1000} s+ kutgan (${kutgan
        .slice(0, 3)
        .map((e) => e.route.replace("/api/v1", ""))
        .join(
          ", ",
        )}${kutgan.length > 3 ? "…" : ""}) — bu odatda BOSHQA so'rov serverni muzlatganining belgisi: yuqoridagi og'ir endpoint va «Server muzlashlari»ni ko'ring`,
    })
  const l = data.labels
  if (l.p95_s != null && l.p95_s >= LABEL_WARN_S)
    out.push({
      level: l.p95_s >= LABEL_BAD_S ? "bad" : "warn",
      text: `Chek agentga kech yetyapti: p95 ${l.p95_s.toFixed(1)} s`,
    })
  const xato = data.endpoints.reduce((s, e) => s + e.errors, 0)
  if (xato)
    out.push({
      level: "warn",
      text: `${xato} ta server xatosi (5xx) — «Xato» ustunida`,
    })
  if (!data.db_available)
    out.push({
      level: "warn",
      text: "Baza statistikasi yoqilmagan — og'ir SQL ko'rinmaydi",
    })
  return out
}

function Verdict({ data }: { data: SystemPerf }) {
  const f = findings(data)
  const level: Level = f.some((x) => x.level === "bad")
    ? "bad"
    : f.length
      ? "warn"
      : "ok"
  const box = {
    ok: "border-emerald-600/30 bg-emerald-600/5",
    warn: "border-amber-500/40 bg-amber-500/5",
    bad: "border-red-600/40 bg-red-600/5",
  }[level]
  return (
    <div className={cn("rounded-xl border p-4", box)}>
      <div className={cn("font-semibold", LEVEL_TEXT[level])}>
        {level === "ok"
          ? `Hammasi joyida — oxirgi ${data.minutes} daqiqada sekinlik yo'q`
          : level === "bad"
            ? "Muammo bor"
            : "E'tibor bering"}
      </div>
      {f.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm">
          {f.map((x) => (
            <li key={x.text} className={LEVEL_TEXT[x.level]}>
              {x.text}
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
          hint={`daqiqasiga ${(data.requests / data.minutes).toFixed(1)} · 5xx xato: ${xato}`}
          level={xato ? "warn" : "ok"}
        />
        <Tile
          label="Server muzlashlari (event loop ≥ 200 ms)"
          value={String(data.lag_incidents.length)}
          hint={eng ? `eng uzuni ${eng} ms` : "muzlash yo'q"}
          level={msLevel(eng)}
        />
        <Tile
          label="Chek: navbatdan agentgacha"
          value={l.p50_s == null ? "—" : `${l.p50_s.toFixed(2)} s`}
          hint={
            l.count
              ? `${l.count} ta · p95 ${l.p95_s?.toFixed(2)} s · eng ko'pi ${l.max_s?.toFixed(2)} s · odatda < ${LABEL_WARN_S} s`
              : "bu oynada chek yo'q"
          }
          level={
            (l.p95_s ?? 0) >= LABEL_BAD_S
              ? "bad"
              : (l.p95_s ?? 0) >= LABEL_WARN_S
                ? "warn"
                : "ok"
          }
        />
        <Tile
          label="Baza statistikasi"
          value={data.db_available ? "yoqilgan" : "yoqilmagan"}
          hint={
            data.db_since
              ? `${formatDateTime(data.db_since)} dan beri yig'ilyapti`
              : undefined
          }
          level={data.db_available ? "ok" : "warn"}
        />
      </div>

      <section>
        <h2 className="mb-1 font-semibold">
          Endpointlar — server vaqtini kim yeyapti
        </h2>
        <Legend>
          <b>p50</b> — odatiy so'rov, <b>p95</b> — eng sekin 5% chegarasi (sariq
          ≥ {WARN_MS} ms, qizil ≥ {SLOW_MS} ms). <b>Ulush</b> — shu oynada
          server vaqtining qancha qismi shu endpointga ketgan: tepadagisi
          resursni eng ko'p yeydi. <b>Daq.ga</b> — daqiqasiga necha marta
          chaqirilgan (polling yoki WS to'lqini shu yerda ko'rinadi).
        </Legend>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>So'rov</TableHead>
              <TableHead className="text-right">Daq.ga</TableHead>
              <TableHead className="text-right">p50, ms</TableHead>
              <TableHead className="text-right">p95, ms</TableHead>
              <TableHead className="text-right">Eng uzun, ms</TableHead>
              <TableHead className="w-40">Ulush</TableHead>
              <TableHead className="text-right">Xato</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.endpoints.length ? (
              data.endpoints.slice(0, 25).map((e) => {
                const ulush = total > 0 ? e.total_s / total : 0
                return (
                  <TableRow key={`${e.method} ${e.route}`}>
                    <TableCell className="font-mono text-xs">
                      {e.method} {e.route}
                    </TableCell>
                    <TableCell className="num text-right">
                      {(e.count / data.minutes).toFixed(1)}
                    </TableCell>
                    <TableCell className="num text-right">
                      {Math.round(e.p50_ms)}
                    </TableCell>
                    <TableCell
                      className={cn(
                        "num text-right",
                        msLevel(e.p95_ms) !== "ok" &&
                          cn("font-semibold", LEVEL_TEXT[msLevel(e.p95_ms)]),
                      )}
                    >
                      {Math.round(e.p95_ms)}
                    </TableCell>
                    <TableCell className="num text-right">
                      {Math.round(e.max_ms)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-20 overflow-hidden rounded-full bg-muted">
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
                          {Math.round(ulush * 100)}% · {e.total_s} s
                        </span>
                      </div>
                    </TableCell>
                    <TableCell
                      className={cn(
                        "num text-right",
                        e.errors > 0 && "text-red-600",
                      )}
                    >
                      {e.errors || ""}
                    </TableCell>
                  </TableRow>
                )
              })
            ) : (
              <EmptyRow colSpan={7}>Bu oynada so'rov yo'q</EmptyRow>
            )}
          </TableBody>
        </Table>
      </section>

      <section>
        <h2 className="mb-1 font-semibold">Server muzlashlari</h2>
        <Legend>
          Server ishchisi shuncha vaqt boshqa hech kimga javob bermagan — boshqa
          postlarning chek va skani ham kutgan. Birinchi turgan so'rov (eng uzoq
          ishlagani) odatda aybdor. Serverda 2 ta ishchi bor (<b>pid</b>).
        </Legend>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Vaqt</TableHead>
              <TableHead className="text-right">Muzlash, ms</TableHead>
              <TableHead className="text-right">pid</TableHead>
              <TableHead>O'sha paytda ishlagan so'rovlar (ms)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.lag_incidents.length ? (
              data.lag_incidents.map((i) => (
                <TableRow key={`${i.at}-${i.pid}`}>
                  <TableCell className="num">{clock(i.at)}</TableCell>
                  <TableCell
                    className={cn(
                      "num text-right",
                      LEVEL_TEXT[msLevel(i.lag_ms)],
                    )}
                  >
                    {i.lag_ms}
                  </TableCell>
                  <TableCell className="num text-right">{i.pid}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {i.inflight.length ? (
                      <>
                        <b>
                          {i.inflight[0].path} ({i.inflight[0].elapsed_ms})
                        </b>
                        {i.inflight
                          .slice(1)
                          .map((f) => ` · ${f.path} (${f.elapsed_ms})`)
                          .join("")}
                      </>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <EmptyRow colSpan={4}>Bu oynada muzlash bo'lmagan</EmptyRow>
            )}
          </TableBody>
        </Table>
      </section>

      <section>
        <h2 className="mb-1 font-semibold">Bazadagi eng og'ir so'rovlar</h2>
        <Legend>
          Jami vaqt bo'yicha.{" "}
          <b>
            Bu jadval tanlangan oyna emas — baza oxirgi marta ishga tushgandan
            beri
          </b>
          {data.db_since ? ` (${formatDateTime(data.db_since)})` : ""}. O'rtacha{" "}
          {WARN_MS} ms dan oshgani sariq.
        </Legend>
        {data.db_available ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">Chaqiruv</TableHead>
                <TableHead className="text-right">Jami, ms</TableHead>
                <TableHead className="text-right">O'rtacha, ms</TableHead>
                <TableHead className="text-right">Qator</TableHead>
                <TableHead>So'rov</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.db_top.map((q) => (
                <TableRow key={q.query}>
                  <TableCell className="num text-right">{q.calls}</TableCell>
                  <TableCell className="num text-right">{q.total_ms}</TableCell>
                  <TableCell
                    className={cn(
                      "num text-right",
                      msLevel(q.mean_ms) !== "ok" &&
                        LEVEL_TEXT[msLevel(q.mean_ms)],
                    )}
                  >
                    {q.mean_ms}
                  </TableCell>
                  <TableCell className="num text-right">{q.rows}</TableCell>
                  <TableCell
                    className="max-w-xl truncate font-mono text-xs"
                    title={q.query}
                  >
                    {q.query}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">
            `pg_stat_statements` yoqilmagan — Postgres uni
            `shared_preload_libraries` bilan yuklashi kerak (docker-compose).
          </p>
        )}
      </section>
    </div>
  )
}
