// Tizim holati (admin-only): serverning o'zi o'lchaydigan ko'rsatkichlar —
// qaysi endpoint qancha vaqt oladi, event loop qachon va KIM tufayli bloklangan,
// chek agentga qancha vaqtda yetadi, bazada qaysi so'rov og'ir (`GET /system/perf`,
// backend `core/perf.py`). 2026-09-26 da tsexdagi 5-10 soniyalik kutish sababi
// loglardan soatlab qidirilgan edi — shu sahifa birinchi daqiqada ko'rsatardi.

import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

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

/** Endpoint p95 shundan oshsa qizil — terminal operatori kutishni sezadigan chegara */
const SLOW_MS = 1000

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString("uz-UZ", { hour12: false })
}

function Tile({
  label,
  value,
  hint,
  bad,
}: {
  label: string
  value: string
  hint?: string
  bad?: boolean
}) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div
        className={cn("num mt-1 text-2xl font-semibold", bad && "text-red-600")}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
    </div>
  )
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
        description="Server tezligi — oxirgi so'rovlar, event loop bloklari, chek kechikishi va bazadagi og'ir so'rovlar. Har 30 soniyada yangilanadi."
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

function Body({ data }: { data: SystemPerf }) {
  const eng = data.lag_incidents.reduce((m, i) => Math.max(m, i.lag_ms), 0)
  const l = data.labels
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="So'rovlar" value={String(data.requests)} />
        <Tile
          label="Event loop bloklari"
          value={String(data.lag_incidents.length)}
          hint={eng ? `eng uzuni ${eng} ms` : "blok yo'q"}
          bad={eng >= SLOW_MS}
        />
        <Tile
          label="Chek: navbatdan agentgacha"
          value={l.p50_s == null ? "—" : `${l.p50_s.toFixed(2)} s`}
          hint={
            l.count
              ? `${l.count} ta · p95 ${l.p95_s?.toFixed(2)} s · eng ko'pi ${l.max_s?.toFixed(2)} s`
              : "bu oynada chek yo'q"
          }
          bad={(l.p95_s ?? 0) * 1000 >= SLOW_MS}
        />
        <Tile
          label="Baza statistikasi"
          value={data.db_available ? "yoqilgan" : "yoqilmagan"}
          hint={
            data.db_since
              ? `${formatDateTime(data.db_since)} dan beri`
              : undefined
          }
          bad={!data.db_available}
        />
      </div>

      <section>
        <h2 className="mb-2 font-semibold">
          Endpointlar — server vaqti bo'yicha
        </h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>So'rov</TableHead>
              <TableHead className="text-right">Soni</TableHead>
              <TableHead className="text-right">p50, ms</TableHead>
              <TableHead className="text-right">p95, ms</TableHead>
              <TableHead className="text-right">Eng uzun, ms</TableHead>
              <TableHead className="text-right">Jami, s</TableHead>
              <TableHead className="text-right">Xato</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.endpoints.length ? (
              data.endpoints.slice(0, 25).map((e) => (
                <TableRow key={`${e.method} ${e.route}`}>
                  <TableCell className="font-mono text-xs">
                    {e.method} {e.route}
                  </TableCell>
                  <TableCell className="num text-right">{e.count}</TableCell>
                  <TableCell className="num text-right">
                    {Math.round(e.p50_ms)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "num text-right",
                      e.p95_ms >= SLOW_MS && "font-semibold text-red-600",
                    )}
                  >
                    {Math.round(e.p95_ms)}
                  </TableCell>
                  <TableCell className="num text-right">
                    {Math.round(e.max_ms)}
                  </TableCell>
                  <TableCell className="num text-right">{e.total_s}</TableCell>
                  <TableCell
                    className={cn(
                      "num text-right",
                      e.errors > 0 && "text-red-600",
                    )}
                  >
                    {e.errors || ""}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <EmptyRow colSpan={7}>Bu oynada so'rov yo'q</EmptyRow>
            )}
          </TableBody>
        </Table>
      </section>

      <section>
        <h2 className="mb-1 font-semibold">Event loop bloklari</h2>
        <p className="mb-2 text-sm text-muted-foreground">
          Blok paytida o'sha server ishchisidagi HAMMA so'rov kutadi — boshqa
          postlarning chek va skani ham. Eng uzoq ishlab turgan so'rov odatda
          aybdor.
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Vaqt</TableHead>
              <TableHead className="text-right">Blok, ms</TableHead>
              <TableHead>Ishlab turgan so'rovlar (ms)</TableHead>
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
                      i.lag_ms >= SLOW_MS && "font-semibold text-red-600",
                    )}
                  >
                    {i.lag_ms}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {i.inflight.length
                      ? i.inflight
                          .map((f) => `${f.path} (${f.elapsed_ms})`)
                          .join(" · ")
                      : "—"}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <EmptyRow colSpan={3}>Bu oynada blok bo'lmagan</EmptyRow>
            )}
          </TableBody>
        </Table>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">
          Bazadagi eng og'ir so'rovlar (jami vaqt bo'yicha)
        </h2>
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
                  <TableCell className="num text-right">{q.mean_ms}</TableCell>
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
