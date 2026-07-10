import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Activity } from "lucide-react"
import { useCallback } from "react"

import { ReportsService, TabloService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { StagePipeline } from "@/components/Common/StagePipeline"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Skeleton } from "@/components/ui/skeleton"
import useCurrentUser from "@/hooks/useCurrentUser"
import { useMesWs } from "@/hooks/useMesWs"
import { formatDate, MACHINE_STATUS_LABELS, POST_COLORS } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getMachinesQueryOptions, getPostsQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({ meta: [{ title: "Boshqaruv paneli | MebeliX" }] }),
})

function Dashboard() {
  const { currentUser } = useCurrentUser()
  const queryClient = useQueryClient()
  const { data: machines, isLoading: machinesLoading } = useQuery(
    getMachinesQueryOptions(),
  )
  const role = currentUser?.role
  const canStats =
    currentUser?.is_superuser ||
    role === "admin" ||
    role === "manager" ||
    role === "director"
  const { data: stats } = useQuery({
    queryKey: ["reports", "dashboard"],
    queryFn: () => ReportsService.reportDashboard(),
    enabled: Boolean(canStats),
    refetchInterval: 60_000,
  })
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { data: matrix, isLoading: matrixLoading } = useQuery({
    queryKey: ["tablo", "matrix"],
    queryFn: () => TabloService.readTabloMatrix(),
    refetchInterval: 60_000,
  })

  const { online } = useMesWs(
    useCallback(
      (event) => {
        if (
          event.type.startsWith("scan.") ||
          event.type.startsWith("order.") ||
          event.type.startsWith("session.")
        ) {
          queryClient.invalidateQueries({ queryKey: ["tablo"] })
        }
      },
      [queryClient],
    ),
  )

  const postById = new Map((posts ?? []).map((p) => [p.id, p]))
  const sortedPosts = (matrix?.posts ?? [])
    .slice()
    .sort((a, b) => (a.order_index as number) - (b.order_index as number))

  return (
    <div>
      <PageHeader
        title={`Salom, ${currentUser?.name || currentUser?.username || ""}!`}
        description="Ishlab chiqarish holati — jonli"
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
            {online ? "LIVE MONITORING" : "OFFLINE"}
          </span>
        }
      />

      {/* Stanoklar (TZ 10.2.1) */}
      <h2 className="mb-2 text-sm font-bold uppercase tracking-wider text-muted-foreground">
        Stanoklar
      </h2>
      {machinesLoading ? (
        <Skeleton className="h-28 w-full" />
      ) : (
        <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {machines?.map((m) => {
            const post = postById.get(m.post_id)
            const color = post ? POST_COLORS[post.code] : "var(--primary)"
            return (
              <div
                key={m.id}
                className="rounded-xl border bg-card p-4"
                style={{ borderTop: `3px solid ${color}` }}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-bold">{m.name}</div>
                    <div className="text-xs italic text-muted-foreground">
                      {post?.name ?? ""}
                    </div>
                  </div>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-bold",
                      m.status === "active"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-500",
                    )}
                  >
                    {MACHINE_STATUS_LABELS[m.status]}
                  </span>
                </div>
                {m.capacity != null && (
                  <div className="num mt-2 text-xs text-muted-foreground">
                    Quvvat: <b>{m.capacity}</b>{" "}
                    {m.capacity_unit === "m2_per_hour"
                      ? "m²/soat"
                      : m.capacity_unit === "meter_per_hour"
                        ? "m/soat"
                        : "dona/soat"}
                  </div>
                )}
                <MachineQueue
                  stat={stats?.machines.find((x) => x.machine_id === m.id)}
                />
              </div>
            )
          })}
          {!machines?.length && (
            <p className="col-span-full rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
              Stanoklar hali qo'shilmagan.
            </p>
          )}
        </div>
      )}

      {/* Aktiv buyurtmalar progressi (TZ 10.2.2) */}
      <h2 className="mb-2 text-sm font-bold uppercase tracking-wider text-muted-foreground">
        Aktiv buyurtmalar
      </h2>
      {matrixLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : matrix?.orders.length ? (
        <div className="space-y-2">
          {matrix.orders.map((o) => (
            <Link
              key={o.id}
              to="/orders/$orderId"
              params={{ orderId: String(o.id) }}
              className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 hover:border-primary/50"
            >
              <div className="min-w-[140px]">
                <div className="font-bold">{o.number}</div>
                {o.name && (
                  <div className="max-w-[200px] truncate text-xs text-muted-foreground">
                    {o.name}
                  </div>
                )}
              </div>
              <div className="num text-xs">
                <span className="text-muted-foreground">Muddat:</span>{" "}
                <b>{formatDate(o.deadline)}</b>
              </div>
              <div className="ml-auto">
                <StagePipeline
                  stages={sortedPosts
                    .filter((p) => o.stages[p.code as string])
                    .map((p) => ({
                      code: p.code as string,
                      done: o.stages[p.code as string].done,
                      total: o.stages[p.code as string].total,
                    }))}
                />
              </div>
              <StatusBadge status={o.status} />
            </Link>
          ))}
        </div>
      ) : (
        <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
          Hozircha ishlab chiqarishda buyurtma yo'q.
        </p>
      )}
    </div>
  )
}

function MachineQueue({
  stat,
}: {
  stat?: {
    queue_scans: number
    queue_volume: number
    unit: string
    forecast_hours: number | null
    today_scans: number
  }
}) {
  if (!stat) return null
  return (
    <div className="num mt-2 space-y-0.5 border-t pt-2 text-xs">
      <div>
        Navbatda: <b>{stat.queue_scans}</b> scan
        {stat.queue_volume > 0 && (
          <span className="text-muted-foreground">
            {" "}
            (~{stat.queue_volume} {stat.unit})
          </span>
        )}
      </div>
      <div className="flex justify-between">
        <span>
          Bugun: <b>{stat.today_scans}</b>
        </span>
        {/* TZ 4.3: tugatish_vaqti = navbatdagi_yuk / capacity */}
        {stat.forecast_hours != null && (
          <span className="font-bold text-primary">
            ~ {stat.forecast_hours} SOAT
          </span>
        )}
      </div>
    </div>
  )
}
