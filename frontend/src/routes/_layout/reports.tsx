// Hisobotlar: mahsuldorlik, buyurtmalar holati, material sarfi + Excel eksport.

import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Download } from "lucide-react"
import { type ReactNode, useState } from "react"

import type { OrderReportRow } from "@/client"
import { ReportsService } from "@/client"
import { client } from "@/client/client.gen"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
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
import {
  formatDate,
  groupThousands,
  isManagement,
  ORDER_STATUS_LABELS,
} from "@/lib/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/reports")({
  component: ReportsPage,
  // Sidebar ko'rinishi bilan bir xil rollar to'plami (lib/mes)
  beforeLoad: requireAccess(isManagement),
  head: () => ({ meta: [{ title: "Hisobotlar | MebeliX" }] }),
})

type Kind = "productivity" | "orders" | "materials"

// Sana LOKAL komponentlardan (`toISOString` UTC ga siljitib kunni buzardi).
function isoOf(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

// Backend bo'sh filtrda oxirgi 30 kunni qo'llaydi (`_range`: bugun-29 … bugun, inklyuziv), Excel ham.
// DatePicker'lar shu default bilan boshlanadi (bo'sh filtr "hamma vaqt" emas).
function isoDay(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return isoOf(d)
}

// Tez tanlov: backend default (30 kun) + kalendar oylar — menejer «shu oy»ni
// ikki DatePicker bilan terib o'tirmasin.
const PRESETS: { label: string; range: () => [string, string] }[] = [
  { label: "30 kun", range: () => [isoDay(-29), isoDay()] },
  {
    label: "Bu oy",
    range: () => {
      const d = new Date()
      return [isoOf(new Date(d.getFullYear(), d.getMonth(), 1)), isoOf(d)]
    },
  },
  {
    label: "O'tgan oy",
    range: () => {
      const d = new Date()
      return [
        isoOf(new Date(d.getFullYear(), d.getMonth() - 1, 1)),
        isoOf(new Date(d.getFullYear(), d.getMonth(), 0)),
      ]
    },
  },
]

function ReportsPage() {
  const [kind, setKind] = useState<Kind>("productivity")
  const [dateFrom, setDateFrom] = useState(() => isoDay(-29))
  const [dateTo, setDateTo] = useState(() => isoDay())

  const params = {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  }
  // Teskari oraliq backend'da bo'sh javob beradi — «buyurtmalar yo'q» deb
  // yolg'on ko'rsatmaslik uchun so'rovga bormaymiz, sababini aytamiz.
  const invalid = !!dateFrom && !!dateTo && dateFrom > dateTo
  const presetActive = (p: (typeof PRESETS)[number]) => {
    const [f, t] = p.range()
    return f === dateFrom && t === dateTo
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
            disabled={exportXlsx.isPending || invalid}
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
        <div className="ml-auto flex flex-wrap items-center gap-2 text-sm">
          {PRESETS.map((p) => (
            <Button
              key={p.label}
              size="sm"
              variant={presetActive(p) ? "secondary" : "ghost"}
              onClick={() => {
                const [f, t] = p.range()
                setDateFrom(f)
                setDateTo(t)
              }}
            >
              {p.label}
            </Button>
          ))}
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

      {invalid ? (
        <p className="text-sm text-destructive">
          Boshlanish sanasi tugash sanasidan keyin — oraliqni to'g'rilang.
        </p>
      ) : (
        <>
          {kind === "productivity" && <ProductivityTable params={params} />}
          {kind === "orders" && <OrdersTable params={params} />}
          {kind === "materials" && <MaterialsTable params={params} />}
        </>
      )}
    </div>
  )
}

type RangeParams = { date_from?: string; date_to?: string }

// Sarlavha ostidagi bir qatorlik xulosa — jadvalga qaramay davr manzarasi.
function Summary({ children }: { children: ReactNode }) {
  return <p className="mb-3 text-sm text-muted-foreground">{children}</p>
}

function ProductivityTable({ params }: { params: RangeParams }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "productivity", params],
    queryFn: async () =>
      (await ReportsService.reportProductivity({ query: params })).data,
  })
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />
  const rows = data?.employees ?? []
  const total = rows.reduce((s, e) => s + e.total_scans, 0)
  return (
    <>
      <Summary>
        {rows.length} hodim · {groupThousands(String(total))} skan
      </Summary>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="hidden md:table-cell">#</TableHead>
            <TableHead>Hodim</TableHead>
            <TableHead className="hidden md:table-cell">Lavozim</TableHead>
            {/* `title` — ustun ma'nosi sarlavhaning o'zida (Mijozlar ABC kabi):
                «skan» nima, «faol soat» nima — raqam yolg'iz o'zi tushuntirmaydi */}
            <TableHead
              className="text-right"
              title="1 skan = 1 detal-operatsiya; bekor qilinganlar sanalmaydi"
            >
              Skanlar
            </TableHead>
            <TableHead
              className="text-right"
              title="Hodimning davrdagi jami skanlardagi ulushi"
            >
              Ulush
            </TableHead>
            <TableHead
              className="hidden md:table-cell text-right"
              title="Kamida bitta skan bo'lgan kunlar"
            >
              Faol kunlar
            </TableHead>
            <TableHead
              className="hidden md:table-cell text-right"
              title="Skanlar ÷ faol kunlar"
            >
              Kuniga
            </TableHead>
            <TableHead
              className="hidden md:table-cell text-right"
              title="Skanlar ÷ kamida bitta skan bo'lgan soatlar — ish tempi, smena uzunligi emas"
            >
              Faol soatiga
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length ? (
            rows.map((e, i) => (
              <TableRow key={e.employee_id}>
                <TableCell className="hidden md:table-cell num text-muted-foreground">
                  {i + 1}
                </TableCell>
                <TableCell className="font-medium">{e.full_name}</TableCell>
                <TableCell className="hidden md:table-cell">
                  {e.position ?? "—"}
                </TableCell>
                <TableCell className="num text-right font-semibold">
                  {groupThousands(String(e.total_scans))}
                </TableCell>
                <TableCell className="num text-right text-muted-foreground">
                  {total
                    ? `${Math.round((e.total_scans / total) * 100)}%`
                    : "—"}
                </TableCell>
                <TableCell className="hidden md:table-cell num text-right">
                  {e.active_days}
                </TableCell>
                <TableCell className="hidden md:table-cell num text-right">
                  {e.per_day}
                </TableCell>
                <TableCell className="hidden md:table-cell num text-right">
                  {e.per_hour}
                </TableCell>
              </TableRow>
            ))
          ) : (
            <EmptyRow colSpan={8}>Tanlangan davrda skanlar yo'q.</EmptyRow>
          )}
        </TableBody>
      </Table>
    </>
  )
}

const ACTIVE_STATUSES = new Set(["draft", "technical_review", "production"])

// Muddatdan necha kun o'tgani. Backend `overdue` faqat FAOL buyurtma uchun —
// kech topshirilgan buyurtma hisobotda toza ko'rinardi (prod nusxada 10 tadan
// 9 tasi shu holatda edi). Tugagan bo'lsa — topshirilgan/tayyor sanasi bilan,
// faol bo'lsa — bugun bilan solishtiriladi; bekor qilingan hisoblanmaydi.
function lateDays(r: OrderReportRow): number {
  if (!r.deadline) return 0
  const end =
    r.delivered_at ??
    r.completed_at ??
    (ACTIVE_STATUSES.has(r.status) ? new Date().toISOString() : null)
  if (!end) return 0
  const endDay = Date.parse(isoOf(new Date(end)))
  return Math.round((endDay - Date.parse(r.deadline)) / 864e5)
}

// Ishga tushgandan tayyor bo'lguncha — menejer ikki vaqt tamg'asidan
// hisoblab o'tirmasin.
function duration(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  if (!start || !end) return "—"
  const h = (new Date(end).getTime() - new Date(start).getTime()) / 36e5
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} daq`
  if (h < 24) return `${Math.round(h)} soat`
  return `${(h / 24).toFixed(1)} kun`
}

function OrdersTable({ params }: { params: RangeParams }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "orders", params],
    queryFn: async () =>
      (await ReportsService.reportOrders({ query: params })).data,
  })
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />
  const rows = data?.rows ?? []
  // Bekor sababi ustuni — sabab bor bo'lgandagina: aks holda 9 ustunlik
  // jadvalda doim bo'sh ustun turardi
  const withReason = rows.some((r) => r.cancel_reason)
  const byStatus = new Map<string, number>()
  for (const r of rows)
    byStatus.set(r.status, (byStatus.get(r.status) ?? 0) + 1)
  const late = rows.filter((r) => lateDays(r) > 0).length
  return (
    <>
      <Summary>
        {rows.length} ta buyurtma
        {Object.keys(ORDER_STATUS_LABELS)
          .filter((s) => byStatus.has(s))
          .map((s) => (
            <span key={s}>
              {" · "}
              {byStatus.get(s)} {ORDER_STATUS_LABELS[s].toLowerCase()}
            </span>
          ))}
        {late > 0 && (
          <span className="font-semibold text-red-700">
            {" "}
            · {late} kechikkan
          </span>
        )}
      </Summary>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Raqam</TableHead>
            <TableHead>Mijoz</TableHead>
            <TableHead className="hidden md:table-cell">Holat</TableHead>
            <TableHead className="hidden md:table-cell">Ochilgan</TableHead>
            <TableHead>Muddat</TableHead>
            <TableHead className="hidden md:table-cell">
              Ishga tushgan
            </TableHead>
            <TableHead className="hidden md:table-cell">Tayyor</TableHead>
            <TableHead className="hidden md:table-cell">Topshirilgan</TableHead>
            <TableHead
              className="hidden md:table-cell text-right"
              title="Ishga tushgandan tayyor bo'lguncha"
            >
              Ishlab chiqarish
            </TableHead>
            {withReason && <TableHead>Bekor sababi</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length ? (
            rows.map((r) => {
              const lateBy = lateDays(r)
              return (
                <TableRow key={r.number}>
                  <TableCell className="font-semibold">{r.number}</TableCell>
                  <TableCell
                    className="max-w-[110px] truncate md:max-w-[220px]"
                    title={r.client_name}
                  >
                    {r.client_name}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <StatusBadge status={r.status} />
                  </TableCell>
                  <TableCell className="hidden md:table-cell num">
                    {formatDate(r.created_at)}
                  </TableCell>
                  <TableCell className="num whitespace-normal md:whitespace-nowrap">
                    {formatDate(r.deadline)}{" "}
                    {/* Faol va kechikkan — qizil chip (hozir muammo); tugagan,
                        lekin kech — sariq matn (tarix, bugungi muammo emas) */}
                    {lateBy > 0 &&
                      (ACTIVE_STATUSES.has(r.status) ? (
                        <span className="ml-1.5 whitespace-nowrap rounded-sm bg-red-100 px-1.5 py-0.5 text-2xs font-bold text-red-700">
                          {lateBy} KUN KECH
                        </span>
                      ) : (
                        <span className="ml-1.5 whitespace-nowrap text-2xs font-semibold text-amber-700">
                          {lateBy} kun kech
                        </span>
                      ))}
                  </TableCell>
                  <TableCell className="hidden md:table-cell num">
                    {formatDate(r.production_started_at)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell num">
                    {formatDate(r.completed_at)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell num">
                    {formatDate(r.delivered_at)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell num text-right">
                    {duration(r.production_started_at, r.completed_at)}
                  </TableCell>
                  {withReason && (
                    <TableCell
                      className="max-w-[220px] truncate text-xs text-muted-foreground"
                      title={r.cancel_reason ?? undefined}
                    >
                      {r.cancel_reason ?? ""}
                    </TableCell>
                  )}
                </TableRow>
              )
            })
          ) : (
            <EmptyRow colSpan={withReason ? 10 : 9}>
              Tanlangan davrda buyurtmalar yo'q.
            </EmptyRow>
          )}
        </TableBody>
      </Table>
    </>
  )
}

// Backend `material_usage[].kind` uch qiymatli — reports.py dagi _KIND_LABELS oynasi.
// Tartib ham shu: list → kromka → furnitura.
const MATERIAL_KINDS: [string, string][] = [
  ["sheet", "List"],
  ["band", "Kromka"],
  ["hardware", "Furnitura"],
]

// 1074.04 → "1 074.04"; ko'pi bilan 2 kasr
function formatQty(n: number): string {
  const [int, frac] = String(Math.round(n * 100) / 100).split(".")
  return groupThousands(int) + (frac ? `.${frac}` : "")
}

function MaterialsTable({ params }: { params: RangeParams }) {
  const [q, setQ] = useState("")
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["reports", "materials", params],
    queryFn: async () =>
      (await ReportsService.reportMaterials({ query: params })).data,
  })
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError) return <QueryError onRetry={() => refetch()} />
  const rows = data?.rows ?? []
  const needle = q.trim().toLowerCase()
  const filtered = needle
    ? rows.filter((r) =>
        `${r.name} ${r.code ?? ""}`.toLowerCase().includes(needle),
      )
    : rows
  // Tur bo'yicha guruh: list (dona) va kromka (metr) bitta ro'yxatda miqdor
  // bo'yicha aralash saralanardi — metr bilan donani solishtirib bo'lmaydi.
  // Sahifalash o'rniga qidiruv: 30 kunda ~120 qator, menejer aniq materialni izlaydi.
  const groups = MATERIAL_KINDS.map(([kind, label]) => ({
    kind,
    label,
    rows: filtered.filter((r) => r.kind === kind),
  })).filter((g) => g.rows.length)
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Summary>
          {rows.length} material
          {MATERIAL_KINDS.map(([kind, label]) => {
            const n = rows.filter((r) => r.kind === kind).length
            return n ? (
              <span key={kind}>
                {" · "}
                {n} {label.toLowerCase()}
              </span>
            ) : null
          })}
          {" · "}davr — .project fayli yuklangan sana bo'yicha, miqdor — Giblab
          rejasi
        </Summary>
        <SearchInput
          value={q}
          onChange={setQ}
          placeholder="Material nomi yoki kodi"
          className="ml-auto w-64"
        />
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Material</TableHead>
            <TableHead
              className="text-right"
              title="Giblab loyihasidagi reja miqdori"
            >
              Jami sarf
            </TableHead>
            <TableHead
              className="text-right"
              title="Shu material ishlatilgan buyurtmalar soni"
            >
              Buyurtmalar
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {groups.length ? (
            groups.map((g) => (
              <GroupRows key={g.kind} label={g.label} rows={g.rows} />
            ))
          ) : (
            <EmptyRow colSpan={3}>
              {rows.length
                ? "Mos material topilmadi."
                : "Tanlangan davrda material sarfi yo'q (fayl yuklangan buyurtmalar hisobga olinadi)."}
            </EmptyRow>
          )}
        </TableBody>
      </Table>
    </>
  )
}

type MaterialRow = {
  name: string
  code?: string | null
  unit: string
  total: number
  orders: number
}

function GroupRows({ label, rows }: { label: string; rows: MaterialRow[] }) {
  const sum = rows.reduce((s, r) => s + r.total, 0)
  return (
    <>
      <TableRow className="bg-muted/40 hover:bg-muted/40">
        <TableCell
          colSpan={3}
          className="py-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
        >
          {label} · {rows.length} ta · {formatQty(sum)} {rows[0].unit}
        </TableCell>
      </TableRow>
      {rows.map((r) => (
        <TableRow key={`${r.code ?? r.name}`}>
          <TableCell className="font-medium">
            {r.name}
            {r.code && (
              <span className="ml-2 text-muted-foreground">{r.code}</span>
            )}
          </TableCell>
          <TableCell className="num whitespace-nowrap text-right font-semibold">
            {formatQty(r.total)}{" "}
            <span className="font-normal text-muted-foreground">{r.unit}</span>
          </TableCell>
          <TableCell className="num text-right">{r.orders}</TableCell>
        </TableRow>
      ))}
    </>
  )
}
