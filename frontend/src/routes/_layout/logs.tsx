// Loglar (admin-only): audit_log jadvali kategoriya, qidiruv, sana filtri va
// sahifalash bilan. Skan/chek kabi jonli oqimlar ham shu yerga yoziladi —
// kim qachon nima qilganini bitta joydan topish uchun.

import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { X } from "lucide-react"
import { useState } from "react"

import { type AuditLogRead, AuditService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useDebounced } from "@/hooks/useDebounced"
import { requireAccess } from "@/lib/guards"
import { formatDateTime, isAdmin } from "@/lib/mes"
import {
  getBridgeAgentsQueryOptions,
  getMachinesQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"

export const Route = createFileRoute("/_layout/logs")({
  component: LogsPage,
  beforeLoad: requireAccess(isAdmin),
  head: () => ({ meta: [{ title: "Loglar | MebeliX" }] }),
})

const PAGE = 50

// Kategoriyalar = log_action module qiymatlari. Manba — backendda `module="..."`
// (grep bilan topiladi); yangi modul qo'shilsa shu ro'yxatga bitta qator qo'shiladi.
// Ro'yxat to'liq bo'lishi SHART: yo'q modul yozuvlari faqat filtrsiz ko'rinadi.
const CATEGORIES: { key: string; label: string }[] = [
  { key: "scan", label: "Skan" },
  { key: "print", label: "Chek" },
  { key: "sessions", label: "Smenalar" },
  { key: "orders", label: "Buyurtmalar" },
  { key: "pachka", label: "Pachkalar" },
  { key: "tmo", label: "TMO" },
  { key: "stock", label: "Materiallar ombori" },
  { key: "bridge_agents", label: "Printer agentlar" },
  { key: "employees", label: "Hodimlar" },
  { key: "users", label: "Foydalanuvchilar" },
  { key: "clients", label: "Mijozlar" },
  { key: "machines", label: "Ish markazlari" },
  { key: "posts", label: "Postlar" },
]
const CATEGORY_LABELS = Object.fromEntries(
  CATEGORIES.map((c) => [c.key, c.label]),
)

// Amal slug'lari — odam tilida (yangi amal qo'shilsa shu yerga bitta qator)
const ACTION_LABELS: Record<string, string> = {
  recorded: "yozildi",
  rejected: "rad etildi",
  cancelled: "bekor qilindi",
  label_sent: "chek yuborildi",
  label_cancelled: "chek bekor qilindi",
  created: "yaratildi",
  updated: "o'zgartirildi",
  deleted: "o'chirildi",
  started: "boshlandi",
  ended: "tugadi",
  machine_linked: "ish markazi bog'landi",
  can_print_changed: "chek chiqarish o'zgardi",
  scx_regenerated: "SCX qayta yaratildi",
  matrix_edited: "matritsa tahrirlandi",
  code_regenerated: "yangi ulanish kodi",
  paired: "ulandi",
  badge_regenerated: "beyjik qayta yaratildi",
  survey_saved: "anketa saqlandi",
  survey_photo_added: "anketa rasmi qo'shildi",
  survey_photo_deleted: "anketa rasmi o'chirildi",
  delivered: "topshirildi",
  confirmed: "tasdiqlandi",
  production_started: "ishlab chiqarishga uzatildi",
  machines_assigned: "ish markazlari biriktirildi",
  project_uploaded: "fayl yuklandi",
  accepted: "TMO ga qabul qilindi",
  shipped: "yuklab jo'natildi",
  closed: "yopildi",
  item_removed: "pachkadan olindi",
  badge_queued: "beyjik chop etishga yuborildi",
  move: "ombor harakati",
  sale: "sotildi",
  payment: "to'lov qabul qilindi",
}

function LogsPage() {
  const [module, setModule] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [day, setDay] = useState("") // yyyy-mm-dd (native date input)
  const [page, setPage] = useState(0)
  const [detail, setDetail] = useState<AuditLogRead | null>(null)
  const q = useDebounced(search, 400)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["audit-logs", module ?? "", q, day, page],
    queryFn: () =>
      AuditService.readAuditLogs({
        module: module ?? undefined,
        q: q || undefined,
        dateFrom: day || undefined,
        dateTo: day || undefined,
        skip: page * PAGE,
        limit: PAGE,
      }),
  })
  const rows = data?.data ?? []
  const total = data?.count ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE))

  // Dialogda meta'dagi raw ID'lar o'rniga nomlar: post/ish markazi/agent lug'atlari
  // (kichik ro'yxatlar, keshda turadi — har ochilishda so'rov ketmaydi)
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { data: machines } = useQuery(getMachinesQueryOptions())
  const { data: agents } = useQuery({
    ...getBridgeAgentsQueryOptions(),
    staleTime: 5 * 60_000,
  })
  const postName = (id: number) =>
    posts?.find((p) => p.id === id)?.name ?? `post #${id}`
  const machineName = (id: number) =>
    machines?.find((m) => m.id === id)?.name ?? `ish markazi #${id}`
  const agentName = (id: number) =>
    agents?.find((a) => a.id === id)?.name ?? `agent #${id}`

  const setFilter = (fn: () => void) => {
    fn()
    setPage(0)
  }

  return (
    <div>
      <PageHeader
        title="Loglar"
        description="Kim qachon nima qilgani — skan, chek va boshqa amallar tarixi"
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        {[{ key: null as string | null, label: "Hammasi" }, ...CATEGORIES].map(
          (c) => (
            <Button
              key={c.key ?? "all"}
              size="sm"
              variant={module === c.key ? "default" : "outline"}
              onClick={() => setFilter(() => setModule(c.key))}
            >
              {c.label}
            </Button>
          ),
        )}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchInput
          className="w-full max-w-xs"
          placeholder="Xabar bo'yicha qidirish..."
          value={search}
          onChange={(v) => setFilter(() => setSearch(v))}
        />
        <DatePicker
          value={day}
          onChange={(v) => setFilter(() => setDay(v))}
          placeholder="Sana bo'yicha"
          className="h-9"
        />
        {(module || search || day) && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              setFilter(() => {
                setModule(null)
                setSearch("")
                setDay("")
              })
            }
          >
            <X /> Tozalash
          </Button>
        )}
        <div className="num ml-auto text-sm text-muted-foreground">
          Jami: {total}
        </div>
      </div>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-40">Vaqt</TableHead>
              <TableHead className="w-40">Kim</TableHead>
              <TableHead className="w-36">Kategoriya</TableHead>
              <TableHead>Xabar</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length ? (
              rows.map((r) => (
                <TableRow
                  key={r.id}
                  className="cursor-pointer focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
                  tabIndex={0}
                  role="button"
                  onClick={() => setDetail(r)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      setDetail(r)
                    }
                  }}
                >
                  <TableCell className="num whitespace-nowrap text-muted-foreground">
                    {formatDateTime(r.created_at)}
                  </TableCell>
                  <TableCell className="max-w-40 truncate">
                    {r.user_name || r.employee_name || "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {CATEGORY_LABELS[r.module] ?? r.module}
                    </Badge>
                  </TableCell>
                  <TableCell className="max-w-[480px] truncate">
                    {r.message || (ACTION_LABELS[r.action] ?? r.action)}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <EmptyRow colSpan={4}>
                Tanlangan filtr bo'yicha log topilmadi
              </EmptyRow>
            )}
          </TableBody>
        </Table>
      )}

      <div className="mt-3 flex items-center justify-end gap-2">
        <span className="num text-sm text-muted-foreground">
          {page + 1} / {pages}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={page === 0}
          onClick={() => setPage((p) => p - 1)}
        >
          Oldingi
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={page + 1 >= pages}
          onClick={() => setPage((p) => p + 1)}
        >
          Keyingi
        </Button>
      </div>

      <Dialog
        open={detail !== null}
        onOpenChange={(v) => !v && setDetail(null)}
      >
        <DialogContent>
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {CATEGORY_LABELS[detail.module] ?? detail.module} —{" "}
                  {ACTION_LABELS[detail.action] ?? detail.action}
                </DialogTitle>
                <DialogDescription>
                  {formatDateTime(detail.created_at)}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 text-sm">
                <p className="font-medium">{detail.message || "—"}</p>
                <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-muted-foreground">
                  <span>Kim:</span>
                  <span className="text-foreground">
                    {detail.user_name || detail.employee_name || "—"}
                  </span>
                  {detail.meta?.post_id != null && (
                    <>
                      <span>Post:</span>
                      <span className="text-foreground">
                        {postName(Number(detail.meta.post_id))}
                      </span>
                    </>
                  )}
                  {detail.meta?.machine_id != null && (
                    <>
                      <span>Ish markazi:</span>
                      <span className="text-foreground">
                        {machineName(Number(detail.meta.machine_id))}
                      </span>
                    </>
                  )}
                  {detail.meta?.agent_id != null && (
                    <>
                      <span>Agent:</span>
                      <span className="text-foreground">
                        {agentName(Number(detail.meta.agent_id))}
                      </span>
                    </>
                  )}
                  {typeof detail.meta?.code === "string" && (
                    <>
                      <span>Xato kodi:</span>
                      <span className="num text-foreground">
                        {detail.meta.code}
                      </span>
                    </>
                  )}
                  {detail.ip && (
                    <>
                      <span>IP:</span>
                      <span className="num text-foreground">{detail.ip}</span>
                    </>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
