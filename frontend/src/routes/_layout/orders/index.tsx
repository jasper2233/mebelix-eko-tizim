import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowDown, ArrowUp, ChevronsUpDown, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { toast } from "sonner"

import type { OrderStatus } from "@/client"
import { type OrderRead, OrdersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { RowOpenCell } from "@/components/Common/RowOpen"
import { SearchInput } from "@/components/Common/SearchInput"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { AddOrder } from "@/components/Orders/AddOrder"
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useDebounced } from "@/hooks/useDebounced"
import {
  deadlineTone,
  formatDate,
  formatMoney,
  isManager,
  isSuperuser,
  ORDER_STATUS_LABELS,
  PRIORITY_LABELS,
  PRIORITY_RANK,
  PRIORITY_TEXT_CLASSES,
  remainingPayment,
  TERMINAL_STATUSES,
} from "@/lib/mes"
import {
  getOrderStatusCountsQueryOptions,
  getOrdersQueryOptions,
  PAGE_SIZE,
} from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/orders/")({
  component: OrdersPage,
  head: () => ({ meta: [{ title: "Buyurtmalar | MebeliX" }] }),
  // Boshqaruv panelidagi «Hammasi» havolalari to'g'ri tabga tushsin
  // (`/orders?status=completed`); noma'lum qiymat — «Hammasi».
  validateSearch: (s: Record<string, unknown>): { status?: OrderStatus } =>
    typeof s.status === "string" && s.status in ORDER_STATUS_LABELS
      ? { status: s.status as OrderStatus }
      : {},
})

type SortKey = "created_at" | "deadline" | "priority" | "amount" | "left"

const TABS: { value: OrderStatus | ""; label: string }[] = [
  { value: "", label: "Hammasi" },
  { value: "draft", label: "Qoralama" },
  { value: "technical_review", label: "Texnologda" },
  { value: "production", label: "Jarayonda" },
  { value: "completed", label: "Tayyor (tsexda)" },
  { value: "delivered", label: "Topshirilgan" },
  { value: "cancelled", label: "Bekor qilingan" },
]

/**
 * Saralanadigan ustun sarlavhasi. Modul darajasida — avval `OrdersPage` ichida
 * e'lon qilingani uchun har renderda YANGI komponent tipi tug'ilib, beshta
 * sarlavha unmount/remount bo'lardi (fokus va tooltip ham yo'qolardi).
 */
function SortHead({
  label,
  k,
  sort,
  onToggle,
  className,
}: {
  label: string
  k: SortKey
  sort: { key: SortKey; desc: boolean } | null
  onToggle: (k: SortKey) => void
  className?: string
}) {
  const activeSort = sort?.key === k ? sort : null
  return (
    <TableHead
      className={className}
      aria-sort={
        activeSort ? (activeSort.desc ? "descending" : "ascending") : "none"
      }
    >
      {/* `uppercase` shu yerda ham: Tailwind preflight tugmada text-transform'ni
          o'chiradi, shuning uchun saralanadigan sarlavhalar boshqalaridan farqli
          (kichik harf) chiqardi. Nofaol holatda xira ikonka — saralash
          mumkinligi ko'rinsin. */}
      <button
        type="button"
        onClick={() => onToggle(k)}
        className="inline-flex items-center gap-1 rounded-sm uppercase tracking-wider hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
      >
        {label}
        {activeSort ? (
          activeSort.desc ? (
            <ArrowDown className="size-3.5" />
          ) : (
            <ArrowUp className="size-3.5" />
          )
        ) : (
          <ChevronsUpDown className="size-3 opacity-40" />
        )}
      </button>
    </TableHead>
  )
}

/** Faol buyurtmada muddat ohangi: o'tgan — qizil, bugun — amber (tablo/terminal
 *  bilan bir xil qoida). Yopilgan buyurtmada rang yo'q — u endi muddat emas. */
function deadlineClass(o: {
  deadline?: string | null
  status: OrderStatus
}): string {
  if (TERMINAL_STATUSES.includes(o.status)) return ""
  const tone = deadlineTone(o.deadline)
  if (tone === "overdue") return "font-semibold text-destructive"
  if (tone === "today") return "font-semibold text-amber-600"
  return ""
}

function OrdersPage() {
  const navigate = useNavigate()
  const initialStatus = Route.useSearch().status ?? ""
  const [status, setStatus] = useState<OrderStatus | "">(initialStatus)
  const [search, setSearch] = useState("")
  const debounced = useDebounced(search.trim())
  const { data, isLoading, isError, refetch } = useQuery({
    ...getOrdersQueryOptions({ status, search: debounced }),
    placeholderData: keepPreviousData,
  })
  const { data: counts } = useQuery(getOrderStatusCountsQueryOptions())
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
            ? remainingPayment(o)
            : Number.NEGATIVE_INFINITY
      }
    }
    return [...list].sort((a, b) =>
      sort.desc ? val(b) - val(a) : val(a) - val(b),
    )
  }, [data, sort])

  const { currentUser } = useCurrentUser()
  const canCreate = isManager(currentUser)
  // Qatordan o'chirish: qoralama — menejer, bekor qilingan (tirik skansiz) —
  // superuser. Har birini sahifasiga kirib tekshirish shart emas.
  const queryClient = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState<OrderRead | null>(null)
  const remove = useMutation({
    mutationFn: (orderId: number) =>
      OrdersService.deleteOrder({ path: { order_id: orderId } }),
    onSuccess: (r) => {
      toast.success(r.data?.message ?? "O'chirildi")
      setDeleteTarget(null)
      queryClient.invalidateQueries({ queryKey: ["orders"] })
    },
    onError: handleError,
  })
  const canDeleteRow = (o: OrderRead) =>
    (o.status === "draft" && canCreate) ||
    (o.status === "cancelled" && isSuperuser(currentUser))
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
      {/* Telefonda (390 px) holat tablari 3-2-2 bo'lib tasodifiy buqilardi.
          Endi `<md`: tablar BIR qatorda yonga skroll (segment naqshi —
          iOS/Android), qidiruv o'z qatorida to'liq kenglik. `md+`: avvalgidek
          — tablar buqiladi, qidiruv o'ngda. */}
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
        <Tabs
          value={status}
          onValueChange={(v) => setStatus(v as OrderStatus | "")}
          className="min-w-0 max-w-full"
        >
          <TabsList className="h-auto min-h-9 max-w-full flex-nowrap justify-start overflow-x-auto md:flex-wrap md:justify-center [&>*]:shrink-0">
            {visibleTabs.map((t) => (
              <TabsTrigger key={t.value} value={t.value} className="text-xs">
                {t.label}
                {counts && tabCount(t.value) > 0 && (
                  <span className="num ml-1.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-2xs font-bold text-primary">
                    {tabCount(t.value)}
                  </span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <SearchInput
          className="w-full md:ml-auto md:max-w-xs"
          placeholder="Raqam, nom yoki mijoz"
          value={search}
          onChange={setSearch}
        />
      </div>
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Buyurtma</TableHead>
              <TableHead>Kontragent</TableHead>
              <SortHead
                sort={sort}
                onToggle={toggleSort}
                label="Ochilgan"
                k="created_at"
              />
              <SortHead
                sort={sort}
                onToggle={toggleSort}
                label="Topshirish sanasi"
                k="deadline"
              />
              <SortHead
                sort={sort}
                onToggle={toggleSort}
                label="Prioritet"
                k="priority"
              />
              <SortHead
                sort={sort}
                onToggle={toggleSort}
                label="Umumiy narx"
                k="amount"
                className="text-right"
              />
              <SortHead
                sort={sort}
                onToggle={toggleSort}
                label="Qoldiq to'lov"
                k="left"
                className="text-right"
              />
              <TableHead>Holat</TableHead>
              <TableHead className="w-10" aria-label="Amallar" />
              {/* Strelka ustuni — qator sahifa ochadi */}
              <TableHead className="w-8" />
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
                        <span className="block max-w-[220px] truncate text-xs font-normal text-muted-foreground">
                          {o.project_name}
                        </span>
                      )}
                    </Link>
                  </TableCell>
                  <TableCell
                    className="max-w-[240px] truncate"
                    title={o.client_name}
                  >
                    {o.client_name}
                  </TableCell>
                  <TableCell className="num text-muted-foreground">
                    {formatDate(o.created_at)}
                  </TableCell>
                  <TableCell className={`num ${deadlineClass(o)}`}>
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
                    {/* Qarz yo'q — "0 so'm" emas, so'z: menejer ustunni qarz
                        bo'yicha ko'zdan kechiradi, nol raqam ko'zga tashlanmaydi */}
                    {o.amount == null ? (
                      "—"
                    ) : remainingPayment(o) <= 0 ? (
                      <span className="text-muted-foreground">To'langan</span>
                    ) : (
                      formatMoney(remainingPayment(o))
                    )}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={o.status} />
                  </TableCell>
                  <TableCell className="pr-2">
                    {canDeleteRow(o) && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                        // Tirik skani bor bekor qilingan buyurtma — backend 403 bilan
                        // sababini aytadi (toast); oldindan hisoblash ortiqcha edi
                        title="O'chirish"
                        onClick={(e) => {
                          e.stopPropagation()
                          setDeleteTarget(o)
                        }}
                      >
                        <Trash2 />
                      </Button>
                    )}
                  </TableCell>
                  <RowOpenCell />
                </TableRow>
              ))
            ) : (
              <EmptyRow colSpan={10}>
                {debounced
                  ? `"${debounced}" bo'yicha buyurtma topilmadi.`
                  : status
                    ? "Bu holatda buyurtma yo'q."
                    : 'Hali buyurtma yo\'q — birinchisini "Yangi buyurtma" bilan oching.'}
              </EmptyRow>
            )}
          </TableBody>
        </Table>
      )}
      {/* Reestr bitta sahifa (PAGE_SIZE) — chegaraga yetganda jim kesilmasin */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(v) => !v && setDeleteTarget(null)}
        title={
          deleteTarget?.status === "draft"
            ? "Qoralamani o'chirish"
            : "Buyurtmani butunlay o'chirish"
        }
        description={
          deleteTarget?.status === "draft"
            ? `${deleteTarget?.number} qoralamasi o'chiriladi. Raqam band qoladi (qayta berilmaydi), amal audit logda saqlanadi.`
            : `${deleteTarget?.number} — buyurtma, uning detallari, marshrutlari va diskdagi fayllari BUTUNLAY o'chadi. Bu amalni QAYTARIB BO'LMAYDI. Bekor qilish tarixi (audit izi) saqlanadi.`
        }
        confirmText={
          deleteTarget?.status === "draft" ? "O'chirish" : "BUTUNLAY O'CHIRISH"
        }
        cancelText="Ortga"
        loading={remove.isPending}
        onConfirm={() => deleteTarget && remove.mutate(deleteTarget.id)}
      />
      {rows.length >= PAGE_SIZE && (
        <p className="mt-3 text-center text-xs text-muted-foreground">
          Faqat oxirgi {PAGE_SIZE} ta buyurtma ko'rsatilmoqda — kerakligini
          qidiruv yoki holat bo'yicha toping.
        </p>
      )}
    </div>
  )
}
