// Loglar (admin-only): audit_log jadvali — modul tab'lari (backend
// `/audit-logs/summary`dan, sonlari bilan), modul ichida amal chiplari, xabar
// bo'yicha qidiruv, sana filtri, sahifalash. Qator → o'ng paneldagi to'liq
// yozuv (kim, obyekt, IP, meta). Skan/chek kabi jonli oqimlar ham shu yerda —
// kim qachon nima qilganini bitta joydan topish uchun.

import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ExternalLink, X } from "lucide-react"
import { type ReactNode, useState } from "react"

import { type AuditLogRead, AuditService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
import { TablePagination } from "@/components/Common/TablePagination"
import { Button } from "@/components/ui/button"
import { DatePicker } from "@/components/ui/date-picker"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
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
import {
  AUDIT_ACTION_LABELS,
  formatDateTime,
  isAdmin,
  SCAN_ERROR_LABELS,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
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

// Modul nomlari odam tilida. Tab'lar ro'yxati BU YERDAN EMAS — backend
// `summary`dan keladi (bo'sh modul tab bo'lmaydi, yangi modul o'zi chiqadi);
// bu faqat tarjima va tartib. Noma'lum modul xom nomi bilan oxirida chiqadi.
const MODULE_LABELS: Record<string, string> = {
  scan: "Skan",
  print: "Chek",
  tmo: "TMO",
  sessions: "Smenalar",
  orders: "Buyurtmalar",
  pachka: "Pachkalar",
  bridge_agents: "MES agentlar",
  employees: "Hodimlar",
  users: "Foydalanuvchilar",
  clients: "Mijozlar",
  machines: "Ish markazlari",
  posts: "Postlar",
  auth: "Kirish/chiqish",
}
const MODULE_ORDER = Object.keys(MODULE_LABELS)

const ENTITY_LABELS: Record<string, string> = {
  order: "Buyurtma",
  scan: "Skan",
  part_instance: "Detal nusxasi",
  session: "Smena",
  waste_item: "Qoldiq",
  bridge_agent: "MES agent",
  employee: "Hodim",
  client: "Mijoz",
  machine: "Ish markazi",
  user: "Foydalanuvchi",
}

// Salbiy amallar qizil, yakunlovchi milestone'lar yashil — ro'yxatda ko'z
// darhol rad/bekor qatorlarga tushsin (1 077 rad etilgan skan 15 273 orasida).
const NEGATIVE = new Set([
  "rejected",
  "login_failed",
  "cancelled",
  "deleted",
  "label_cancelled",
  "waste_label_cancelled",
])
const POSITIVE = new Set([
  "accepted",
  "delivered",
  "confirmed",
  "production_started",
  "paired",
])

const actionLabel = (a: string) => AUDIT_ACTION_LABELS[a] ?? a
const moduleLabel = (m: string) => MODULE_LABELS[m] ?? m

function ActionBadge({ action }: { action: string }) {
  return (
    <span
      className={cn(
        "inline-block rounded-sm px-1.5 py-0.5 text-2xs font-bold uppercase tracking-wide whitespace-nowrap",
        NEGATIVE.has(action)
          ? "bg-red-100 text-red-700"
          : POSITIVE.has(action)
            ? "bg-emerald-100 text-emerald-800"
            : "bg-muted text-muted-foreground",
      )}
    >
      {actionLabel(action)}
    </span>
  )
}

// Soniyali vaqt — skan oqimida bir daqiqada o'nlab yozuv bo'ladi
function formatDateTimeSec(iso: string): string {
  const d = new Date(iso)
  return `${formatDateTime(iso)}:${String(d.getSeconds()).padStart(2, "0")}`
}

function LogsPage() {
  const [module, setModule] = useState<string | null>(null)
  const [action, setAction] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [day, setDay] = useState("") // yyyy-mm-dd (DatePicker qiymati, date_from=date_to)
  const [page, setPage] = useState(0)
  const [detail, setDetail] = useState<AuditLogRead | null>(null)
  const q = useDebounced(search, 400)
  const dayParams = { date_from: day || undefined, date_to: day || undefined }

  // Tab sonlari — ko'rinib turgan kun bo'yicha (ro'yxat bilan bir xil filtr)
  const { data: summary } = useQuery({
    queryKey: ["audit-logs", "summary", day],
    queryFn: async () =>
      (await AuditService.readAuditSummary({ query: dayParams })).data,
    placeholderData: keepPreviousData,
  })
  const moduleCounts = new Map<string, number>()
  for (const r of summary ?? [])
    moduleCounts.set(r.module, (moduleCounts.get(r.module) ?? 0) + r.count)
  const modules = [...moduleCounts.keys()].sort((a, b) => {
    const ia = MODULE_ORDER.indexOf(a)
    const ib = MODULE_ORDER.indexOf(b)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b)
  })
  const allCount = [...moduleCounts.values()].reduce((a, b) => a + b, 0)
  const actions = module
    ? (summary ?? []).filter((r) => r.module === module)
    : []

  const { data, isLoading, isError, refetch } = useQuery({
    // Sahifa/filtr almashganda eski natija ekranda qoladi: aks holda `data`
    // bir zumga `undefined` bo'lib, "Jami" va sahifalash tugmalari yo'qoladi.
    placeholderData: keepPreviousData,
    queryKey: ["audit-logs", module ?? "", action ?? "", q, day, page],
    queryFn: async () =>
      (
        await AuditService.readAuditLogs({
          query: {
            module: module ?? undefined,
            action: action ?? undefined,
            q: q || undefined,
            ...dayParams,
            skip: page * PAGE,
            limit: PAGE,
          },
        })
      ).data,
  })
  const rows = data?.data ?? []
  const total = data?.count ?? 0

  const pickModule = (m: string | null) => {
    setModule(m)
    setAction(null)
    setPage(0)
  }
  const hasFilter = module || action || search || day

  return (
    <div>
      <PageHeader
        title="Loglar"
        description="Kim qachon nima qilgani — skan, chek va boshqa amallar tarixi"
      />

      {/* Modul tab'lari — sonlari bilan; faqat yozuvi bor modullar */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <FilterChip active={module === null} onClick={() => pickModule(null)}>
          Hammasi <Count n={allCount} />
        </FilterChip>
        {modules.map((m) => (
          <FilterChip
            key={m}
            active={module === m}
            onClick={() => pickModule(m)}
          >
            {moduleLabel(m)} <Count n={moduleCounts.get(m) ?? 0} />
          </FilterChip>
        ))}
      </div>
      {/* Amal chiplari — modul tanlanganda, 2+ amal bo'lsa */}
      {module && actions.length > 1 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 pl-1">
          <span className="text-xs text-muted-foreground">Amal:</span>
          <FilterChip
            small
            active={action === null}
            onClick={() => {
              setAction(null)
              setPage(0)
            }}
          >
            hammasi
          </FilterChip>
          {actions.map((a) => (
            <FilterChip
              key={a.action}
              small
              active={action === a.action}
              tone={NEGATIVE.has(a.action) ? "red" : undefined}
              onClick={() => {
                setAction(a.action)
                setPage(0)
              }}
            >
              {actionLabel(a.action)} <Count n={a.count} />
            </FilterChip>
          ))}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchInput
          className="w-full max-w-sm"
          placeholder="Xabar bo'yicha: detal kodi, buyurtma raqami, ism…"
          value={search}
          onChange={(v) => {
            setSearch(v)
            setPage(0)
          }}
        />
        <DatePicker
          value={day}
          onChange={(v) => {
            setDay(v)
            setPage(0)
          }}
          placeholder="Sana bo'yicha"
          className="h-9"
        />
        {hasFilter && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              pickModule(null)
              setSearch("")
              setDay("")
            }}
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
              <TableHead className="w-44">Vaqt</TableHead>
              <TableHead className="w-44">Kim</TableHead>
              {/* Modul tanlanganda kategoriya ustuni takror — yashiriladi */}
              {!module && <TableHead className="w-36">Kategoriya</TableHead>}
              <TableHead className="w-44">Amal</TableHead>
              <TableHead>Xabar</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length ? (
              rows.map((r) => (
                <TableRow
                  key={r.id}
                  className={cn(
                    "cursor-pointer focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2",
                    detail?.id === r.id && "bg-muted/60",
                  )}
                  tabIndex={0}
                  onClick={() => setDetail(r)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      setDetail(r)
                    }
                  }}
                >
                  <TableCell className="num whitespace-nowrap text-muted-foreground">
                    {formatDateTimeSec(r.created_at)}
                  </TableCell>
                  <TableCell className="max-w-44 truncate">
                    {/* Odam birinchi: skanda hodim ham, terminal hisobi ham bor */}
                    {r.employee_name || r.user_name || (
                      <span className="text-muted-foreground">tizim</span>
                    )}
                  </TableCell>
                  {!module && (
                    <TableCell className="text-muted-foreground">
                      {moduleLabel(r.module)}
                    </TableCell>
                  )}
                  <TableCell>
                    <ActionBadge action={r.action} />
                  </TableCell>
                  <TableCell
                    className="max-w-[520px] truncate"
                    title={r.message ?? undefined}
                  >
                    {r.message || "—"}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <EmptyRow colSpan={module ? 4 : 5}>
                Tanlangan filtr bo'yicha log topilmadi
              </EmptyRow>
            )}
          </TableBody>
        </Table>
      )}

      <TablePagination
        page={page}
        pageSize={PAGE}
        total={total}
        onPage={setPage}
      />

      <DetailSheet entry={detail} onClose={() => setDetail(null)} />
    </div>
  )
}

function FilterChip({
  active,
  small,
  tone,
  onClick,
  children,
}: {
  active: boolean
  small?: boolean
  tone?: "red"
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-medium transition-colors",
        small ? "h-7 px-2 text-xs" : "h-8 px-2.5 text-sm",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "bg-card hover:bg-muted",
        !active && tone === "red" && "text-red-700",
      )}
    >
      {children}
    </button>
  )
}

function Count({ n }: { n: number }) {
  return <span className="num text-xs opacity-70">{n}</span>
}

// ---------- o'ng panel: bitta yozuv to'liq ----------

// Meta kalitlari — odam tilida chiziladiganlari. Qolgani «Qo'shimcha» JSON.
const KNOWN_META = new Set([
  "post_id",
  "machine_id",
  "agent_id",
  "code",
  "fix",
  "products",
  "parts",
  "instances",
  "materials",
  "warnings",
  "assignments",
])

function DetailSheet({
  entry,
  onClose,
}: {
  entry: AuditLogRead | null
  onClose: () => void
}) {
  // Meta'dagi raw ID'lar o'rniga nomlar: post/ish markazi/agent lug'atlari
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

  const meta = entry?.meta ?? {}
  const extra = Object.fromEntries(
    Object.entries(meta).filter(([k]) => !KNOWN_META.has(k)),
  )
  const warnings = Array.isArray(meta.warnings) ? meta.warnings : []
  const uploadStats = (["products", "parts", "instances", "materials"] as const)
    .filter((k) => typeof meta[k] === "number")
    .map((k) => `${meta[k]} ${UPLOAD_LABELS[k]}`)

  return (
    <Sheet open={entry !== null} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {entry && (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  {moduleLabel(entry.module)}
                </span>
                <ActionBadge action={entry.action} />
              </div>
              <SheetTitle className="text-base leading-snug">
                {entry.message || actionLabel(entry.action)}
              </SheetTitle>
              <SheetDescription className="num">
                {formatDateTimeSec(entry.created_at)} · #{entry.id}
              </SheetDescription>
            </SheetHeader>

            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 px-4 text-sm">
              <Fact label="Hodim">{entry.employee_name}</Fact>
              <Fact label="Hisob">{entry.user_name}</Fact>
              {!entry.employee_name && !entry.user_name && (
                <Fact label="Kim">
                  <span className="text-muted-foreground">
                    tizim (foydalanuvchisiz)
                  </span>
                </Fact>
              )}
              <Fact label="Obyekt">
                {entry.entity_type && (
                  <EntityLink
                    type={entry.entity_type}
                    id={entry.entity_id ?? null}
                  />
                )}
              </Fact>
              <Fact label="Post">
                {meta.post_id != null && postName(Number(meta.post_id))}
              </Fact>
              <Fact label="Ish markazi">
                {meta.machine_id != null &&
                  machineName(Number(meta.machine_id))}
              </Fact>
              <Fact label="Agent">
                {meta.agent_id != null && agentName(Number(meta.agent_id))}
              </Fact>
              <Fact label="Xato kodi">
                {typeof meta.code === "string" && (
                  <>
                    <span className="num font-semibold text-red-700">
                      {meta.code}
                    </span>
                    {SCAN_ERROR_LABELS[meta.code] && (
                      <span className="text-muted-foreground">
                        {" — "}
                        {SCAN_ERROR_LABELS[meta.code]}
                      </span>
                    )}
                  </>
                )}
              </Fact>
              <Fact label="Fayl">{uploadStats.join(" · ") || null}</Fact>
              <Fact label="Izoh">
                {typeof meta.fix === "string" ? meta.fix : null}
              </Fact>
              <Fact label="IP">
                {entry.ip && <span className="num">{entry.ip}</span>}
              </Fact>
            </dl>

            {warnings.length > 0 && (
              <div className="px-4">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Ogohlantirishlar · {warnings.length}
                </div>
                <ul className="list-disc space-y-0.5 pl-4 text-sm text-amber-800">
                  {warnings.map((w) => (
                    <li key={String(w)}>{String(w)}</li>
                  ))}
                </ul>
              </div>
            )}

            {(Object.keys(extra).length > 0 || meta.assignments != null) && (
              <div className="px-4">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Qo'shimcha
                </div>
                <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
                  {JSON.stringify(
                    meta.assignments != null
                      ? { assignments: meta.assignments, ...extra }
                      : extra,
                    null,
                    2,
                  )}
                </pre>
              </div>
            )}
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

const UPLOAD_LABELS = {
  products: "mahsulot",
  parts: "detal",
  instances: "nusxa",
  materials: "material",
} as const

/** Bo'sh qiymatli fakt umuman chizilmaydi — panelda «—» qatorlari turmasin. */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  if (children === null || children === undefined || children === false)
    return null
  if (typeof children === "string" && !children) return null
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  )
}

/** Obyekt turi + ID; sahifasi bor turlar havola. */
function EntityLink({ type, id }: { type: string; id: number | null }) {
  const label = `${ENTITY_LABELS[type] ?? type}${id != null ? ` #${id}` : ""}`
  const cls =
    "inline-flex items-center gap-1 font-medium text-primary hover:underline"
  if (id != null && type === "order")
    return (
      <Link
        to="/orders/$orderId"
        params={{ orderId: String(id) }}
        className={cls}
      >
        {label} <ExternalLink className="size-3" />
      </Link>
    )
  const to = ENTITY_ROUTES[type]
  if (to)
    return (
      <Link to={to} className={cls}>
        {label} <ExternalLink className="size-3" />
      </Link>
    )
  return <span>{label}</span>
}

const ENTITY_ROUTES: Record<
  string,
  "/clients" | "/employees" | "/work-centers" | "/agents" | "/admin"
> = {
  client: "/clients",
  employee: "/employees",
  machine: "/work-centers",
  bridge_agent: "/agents",
  user: "/admin",
}
