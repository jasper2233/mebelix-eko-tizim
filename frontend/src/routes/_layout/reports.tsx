// Hisobotlar (TZ 11): mahsuldorlik, buyurtmalar holati, material sarfi + Excel eksport.

import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Download } from "lucide-react"
import { useState } from "react"

import { ReportsService } from "@/client"
import { client } from "@/client/client.gen"
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
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/reports")({
  component: ReportsPage,
  // Sidebar ko'rinishi bilan bir xil rollar to'plami (lib/mes)
  beforeLoad: requireAccess(isManagement),
  head: () => ({ meta: [{ title: "Hisobotlar | MebeliX" }] }),
})

type Kind = "productivity" | "orders" | "materials"

// Backend bo'sh filtrda jimgina oxirgi 30 kunni qo'llaydi (reports.py `_range`:
// bugun-29 … bugun, chegaralar inklyuziv),
// Excel eksporti ham aynan shu oraliqni oladi. Shuning uchun DatePicker'lar
// o'sha default bilan boshlanadi — aks holda menejer bo'sh filtrni "hamma vaqt"
// deb o'ylaydi. Sana LOKAL komponentlardan quriladi (DatePicker bilan bir xil).
function isoDay(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function ReportsPage() {
  const [kind, setKind] = useState<Kind>("productivity")
  const [dateFrom, setDateFrom] = useState(() => isoDay(-29))
  const [dateTo, setDateTo] = useState(() => isoDay())

  const params = {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }
  // Eksport oddiy `<a download>` emas, `client.instance` orqali ketadi: shunda
  // silent-refresh interceptor (main.tsx) ishlaydi va 401/500 sahifadan chiqib
  // ketgan xom JSON emas, o'zbekcha toast bo'lib ko'rinadi.
  const exportXlsx = useMutation({
    mutationFn: async () => {
      const q = new URLSearchParams({ format: "xlsx" })
      if (dateFrom) q.set("date_from", dateFrom)
      if (dateTo) q.set("date_to", dateTo)
      const res = await client.instance.get<Blob>(
        `/api/v1/reports/${kind}?${q}`,
        { responseType: "blob" },
      )
      const disposition = String(res.headers["content-disposition"] ?? "")
      const url = URL.createObjectURL(res.data)
      const a = document.createElement("a")
      a.href = url
      a.download =
        /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? `${kind}.xlsx`
      a.click()
      // Darhol revoke qilinsa ba'zi brauzerlarda yuklab olish boshlanmay qoladi
      setTimeout(() => URL.revokeObjectURL(url), 0)
    },
    onError: handleError,
  })

  return (
    <div>
      <PageHeader
        title="Hisobotlar"
        description="Mahsuldorlik, buyurtmalar holati va material sarfi"
        actions={
          <Button
            variant="outline"
            onClick={() => exportXlsx.mutate()}
            disabled={exportXlsx.isPending}
          >
            <Download /> Excel yuklash
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={kind} onValueChange={(v) => setKind(v as Kind)}>
          <TabsList className="h-9">
            <TabsTrigger value="productivity">Mahsuldorlik</TabsTrigger>
            <TabsTrigger value="orders">Buyurtmalar</TabsTrigger>
            <TabsTrigger value="materials">Material sarfi</TabsTrigger>
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
              <TableCell className="num text-right">{e.active_days}</TableCell>
              <TableCell className="num text-right">{e.per_day}</TableCell>
              <TableCell className="num text-right">{e.per_hour}</TableCell>
            </TableRow>
          ))
        ) : (
          <EmptyRow colSpan={7}>Tanlangan davrda scanlar yo'q.</EmptyRow>
        )}
      </TableBody>
    </Table>
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
  )
}

// Backend `material_usage[].kind` uch qiymatli — reports.py dagi _KIND_LABELS oynasi.
const MATERIAL_KIND_LABELS: Record<string, string> = {
  sheet: "List",
  band: "Kromka",
  hardware: "Furnitura",
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
              <TableCell>{MATERIAL_KIND_LABELS[r.kind] ?? r.kind}</TableCell>
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
  )
}
