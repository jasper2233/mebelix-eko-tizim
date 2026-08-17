import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Activity } from "lucide-react"
import { useCallback } from "react"

import { ReportsService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { PostBadge } from "@/components/Common/PostBadge"
import { SectionTitle } from "@/components/Common/SectionTitle"
import { StagePipeline } from "@/components/Common/StagePipeline"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { Badge } from "@/components/ui/badge"
import { cardSurface } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useMesWs } from "@/hooks/useMesWs"
import {
  CAPACITY_UNIT_LABELS,
  formatDate,
  MACHINE_STATUS_LABELS,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  getMachinesQueryOptions,
  getPostsQueryOptions,
  getTabloMatrixQueryOptions,
} from "@/queries/mes"

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
  const { data: matrix, isLoading: matrixLoading } = useQuery(
    getTabloMatrixQueryOptions(),
  )

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
        title="Boshqaruv paneli"
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
            {online ? "JONLI" : "ALOQA YO'Q"}
          </span>
        }
      />

      {/* Ish markazlari (TZ 10.2.1) — jadval, karta emas: beshta bir xil tuzilishli
          obyekt, har birida 3-5 raqam. Kartalar geterogen yoki rasm/amal talab
          qiladigan narsalar uchun; bir xil ustunli raqamlar solishtiriladi,
          ya'ni jadval zichroq va skanerlanadigan. Kartalar teng balandlikka
          cho'zilib, oxirgi qatorda yolg'iz element qoldirardi. */}
      <SectionTitle>Ish markazlari</SectionTitle>
      {machinesLoading ? (
        <Skeleton className="mb-8 h-40 w-full" />
      ) : machines?.length ? (
        <div className="mb-8 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ish markazi</TableHead>
                <TableHead>Post</TableHead>
                <TableHead className="text-right">Quvvat</TableHead>
                <TableHead className="text-right">Navbatda</TableHead>
                <TableHead className="text-right">Bugun</TableHead>
                <TableHead className="text-right">Tugash</TableHead>
                <TableHead>Holat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {machines.map((m) => {
                const post = postById.get(m.post_id)
                const stat = stats?.machines.find((x) => x.machine_id === m.id)
                return (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium">{m.name}</TableCell>
                    <TableCell>
                      {post ? <PostBadge code={post.code} /> : "—"}
                    </TableCell>
                    <TableCell className="num text-right text-muted-foreground">
                      {m.capacity != null
                        ? `${m.capacity} ${CAPACITY_UNIT_LABELS[m.capacity_unit ?? "units_per_hour"]}`
                        : "—"}
                    </TableCell>
                    {/* Navbat — sahifadagi asosiy signal, shuning uchun eng katta */}
                    <TableCell className="num text-right">
                      {stat ? (
                        <>
                          <span className="text-lg font-bold">
                            {stat.queue_scans}
                          </span>
                          {stat.queue_volume > 0 && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              ~{stat.queue_volume} {stat.unit}
                            </span>
                          )}
                        </>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="num text-right">
                      {stat?.today_scans ?? "—"}
                    </TableCell>
                    {/* TZ 4.3: tugatish_vaqti = navbatdagi_yuk / capacity */}
                    <TableCell className="num text-right font-bold text-primary">
                      {stat?.forecast_hours != null
                        ? `~${stat.forecast_hours} soat`
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          m.status === "active" ? "default" : "secondary"
                        }
                      >
                        {MACHINE_STATUS_LABELS[m.status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      ) : (
        <p className="mb-8 rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
          Ish markazlari hali qo'shilmagan — "Ish markazlari" bo'limidan
          qo'shing.
        </p>
      )}

      {/* Aktiv buyurtmalar progressi (TZ 10.2.2) */}
      <SectionTitle>Aktiv buyurtmalar</SectionTitle>
      {matrixLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : matrix?.orders.length ? (
        <div className="space-y-2">
          {matrix.orders.map((o) => (
            <Link
              key={o.id}
              to="/orders/$orderId"
              params={{ orderId: String(o.id) }}
              className={cn(
                cardSurface,
                "flex flex-wrap items-center gap-3 p-3 hover:border-primary/50",
              )}
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
                <span className="text-muted-foreground">
                  Topshirish sanasi:
                </span>{" "}
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
