// Boshqaruv paneli: bir qarashda «bugun nima bo'lyapti, nima kechikdi, nimani
// topshirish kerak». Buyurtma-ma-buyurtma taxta — /tablo, bu yerda emas.

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Activity, ArrowRight } from "lucide-react"
import type { ReactNode } from "react"

import type { PostLoad, ReadyOrder, TabloOrderRow, TrendDay } from "@/client"
import { ReportsService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { PostBadge } from "@/components/Common/PostBadge"
import { QueryError } from "@/components/Common/QueryError"
import { SectionTitle } from "@/components/Common/SectionTitle"
import { cardSurface } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useMesWs } from "@/hooks/useMesWs"
import { useThrottled } from "@/hooks/useThrottled"
import {
  formatDate,
  formatMoney,
  groupThousands,
  isProductionStaff,
  POST_COLORS,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getTabloMatrixQueryOptions, TABLO_WS_THROTTLE_MS } from "@/queries/mes"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({ meta: [{ title: "Boshqaruv paneli | MebeliX" }] }),
})

const WEEKDAYS = [
  "Yakshanba",
  "Dushanba",
  "Seshanba",
  "Chorshanba",
  "Payshanba",
  "Juma",
  "Shanba",
]

// Sana LOKAL komponentlardan — `toISOString` UTC ga siljitib kunni buzadi
function localIso(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const num = (n: number) => groupThousands(String(Math.round(n)))

/** Muddatdan necha kun o'tgani (bugun = 0, kelajak — manfiy). */
function daysLate(deadline: string | null | undefined): number | null {
  if (!deadline) return null
  return Math.round(
    (Date.parse(localIso(new Date())) - Date.parse(deadline)) / 864e5,
  )
}

/** Buyurtma bo'yicha bajarilgan qadamlar ulushi (barcha postlar yig'indisi). */
function progressPct(o: TabloOrderRow): number {
  let done = 0
  let total = 0
  for (const s of Object.values(o.stages)) {
    done += s.done
    total += s.total
  }
  return total ? Math.round((done / total) * 100) : 0
}

const LIST_LIMIT = 6

function Dashboard() {
  const { currentUser } = useCurrentUser()
  const queryClient = useQueryClient()
  const canSee = isProductionStaff(currentUser)
  const {
    data: stats,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["reports", "dashboard"],
    queryFn: async () => (await ReportsService.reportDashboard()).data,
    enabled: canSee,
    refetchInterval: 60_000,
  })
  // Kechikkan / to'xtab qolgan ro'yxatlar — Tablo matritsasidan (idle_days va
  // bosqich progressi faqat o'sha yerda), alohida endpoint yozilmadi.
  const { data: matrix } = useQuery({
    ...getTabloMatrixQueryOptions(),
    enabled: canSee,
  })

  // Matritsa tablo bilan bir xil qoida bo'yicha: har skanda emas, 10 s da bir
  // (birinchisi darhol) — sababi `routes/tablo.tsx` dagi izohda
  const refreshMatrix = useThrottled(
    () => queryClient.invalidateQueries({ queryKey: ["tablo"] }),
    TABLO_WS_THROTTLE_MS,
  )
  const { online } = useMesWs((event) => {
    if (event.type.startsWith("scan.")) refreshMatrix()
    // Skan oqimida panelni har skanda qayta so'ramaymiz (60s poll yetadi);
    // buyurtma va smena hodisalari kam, ular darhol aks etsin.
    if (event.type.startsWith("order.") || event.type.startsWith("session.")) {
      refreshMatrix()
      queryClient.invalidateQueries({ queryKey: ["reports", "dashboard"] })
    }
  })

  const now = new Date()
  const overdue = (matrix?.orders ?? [])
    .map((o) => ({ o, late: daysLate(o.deadline) ?? 0 }))
    .filter((x) => x.late > 0)
    .sort((a, b) => b.late - a.late)
  const stalled = (matrix?.orders ?? [])
    .filter((o) => (o.idle_days ?? 0) >= 2)
    .sort((a, b) => (b.idle_days ?? 0) - (a.idle_days ?? 0))

  return (
    <div>
      <PageHeader
        title="Boshqaruv paneli"
        description={`${WEEKDAYS[now.getDay()]}, ${formatDate(localIso(now))}`}
        actions={
          <span
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold",
              online
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700",
            )}
          >
            <Activity className="size-3.5" />
            {online ? "JONLI" : "ALOQA YO'Q"}
          </span>
        }
      />

      {!canSee ? (
        <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
          Bu panel ofis xodimlari (menejer, texnolog, direktor) uchun.
        </p>
      ) : isLoading ? (
        <div className="space-y-6">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : isError || !stats ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <div className="space-y-8">
          {/* ---- Bugun: beshta raqam ---- */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <Kpi
              label="Bugungi skanlar"
              value={num(stats.today.scans)}
              sub={`kecha ${num(stats.today.scans_yesterday)}`}
            />
            <Kpi
              label="Smenada"
              value={String(stats.today.on_shift)}
              unit="hodim"
              sub="beyjik bilan ochiq smena"
            />
            <Kpi
              label="Bugun buyurtmalar"
              value={
                <span className="flex items-baseline gap-3">
                  <Triple n={stats.today.started} label="ishga tushdi" />
                  <Triple n={stats.today.completed} label="tayyor" />
                  <Triple n={stats.today.delivered} label="topshirildi" />
                </span>
              }
            />
            <Kpi
              label="Jarayonda"
              value={String(stats.orders.production)}
              unit="buyurtma"
              to="/tablo"
              sub={
                stats.orders.overdue || stats.orders.no_deadline ? (
                  <>
                    {stats.orders.overdue > 0 && (
                      <span className="font-semibold text-destructive">
                        {stats.orders.overdue} kechikkan
                      </span>
                    )}
                    {stats.orders.overdue > 0 && stats.orders.no_deadline > 0
                      ? " · "
                      : ""}
                    {stats.orders.no_deadline > 0 && (
                      <span className="text-amber-700">
                        {stats.orders.no_deadline} muddatsiz
                      </span>
                    )}
                    {stats.orders.due_today > 0 &&
                      ` · bugun ${stats.orders.due_today} ta muddat`}
                  </>
                ) : stats.orders.due_today > 0 ? (
                  `bugun ${stats.orders.due_today} ta muddat`
                ) : (
                  "kechikkan yo'q"
                )
              }
            />
            <Kpi
              label="Topshirishga tayyor"
              value={String(stats.orders.ready)}
              unit="buyurtma"
              to="/orders"
              search={{ status: "completed" }}
              sub={
                stats.ready[0] && stats.ready[0].waiting_days >= 3 ? (
                  <span className="font-semibold text-amber-700">
                    eng eskisi {stats.ready[0].waiting_days} kun kutmoqda
                  </span>
                ) : stats.orders.ready ? (
                  "tsexdan chiqqan, mijozga topshirilmagan"
                ) : (
                  "hammasi topshirilgan"
                )
              }
            />
          </div>

          {/* ---- Diqqat talab: uchta ro'yxat ---- */}
          <section>
            <SectionTitle>Diqqat talab</SectionTitle>
            <div className="grid gap-4 lg:grid-cols-3">
              <Panel
                title="Kechikkan"
                count={overdue.length}
                more={
                  overdue.length > LIST_LIMIT ? (
                    <MoreLink to="/tablo">Tablo</MoreLink>
                  ) : null
                }
                empty="Muddati o'tgan buyurtma yo'q"
              >
                {overdue.slice(0, LIST_LIMIT).map(({ o, late }) => (
                  <OrderRow
                    key={o.id}
                    id={o.id}
                    number={o.number}
                    sub={o.name}
                    right={
                      <>
                        <span className="num text-xs text-muted-foreground">
                          {progressPct(o)}%
                        </span>
                        <Tag tone="red">{late} KUN</Tag>
                      </>
                    }
                  />
                ))}
              </Panel>
              <Panel
                title="To'xtab qolgan"
                count={stalled.length}
                hint="2+ ish kuni skan yo'q"
                more={
                  stalled.length > LIST_LIMIT ? (
                    <MoreLink to="/tablo">Tablo</MoreLink>
                  ) : null
                }
                empty="Hamma buyurtma qimirlayapti"
              >
                {stalled.slice(0, LIST_LIMIT).map((o) => (
                  <OrderRow
                    key={o.id}
                    id={o.id}
                    number={o.number}
                    sub={o.name}
                    right={
                      <>
                        <span className="num text-xs text-muted-foreground">
                          {o.idle_days} ish kuni
                        </span>
                        <Tag tone="amber">
                          {progressPct(o) > 0 ? "QIMIRLAMADI" : "BOSHLANMAGAN"}
                        </Tag>
                      </>
                    }
                  />
                ))}
              </Panel>
              <Panel
                title="Topshirishga tayyor"
                count={stats.ready.length}
                more={
                  stats.ready.length > LIST_LIMIT ? (
                    <MoreLink to="/orders" search={{ status: "completed" }}>
                      Buyurtmalar
                    </MoreLink>
                  ) : null
                }
                empty="Topshirilmagan tayyor buyurtma yo'q"
              >
                {stats.ready.slice(0, LIST_LIMIT).map((r) => (
                  <ReadyRow key={r.id} r={r} />
                ))}
              </Panel>
            </div>
          </section>

          {/* ---- Postlar yuklamasi ---- */}
          <section>
            <SectionTitle>Postlar yuklamasi</SectionTitle>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {stats.posts.map((p) => (
                <PostCard key={p.post_id} p={p} />
              ))}
            </div>
          </section>

          {/* ---- Tendensiya + pul ---- */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Panel
              title="Skanlar — oxirgi 14 kun"
              className="lg:col-span-2"
              hint={`o'rtacha ${num(avgFullDays(stats.trend))} / kun`}
            >
              <Trend days={stats.trend} />
            </Panel>
            {stats.money && (
              <Panel
                title="Qoldiq to'lovlar"
                more={<MoreLink to="/clients">Mijozlar</MoreLink>}
              >
                <div className="px-4 py-3">
                  <div className="num text-2xl font-bold">
                    {formatMoney(stats.money.receivable)}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {stats.money.orders} buyurtma
                    {stats.money.delivered_unpaid > 0 && (
                      <>
                        {" · "}
                        <span className="font-semibold text-destructive">
                          {stats.money.delivered_unpaid} tasi topshirilgan
                        </span>
                      </>
                    )}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Narx − boshlang'ich to'lov, qoralama va bekor qilinganlarsiz
                  </div>
                </div>
              </Panel>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/** Bugungi o'rtacha to'liq bo'lmagan kun — o'rtacha faqat tugagan kunlardan. */
function avgFullDays(days: TrendDay[]): number {
  const full = days.slice(0, -1).filter((d) => d.scans > 0)
  return full.length ? full.reduce((s, d) => s + d.scans, 0) / full.length : 0
}

// ---------- kichik bloklar ----------

function Kpi({
  label,
  value,
  unit,
  sub,
  to,
  search,
}: {
  label: string
  value: ReactNode
  unit?: string
  sub?: ReactNode
  to?: "/tablo" | "/orders"
  search?: { status: "completed" }
}) {
  const body = (
    <>
      <div className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="num text-3xl font-bold leading-none">{value}</span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
      </div>
      {sub && (
        <div className="mt-1.5 truncate text-xs text-muted-foreground">
          {sub}
        </div>
      )}
    </>
  )
  const cls = cn(cardSurface, "block p-4")
  if (to === "/orders")
    return (
      <Link
        to={to}
        search={search ?? {}}
        className={cn(cls, "hover:border-primary/50")}
      >
        {body}
      </Link>
    )
  if (to === "/tablo")
    return (
      <Link to={to} className={cn(cls, "hover:border-primary/50")}>
        {body}
      </Link>
    )
  return <div className={cls}>{body}</div>
}

function Triple({ n, label }: { n: number; label: string }) {
  return (
    <span className="flex items-baseline gap-1">
      <span className="num text-3xl font-bold leading-none">{n}</span>
      <span className="text-2xs text-muted-foreground">{label}</span>
    </span>
  )
}

function Panel({
  title,
  count,
  hint,
  more,
  empty,
  className,
  children,
}: {
  title: string
  count?: number
  hint?: string
  more?: ReactNode
  empty?: string
  className?: string
  children: ReactNode
}) {
  const isEmpty =
    empty !== undefined &&
    (count === 0 || (Array.isArray(children) && !children.length))
  return (
    <div className={cn(cardSurface, "flex flex-col", className)}>
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <h3 className="text-sm font-semibold">{title}</h3>
        {count !== undefined && count > 0 && (
          <span className="num rounded-full bg-muted px-1.5 text-xs font-semibold text-muted-foreground">
            {count}
          </span>
        )}
        {hint && (
          <span className="text-xs text-muted-foreground">· {hint}</span>
        )}
        <span className="ml-auto">{more}</span>
      </div>
      {isEmpty ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground">
          {empty}
        </p>
      ) : (
        <div className="divide-y">{children}</div>
      )}
    </div>
  )
}

function MoreLink({
  to,
  search,
  children,
}: {
  to: "/tablo" | "/orders" | "/clients"
  search?: { status: "completed" }
  children: ReactNode
}) {
  const cls =
    "flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
  if (to === "/orders")
    return (
      <Link to={to} search={search ?? {}} className={cls}>
        {children} <ArrowRight className="size-3" />
      </Link>
    )
  return (
    <Link to={to} className={cls}>
      {children} <ArrowRight className="size-3" />
    </Link>
  )
}

function OrderRow({
  id,
  number,
  sub,
  right,
}: {
  id: number
  number: string
  sub?: string | null
  right: ReactNode
}) {
  return (
    <Link
      to="/orders/$orderId"
      params={{ orderId: String(id) }}
      className="flex items-center gap-3 px-4 py-2 hover:bg-muted/50"
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold">{number}</div>
        {sub && (
          <div className="truncate text-xs text-muted-foreground" title={sub}>
            {sub}
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">{right}</div>
    </Link>
  )
}

function ReadyRow({ r }: { r: ReadyOrder }) {
  return (
    <OrderRow
      id={r.id}
      number={r.number}
      sub={r.client_name}
      right={
        <>
          <span className="num text-xs text-muted-foreground">
            {formatDate(r.completed_at)}
          </span>
          {r.waiting_days >= 3 ? (
            <Tag tone="amber">{r.waiting_days} KUN</Tag>
          ) : (
            <Tag tone="muted">{r.waiting_days} KUN</Tag>
          )}
        </>
      }
    />
  )
}

function Tag({
  tone,
  children,
}: {
  tone: "red" | "amber" | "muted"
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        "num rounded-sm px-1.5 py-0.5 text-2xs font-bold whitespace-nowrap",
        tone === "red" && "bg-red-100 text-red-700",
        tone === "amber" && "bg-amber-100 text-amber-800",
        tone === "muted" && "bg-muted text-muted-foreground",
      )}
    >
      {children}
    </span>
  )
}

function PostCard({ p }: { p: PostLoad }) {
  // Dona birlikli postda hajm — DETAL soni, yonidagi skan soni esa qolgan skanlar.
  // Odatdagi holatda (postga bitta marshrut qatori) ular teng, ya'ni takror; detal
  // shu postdan ikki marta o'tsa hajm ulushga bo'linadi (`metrics.VolumeShare`) va
  // ikki raqam ajraladi — o'shanda ham operatorga kerakligi SKAN soni, shuning
  // uchun dona postda hajm ko'rsatilmaydi.
  const showVolume = p.queue_volume > 0 && p.unit !== "dona"
  const idle = p.queue_scans === 0 && p.today_scans === 0
  return (
    <div
      className={cn(cardSurface, "border-l-4 p-3", idle && "opacity-60")}
      style={{ borderLeftColor: POST_COLORS[p.code] }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-semibold">{p.name}</span>
        <PostBadge code={p.code} />
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="num text-2xl font-bold leading-none">
          {num(p.queue_scans)}
        </span>
        <span className="truncate text-xs text-muted-foreground">
          {idle ? "ish yo'q" : "navbatda"}
          {showVolume && ` · ~${num(p.queue_volume)} ${p.unit}`}
        </span>
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-muted-foreground">
        <span>
          bugun{" "}
          <span className="num font-semibold text-foreground">
            {num(p.today_scans)}
          </span>
        </span>
        <span className="num">{p.orders} buyurtma</span>
      </div>
      {p.down.length > 0 && (
        <div className="mt-1.5 text-xs font-semibold text-destructive">
          {p.down.join(", ")} — ishlamayapti
        </div>
      )}
    </div>
  )
}

function Trend({ days }: { days: TrendDay[] }) {
  const max = Math.max(1, ...days.map((d) => d.scans))
  const last = days.length - 1
  return (
    <div className="px-4 pt-3 pb-2">
      <div className="flex h-28 items-end gap-1">
        {days.map((d, i) => (
          <div
            key={d.day}
            title={`${formatDate(d.day)} · ${num(d.scans)} skan`}
            className={cn(
              "flex-1 rounded-t-sm",
              i === last ? "bg-primary" : "bg-primary/25",
            )}
            style={{ height: `${Math.max(2, (d.scans / max) * 100)}%` }}
          />
        ))}
      </div>
      <div className="num mt-1.5 flex justify-between text-2xs text-muted-foreground">
        <span>{formatDate(days[0]?.day)}</span>
        <span>bugun {num(days[last]?.scans ?? 0)}</span>
      </div>
    </div>
  )
}
