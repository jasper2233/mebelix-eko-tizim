// Loglar (admin-only): audit_log jadvali kategoriya, qidiruv, sana filtri va
// sahifalash bilan. Skan/chek kabi jonli oqimlar ham shu yerga yoziladi —
// kim qachon nima qilganini bitta joydan topish uchun.

import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search, X } from "lucide-react"
import { useState } from "react"

import { type AuditLogRead, AuditService, BridgeAgentsService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
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
import { useDebounced } from "@/hooks/useDebounced"
import { formatDateTime } from "@/lib/mes"
import { getMachinesQueryOptions, getPostsQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/logs")({
  component: LogsPage,
  head: () => ({ meta: [{ title: "Loglar | MebeliX" }] }),
})

const PAGE = 50

// Kategoriyalar = log_action module qiymatlari. Yangi modul qo'shilsa shu
// ro'yxatga bitta qator qo'shiladi — sahifaning qolgan qismi o'zgarmaydi.
const CATEGORIES: { key: string; label: string }[] = [
  { key: "scan", label: "Skan" },
  { key: "print", label: "Chek" },
  { key: "orders", label: "Buyurtmalar" },
  { key: "bridge_agents", label: "Printer agentlar" },
  { key: "employees", label: "Hodimlar" },
  { key: "clients", label: "Mijozlar" },
  { key: "materials", label: "Materiallar" },
  { key: "machines", label: "Stanoklar" },
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
  machine_linked: "stanok bog'landi",
  can_print_changed: "chek chiqarish o'zgardi",
  scx_regenerated: "SCX qayta yaratildi",
  matrix_edited: "matritsa tahrirlandi",
  code_regenerated: "yangi ulanish kodi",
  paired: "ulandi",
}

function LogsPage() {
  const [module, setModule] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [day, setDay] = useState("") // yyyy-mm-dd (native date input)
  const [page, setPage] = useState(0)
  const [detail, setDetail] = useState<AuditLogRead | null>(null)
  const q = useDebounced(search, 400)

  const { data, isLoading } = useQuery({
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

  // Dialogda meta'dagi raw ID'lar o'rniga nomlar: post/stanok/agent lug'atlari
  // (kichik ro'yxatlar, keshda turadi — har ochilishda so'rov ketmaydi)
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { data: machines } = useQuery(getMachinesQueryOptions())
  const { data: agents } = useQuery({
    queryKey: ["bridge-agents"],
    queryFn: () => BridgeAgentsService.readBridgeAgents(),
    staleTime: 5 * 60_000,
  })
  const postName = (id: number) =>
    posts?.find((p) => p.id === id)?.name ?? `post #${id}`
  const machineName = (id: number) =>
    machines?.find((m) => m.id === id)?.name ?? `stanok #${id}`
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

      <div className="mb-3 flex flex-wrap items-center gap-2">
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

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-72">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Xabar bo'yicha qidirish..."
            value={search}
            onChange={(e) => setFilter(() => setSearch(e.target.value))}
          />
        </div>
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
      ) : (
        <div className="overflow-x-auto rounded-lg border">
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
                    className="cursor-pointer"
                    onClick={() => setDetail(r)}
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
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className="h-24 text-center text-muted-foreground"
                  >
                    Tanlangan filtr bo'yicha log topilmadi
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
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
                      <span>Stanok:</span>
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
