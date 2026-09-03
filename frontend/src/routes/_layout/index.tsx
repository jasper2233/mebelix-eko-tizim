import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Activity } from "lucide-react"
import { ReportsService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { PostBadge } from "@/components/Common/PostBadge"
import { QueryError } from "@/components/Common/QueryError"
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
import { formatDate, isManagement, MACHINE_STATUS_LABELS } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  getMachinesQueryOptions,
  getPostsQueryOptions,
  getTabloMatrixQueryOptions,
} from "@/queries/mes"

/** So'rov yiqilganda katak jim "—" ko'rsatmasligi uchun — bo'sh va buzuq
 * holat bir xil ko'rinsa, direktor "navbat bo'sh" deb o'qiydi. */
const cellFallback = (isError: boolean) =>
  isError ? <span className="text-destructive">xato</span> : "—"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({ meta: [{ title: "Boshqaruv paneli | MebeliX" }] }),
})

function Dashboard() {
  const { currentUser } = useCurrentUser()
  const queryClient = useQueryClient()
  const {
    data: machines,
    isLoading: machinesLoading,
    isError: machinesError,
    refetch: refetchMachines,
  } = useQuery(getMachinesQueryOptions())
  const canStats = isManagement(currentUser)
  const { data: stats, isError: statsError } = useQuery({
    queryKey: ["reports", "dashboard"],
    queryFn: async () => (await ReportsService.reportDashboard()).data,
    enabled: Boolean(canStats),
    refetchInterval: 60_000,
  })
  const { data: posts, isError: postsError } = useQuery(getPostsQueryOptions())
  const {
    data: matrix,
    isLoading: matrixLoading,
    isError: matrixError,
    refetch: refetchMatrix,
  } = useQuery(getTabloMatrixQueryOptions())

  const { online } = useMesWs((event) => {
    if (
      event.type.startsWith("scan.") ||
      event.type.startsWith("order.") ||
      event.type.startsWith("session.")
    ) {
      queryClient.invalidateQueries({ queryKey: ["tablo"] })
    }
  })

  const postById = new Map((posts ?? []).map((p) => [p.id, p]))
  const sortedPosts = (matrix?.posts ?? [])
    .slice()
    .sort((a, b) => a.order_index - b.order_index)

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

      {/* Ish markazlari — jadval, karta emas: beshta bir xil tuzilishli
          obyekt, har birida 3-5 raqam. Kartalar geterogen yoki rasm/amal talab
          qiladigan narsalar uchun; bir xil ustunli raqamlar solishtiriladi,
          ya'ni jadval zichroq va skanerlanadigan. Kartalar teng balandlikka
          cho'zilib, oxirgi qatorda yolg'iz element qoldirardi. */}
      <SectionTitle>Ish markazlari</SectionTitle>
      {machinesLoading ? (
        <Skeleton className="mb-8 h-40 w-full" />
      ) : machinesError ? (
        <div className="mb-8">
          <QueryError onRetry={() => refetchMachines()} />
        </div>
      ) : machines?.length ? (
        <div className="mb-8">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ish markazi</TableHead>
                <TableHead>Post</TableHead>
                <TableHead className="text-right">Navbatda</TableHead>
                <TableHead className="text-right">Bugun</TableHead>
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
                      {post ? (
                        <PostBadge code={post.code} />
                      ) : (
                        cellFallback(postsError)
                      )}
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
                        cellFallback(statsError)
                      )}
                    </TableCell>
                    <TableCell className="num text-right">
                      {stat ? stat.today_scans : cellFallback(statsError)}
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

      {/* Aktiv buyurtmalar progressi */}
      <SectionTitle>Aktiv buyurtmalar</SectionTitle>
      {matrixLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : matrixError ? (
        <QueryError onRetry={() => refetchMatrix()} />
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
                    .filter((p) => o.stages[p.code])
                    .map((p) => ({
                      code: p.code,
                      done: o.stages[p.code].done,
                      total: o.stages[p.code].total,
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
