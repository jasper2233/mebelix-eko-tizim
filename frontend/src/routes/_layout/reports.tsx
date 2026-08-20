// Hisobotlar (TZ 11): mahsuldorlik, buyurtmalar holati, material sarfi + Excel eksport.

import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Download } from "lucide-react"
import { useState } from "react"

import { ReportsService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Button } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { requireAccess } from "@/lib/guards"
import { formatDate, formatDateTime, isManagement } from "@/lib/mes"
import { API_BASE } from "@/utils"

export const Route = createFileRoute("/_layout/reports")({
  component: ReportsPage,
  // Sidebar ko'rinishi bilan bir xil rollar to'plami (lib/mes)
  beforeLoad: requireAccess(isManagement),
  head: () => ({ meta: [{ title: "Hisobotlar | MebeliX" }] }),
})

type Kind = "productivity" | "orders" | "materials" | "oee"

function ReportsPage() {
  const [kind, setKind] = useState<Kind>("productivity")
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")

  const params = {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }
  const exportUrl = () => {
    const q = new URLSearchParams({ format: "xlsx" })
    if (dateFrom) q.set("date_from", dateFrom)
    if (dateTo) q.set("date_to", dateTo)
    return `${API_BASE}/api/v1/reports/${kind}?${q}`
  }

  return (
    <div>
      <PageHeader
        title="Hisobotlar"
        description="Mahsuldorlik, buyurtmalar holati va material sarfi"
        actions={
          // OEE da Excel yo'q: hisobot ichma-ich (ish markazi -> to'xtash
          // sabablari) va uni yassi jadvalga aylantirish ma'noni yo'qotardi
          kind === "oee" ? undefined : (
            <Button asChild variant="outline">
              <a href={exportUrl()} download>
                <Download /> Excel yuklash
              </a>
            </Button>
          )
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={kind} onValueChange={(v) => setKind(v as Kind)}>
          <TabsList className="h-9">
            <TabsTrigger value="productivity">Mahsuldorlik</TabsTrigger>
            <TabsTrigger value="orders">Buyurtmalar</TabsTrigger>
            <TabsTrigger value="materials">Material sarfi</TabsTrigger>
            <TabsTrigger value="oee">OEE</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="ml-auto flex items-center gap-2 text-sm">
          <DatePicker
            value={dateFrom}
            onChange={setDateFrom}
            placeholder="Boshlanish"
            className="h-9"
            aria-label="Boshlanish sanasi"
          />
          <span className="text-muted-foreground">—</span>
          <DatePicker
            value={dateTo}
            onChange={setDateTo}
            placeholder="Tugash"
            className="h-9"
            aria-label="Tugash sanasi"
          />
        </div>
      </div>

      {kind === "productivity" && <ProductivityTable params={params} />}
      {kind === "orders" && <OrdersTable params={params} />}
      {kind === "materials" && <MaterialsTable params={params} />}
      {kind === "oee" && <OeeTable params={params} />}
    </div>
  )
}

type RangeParams = { date_from?: string; date_to?: string }

function ProductivityTable({ params }: { params: RangeParams }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "productivity", params],
    queryFn: async () =>
      (await ReportsService.reportProductivity({ query: params })).data,
  })
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>#</TableHead>
            <TableHead>Hodim</TableHead>
            <TableHead>Lavozim</TableHead>
            <TableHead className="text-right">Jami scan</TableHead>
            <TableHead className="text-right">Faol kunlar</TableHead>
            <TableHead className="text-right">Kuniga</TableHead>
            <TableHead className="text-right">Soatiga</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data?.employees.length ? (
            data.employees.map((e, i) => (
              <TableRow key={e.employee_id}>
                <TableCell className="num text-muted-foreground">
                  {i + 1}
                </TableCell>
                <TableCell className="font-medium">{e.full_name}</TableCell>
                <TableCell>{e.position ?? "—"}</TableCell>
                <TableCell className="num text-right font-semibold">
                  {e.total_scans}
                </TableCell>
                <TableCell className="num text-right">
                  {e.active_days}
                </TableCell>
                <TableCell className="num text-right">{e.per_day}</TableCell>
                <TableCell className="num text-right">{e.per_hour}</TableCell>
              </TableRow>
            ))
          ) : (
            <EmptyRow colSpan={7}>Tanlangan davrda scanlar yo'q.</EmptyRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

function OrdersTable({ params }: { params: RangeParams }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "orders", params],
    queryFn: async () =>
      (await ReportsService.reportOrders({ query: params })).data,
  })
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Raqam</TableHead>
            <TableHead>Mijoz</TableHead>
            <TableHead>Holat</TableHead>
            <TableHead>Topshirish sanasi</TableHead>
            <TableHead>Tayyor</TableHead>
            <TableHead>Topshirilgan</TableHead>
            <TableHead>Izoh</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data?.rows.length ? (
            data.rows.map((r) => (
              <TableRow key={r.number}>
                <TableCell className="font-semibold">{r.number}</TableCell>
                <TableCell
                  className="max-w-[220px] truncate"
                  title={r.client_name}
                >
                  {r.client_name}
                </TableCell>
                <TableCell>
                  <StatusBadge status={r.status} />
                </TableCell>
                <TableCell className="num">
                  {formatDate(r.deadline)}
                  {r.overdue && (
                    <span className="ml-1.5 rounded-sm bg-red-100 px-1.5 py-0.5 text-2xs font-bold text-red-700">
                      KECHIKKAN
                    </span>
                  )}
                </TableCell>
                <TableCell className="num">
                  {formatDateTime(r.completed_at)}
                </TableCell>
                <TableCell className="num">
                  {formatDateTime(r.delivered_at)}
                </TableCell>
                <TableCell className="max-w-[220px] truncate text-xs text-muted-foreground">
                  {r.cancel_reason ?? ""}
                </TableCell>
              </TableRow>
            ))
          ) : (
            <EmptyRow colSpan={7}>Tanlangan davrda buyurtmalar yo'q.</EmptyRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

function MaterialsTable({ params }: { params: RangeParams }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "materials", params],
    queryFn: async () =>
      (await ReportsService.reportMaterials({ query: params })).data,
  })
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Material</TableHead>
            <TableHead>Turi</TableHead>
            <TableHead className="text-right">Jami sarf</TableHead>
            <TableHead>Birlik</TableHead>
            <TableHead className="text-right">Buyurtmalar</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data?.rows.length ? (
            data.rows.map((r) => (
              <TableRow key={`${r.name}-${r.kind}`}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell>{r.kind === "sheet" ? "List" : "Kromka"}</TableCell>
                <TableCell className="num text-right font-semibold">
                  {Math.round(r.total * 100) / 100}
                </TableCell>
                <TableCell>{r.unit}</TableCell>
                <TableCell className="num text-right">{r.orders}</TableCell>
              </TableRow>
            ))
          ) : (
            <EmptyRow colSpan={5}>
              Tanlangan davrda material sarfi yo'q (fayl yuklangan buyurtmalar
              hisobga olinadi).
            </EmptyRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

/** Foizga o'girish. `null` — o'sha davrda reja bo'lmagan: "0%" yolg'on bo'lardi. */
function pct(value: number | null | undefined): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`
}

function hhmm(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return h ? `${h} s ${m} d` : `${m} d`
}

function OeeTable({ params }: { params: RangeParams }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "oee", params],
    queryFn: async () =>
      (await ReportsService.reportOee({ query: params })).data,
  })
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />
  const rows = data?.machines ?? []
  return (
    <div className="grid gap-3">
      {/* Hozircha OEE ning VAQT qismi. Performance ideal tezlik va ishlab
          chiqarilgan miqdorni, Quality esa brak hisobini talab qiladi. */}
      <p className="text-xs text-muted-foreground">
        Availability = ishlagan vaqt ÷ rejalashtirilgan vaqt. Tushlik va
        tanaffus rejadan ayriladi — ular yo'qotish emas.
      </p>
      {rows.length ? (
        rows.map((m) => {
          const losses = (m.stops ?? []).filter((s) => !s.excludes_planned)
          return (
            <div key={m.machine_id} className="rounded-lg border p-3">
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="font-semibold">{m.machine_name}</span>
                <span className="text-xs text-muted-foreground">
                  {m.post_name}
                </span>
                <span className="num ml-auto text-2xl font-black tabular-nums">
                  {pct(m.availability)}
                </span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {m.active_days} kun · reja {hhmm(m.planned_minutes)} · ishlagan{" "}
                {hhmm(m.run_minutes)}
                {m.planned_off_minutes > 0 &&
                  ` · rejadan ayrildi ${hhmm(m.planned_off_minutes)}`}
              </div>
              {losses.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {losses.map((s) => (
                    <span
                      key={s.reason}
                      className="rounded-md bg-destructive/10 px-2 py-1 text-xs text-destructive"
                    >
                      {s.reason} · {hhmm(s.minutes)}
                      {s.count > 1 && ` (${s.count})`}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })
      ) : (
        <p className="text-sm text-muted-foreground">
          Ish markazlari topilmadi.
        </p>
      )}
    </div>
  )
}
