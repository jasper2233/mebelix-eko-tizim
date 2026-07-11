import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowDown, ArrowUp, Search } from "lucide-react"
import { useMemo, useState } from "react"

import { OrdersService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { AddOrder } from "@/components/Orders/AddOrder"
import { Input } from "@/components/ui/input"
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
import useCurrentUser from "@/hooks/useCurrentUser"
import {
  formatDate,
  formatMoney,
  PRIORITY_LABELS,
  PRIORITY_TEXT_CLASSES,
} from "@/lib/mes"
import { getOrdersQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/orders/")({
  component: OrdersPage,
  head: () => ({ meta: [{ title: "Buyurtmalar | MebeliX" }] }),
})

type SortKey = "created_at" | "deadline" | "priority" | "amount" | "left"
const PRIORITY_RANK: Record<string, number> = {
  low: 0,
  medium: 1,
  high: 2,
  urgent: 3,
}

const TABS = [
  { value: "", label: "Hammasi" },
  { value: "draft", label: "Qoralama" },
  { value: "technical_review", label: "Texnologda" },
  { value: "production", label: "Jarayonda" },
  { value: "completed", label: "Tayyor (sexda)" },
  { value: "delivered", label: "Topshirilgan" },
  { value: "cancelled", label: "Bekor qilingan" },
]

function OrdersPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState("")
  const [search, setSearch] = useState("")
  const { data, isLoading } = useQuery(
    getOrdersQueryOptions({ status, search }),
  )
  const { data: counts } = useQuery({
    queryKey: ["orders", "status-counts"],
    queryFn: () => OrdersService.readOrderStatusCounts(),
    refetchInterval: 30_000,
  })
  const tabCount = (value: string) =>
    value === ""
      ? Object.values(counts ?? {}).reduce((a, b) => a + b, 0)
      : (counts?.[value] ?? 0)

  const [sort, setSort] = useState<{ key: SortKey; desc: boolean } | null>(null)
  const toggleSort = (key: SortKey) =>
    setSort((s) =>
      s?.key === key
        ? s.desc
          ? null
          : { key, desc: true }
        : { key, desc: false },
    )

  // ponytail: client-side sort — reestr bitta sahifaga sig'adi (limit 100); oshsa server-side sort param qo'shiladi
  const rows = useMemo(() => {
    const list = data?.data ?? []
    if (!sort) return list
    const val = (o: (typeof list)[number]): number => {
      switch (sort.key) {
        case "created_at":
          return new Date(o.created_at).getTime()
        case "deadline":
          return o.deadline
            ? new Date(o.deadline).getTime()
            : Number.POSITIVE_INFINITY
        case "priority":
          return PRIORITY_RANK[o.priority] ?? 0
        case "amount":
          return o.amount != null ? Number(o.amount) : Number.NEGATIVE_INFINITY
        case "left":
          return o.amount != null
            ? Number(o.amount) - Number(o.advance_payment ?? 0)
            : Number.NEGATIVE_INFINITY
      }
    }
    return [...list].sort((a, b) =>
      sort.desc ? val(b) - val(a) : val(a) - val(b),
    )
  }, [data, sort])

  const SortHead = ({
    label,
    k,
    className,
  }: {
    label: string
    k: SortKey
    className?: string
  }) => (
    <TableHead className={className}>
      <button
        type="button"
        onClick={() => toggleSort(k)}
        className="inline-flex items-center gap-1 hover:text-foreground"
      >
        {label}
        {sort?.key === k &&
          (sort.desc ? (
            <ArrowDown className="size-3.5" />
          ) : (
            <ArrowUp className="size-3.5" />
          ))}
      </button>
    </TableHead>
  )
  const { currentUser } = useCurrentUser()
  const canCreate =
    currentUser?.is_superuser ||
    currentUser?.role === "admin" ||
    currentUser?.role === "manager"
  // Qoralama va bekor qilinganlar texnologga ko'rinmaydi (backend ham filtrlaydi):
  // buyurtma texnolog navbatiga confirm'dan keyin tushadi
  const isTexnolog =
    currentUser?.role === "texnolog" && !currentUser.is_superuser
  const visibleTabs = isTexnolog
    ? TABS.filter((t) => t.value !== "cancelled" && t.value !== "draft")
    : TABS

  return (
    <div>
      <PageHeader
        title="Buyurtmalar reestri"
        description="Tizimdagi barcha shartnomalar va ishlab chiqarish holati"
        actions={canCreate ? <AddOrder /> : undefined}
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={status} onValueChange={setStatus}>
          <TabsList className="h-9 flex-wrap">
            {visibleTabs.map((t) => (
              <TabsTrigger key={t.value} value={t.value} className="text-xs">
                {t.label}
                {counts && tabCount(t.value) > 0 && (
                  <span className="num ml-1.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                    {tabCount(t.value)}
                  </span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative ml-auto w-full max-w-xs">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            placeholder="Raqam, nom yoki mijoz"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Buyurtma</TableHead>
                <TableHead>Kontragent</TableHead>
                <SortHead label="Ochilgan" k="created_at" />
                <SortHead label="Topshirish sanasi" k="deadline" />
                <SortHead label="Prioritet" k="priority" />
                <SortHead
                  label="Umumiy narx"
                  k="amount"
                  className="text-right"
                />
                <SortHead
                  label="Qoldiq to'lov"
                  k="left"
                  className="text-right"
                />
                <TableHead>Holat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length ? (
                rows.map((o) => (
                  <TableRow
                    key={o.id}
                    className="cursor-pointer"
                    onClick={() =>
                      navigate({
                        to: "/orders/$orderId",
                        params: { orderId: String(o.id) },
                      })
                    }
                  >
                    <TableCell>
                      <Link
                        to="/orders/$orderId"
                        params={{ orderId: String(o.id) }}
                        className="block font-semibold text-primary hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {o.number}
                        {o.project_name && (
                          <span className="block text-xs font-normal text-muted-foreground">
                            {o.project_name}
                          </span>
                        )}
                      </Link>
                    </TableCell>
                    <TableCell>{o.client_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(o.created_at)}
                    </TableCell>
                    <TableCell className="num">
                      {formatDate(o.deadline)}
                    </TableCell>
                    <TableCell>
                      <span
                        className={
                          PRIORITY_TEXT_CLASSES[o.priority] ??
                          "text-muted-foreground"
                        }
                      >
                        {PRIORITY_LABELS[o.priority] ?? o.priority}
                      </span>
                    </TableCell>
                    <TableCell className="num text-right">
                      {formatMoney(o.amount)}
                    </TableCell>
                    <TableCell className="num text-right">
                      {o.amount != null
                        ? formatMoney(
                            Number(o.amount) - Number(o.advance_payment ?? 0),
                          )
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={o.status} />
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="h-24 text-center text-muted-foreground"
                  >
                    Buyurtmalar topilmadi.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
