// Ish markazining O'Z sahifasi: «hozir nima qilyapti» + sozlamalari.
//
// Nega oyna emas, sahifa: tsexda stanok ustiga bosganda kerak bo'ladigan narsa bitta
// sozlama emas — joriy ish, oxirgi amallar, kim smenada. Oyna bunga tor va orqasidagi
// jadvalni to'sib qo'yadi. Teppada «Ish markazlari» havolasi — ro'yxatga qaytaradi.
//
// Tablar: «Ish» (jonli) va «Sozlamalar» (sozlanadigan posti bor stanokda, adminga).
// Tab URL'da (`?tab=`): sahifa yangilansa joyida qoladi.

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react"

import { MachinesService, SettingsService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { PostBadge } from "@/components/Common/PostBadge"
import { QueryError } from "@/components/Common/QueryError"
import {
  hasMachineSettings,
  IdealCycleCard,
  KromkaBindCard,
  KromkaCycleCard,
  KromkaIdleCard,
  KromkaKalCard,
  RoverCycleCard,
} from "@/components/Settings/MachineCards"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { KromkaLive } from "@/components/WorkCenters/KromkaLive"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useMesWs } from "@/hooks/useMesWs"
import { requireAccess } from "@/lib/guards"
import {
  ANDON_STATE_LABELS,
  ANDON_STYLE,
  formatDateTime,
  formatSince,
  isAdmin,
  isProductionStaff,
  MACHINE_STATUS_LABELS,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getMachinesQueryOptions, getPostsQueryOptions } from "@/queries/mes"

const TABS = [
  { value: "ish", label: "Ish" },
  { value: "sozlama", label: "Sozlamalar" },
] as const
type WcTab = (typeof TABS)[number]["value"]
const TAB_PANEL = "data-[state=inactive]:hidden"

export const Route = createFileRoute("/_layout/work-centers/$machineId")({
  component: WorkCenterPage,
  // Noto'g'ri qiymatda `undefined` — ota marshrutning xom search'i o'tib ketmasin
  validateSearch: (s: Record<string, unknown>): { tab?: WcTab } => ({
    tab: TABS.some((t) => t.value === s.tab) ? (s.tab as WcTab) : undefined,
  }),
  beforeLoad: requireAccess(isProductionStaff),
  head: () => ({ meta: [{ title: "Ish markazi | MebeliX" }] }),
})

const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })

function WorkCenterPage() {
  const { machineId } = Route.useParams()
  const { tab } = Route.useSearch()
  const navigate = Route.useNavigate()
  const id = Number(machineId)
  const machinesQ = useQuery(getMachinesQueryOptions())
  const postsQ = useQuery(getPostsQueryOptions())
  const { data: overview } = useQuery({
    queryKey: ["machines", "overview"],
    queryFn: async () => (await MachinesService.readMachinesOverview()).data,
    refetchInterval: 60_000,
  })
  const activityQ = useQuery({
    queryKey: ["machines", "activity", id],
    queryFn: async () =>
      (await MachinesService.readMachineActivity({ path: { machine_id: id } }))
        .data,
    // WS asosiy manba; poll — soket uzilib qolgan holat uchun zaxira
    refetchInterval: 60_000,
    enabled: Number.isFinite(id),
  })

  // Skan kelishi bilan ro'yxat yangilanadi — 60 s poll kutilmaydi. Payload'ni
  // qo'lda yopishtirmaymiz: unda hodim nomi va detal nomi yo'q, so'rov esa kichik.
  const queryClient = useQueryClient()
  useMesWs(
    useCallback(
      (event) => {
        const mid = event.payload?.machine_id
        if (mid !== undefined && mid !== id) return
        if (event.type === "scan.recorded" || event.type === "scan.cancelled") {
          queryClient.invalidateQueries({
            queryKey: ["machines", "activity", id],
          })
          // «Bugun» va «Navbatda» sanoqlari ham shu skandan o'zgaradi
          queryClient.invalidateQueries({ queryKey: ["machines", "overview"] })
        }
        if (event.type === "andon.state")
          queryClient.invalidateQueries({ queryKey: ["machines", "overview"] })
      },
      [id, queryClient],
    ),
  )
  // «12 daq» matni holat o'zgarmasa ham o'sib borsin
  const [, setTick] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [])

  const machine = machinesQ.data?.find((m) => m.id === id)
  const post = postsQ.data?.find((p) => p.id === machine?.post_id)
  const o = overview?.find((row) => row.machine_id === id)
  const activity = activityQ.data
  const { currentUser } = useCurrentUser()
  const sozlamali = isAdmin(currentUser) && hasMachineSettings(post?.code)
  const faol: WcTab = tab && (tab !== "sozlama" || sozlamali) ? tab : "ish"

  // Eng yangi qator bir marta yashil urilsin (tabloning belgisi bilan bir xil).
  // Birinchi yuklanishda urilmaydi: o'shanda hamma qator «yangi» bo'lardi.
  const topId = activity?.rows[0]?.scan_id
  const korilgan = useRef<number | undefined>(undefined)
  const flash = korilgan.current !== undefined && topId !== korilgan.current
  useEffect(() => {
    korilgan.current = topId
  }, [topId])

  if (machinesQ.isLoading || postsQ.isLoading)
    return <Skeleton className="h-64 w-full" />
  if (machinesQ.isError || postsQ.isError)
    return (
      <QueryError
        onRetry={() => {
          machinesQ.refetch()
          postsQ.refetch()
        }}
      />
    )
  if (!machine)
    return (
      <div>
        <BackLink />
        <p className="text-muted-foreground">Ish markazi topilmadi.</p>
      </div>
    )

  return (
    <div>
      <BackLink />
      <PageHeader
        title={machine.name}
        titleAside={
          <div className="flex flex-wrap items-center gap-2">
            {post && <PostBadge code={post.code} />}
            {machine.status !== "active" && (
              <Badge variant="outline">
                {MACHINE_STATUS_LABELS[machine.status]}
              </Badge>
            )}
            {o?.andon_state && (
              <Badge
                variant="outline"
                className={cn(
                  "gap-1.5",
                  ANDON_STYLE[o.andon_state] ??
                    "border-transparent bg-muted text-muted-foreground",
                )}
              >
                <span
                  className={cn(
                    "inline-block size-1.5 rounded-full bg-current",
                    o.andon_state === "AWAIT_PART" &&
                      "motion-safe:animate-pulse",
                  )}
                />
                {ANDON_STATE_LABELS[o.andon_state] ?? o.andon_state}
                {o.andon_since && (
                  <span className="num font-normal">
                    · {formatSince(o.andon_since)}
                  </span>
                )}
              </Badge>
            )}
          </div>
        }
        description="Markaz hozir nima qilyapti: joriy buyurtma, smenadagilar va oxirgi amallar jonli"
      />

      <Tabs
        value={faol}
        onValueChange={(v) =>
          navigate({ search: { tab: v as WcTab }, replace: true })
        }
      >
        {/* Sozlanadigan narsasi yo'q postda tab qatori chizilmaydi — bitta
            «Ish» tabi hech qayerga olib bormaydi */}
        {sozlamali && (
          <TabsList>
            {TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        )}

        <TabsContent value="ish" className={cn("mt-4", TAB_PANEL)}>
          <div className={cn(cardSurface, "mb-6 p-4")}>
            <h2 className="mb-3 text-sm font-semibold">Joriy ish</h2>
            {activityQ.isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : activityQ.isError ? (
              <QueryError onRetry={() => activityQ.refetch()} />
            ) : (
              <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Fakt label="Buyurtma">
                  {activity?.order_number && activity.order_id ? (
                    <Link
                      to="/orders/$orderId"
                      params={{ orderId: String(activity.order_id) }}
                      className="underline underline-offset-4"
                    >
                      {activity.order_number}
                    </Link>
                  ) : (
                    <span className="text-muted-foreground">
                      hali skan yo'q
                    </span>
                  )}
                  {activity?.order_remaining ? (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      shu postda {activity.order_remaining} skan qoldi
                    </span>
                  ) : null}
                </Fakt>
                <Fakt label="Smenada">
                  {activity?.employees.length ? (
                    activity.employees.join(", ")
                  ) : (
                    <span className="text-muted-foreground">yo'q</span>
                  )}
                </Fakt>
                <Fakt label="Bugun">
                  {o?.today_scans ?? 0}{" "}
                  <span className="text-xs font-normal text-muted-foreground">
                    skan
                  </span>
                </Fakt>
                <Fakt label="Navbatda">
                  {o?.queue_scans ? (
                    <>
                      {o.queue_scans}{" "}
                      <span className="text-xs font-normal text-muted-foreground">
                        skan
                      </span>
                    </>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </Fakt>
              </dl>
            )}
          </div>

          {/* KROMKA: o'lchov oqimi — har detalning mos/nomosligi ketma-ket */}
          {post?.code === "KROMKA" && (
            <div className="mb-6">
              <KromkaLive machineId={id} title="Jonli o'lchov" />
            </div>
          )}

          <h2 className="mb-2 text-sm font-semibold">
            Oxirgi amallar
            <span className="ml-2 font-normal text-muted-foreground">
              detal skanerlanishi bilan chiqadi
            </span>
          </h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-24">Vaqt</TableHead>
                <TableHead>Detal</TableHead>
                <TableHead>Buyurtma</TableHead>
                <TableHead>Hodim</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activity?.rows.length ? (
                activity.rows.map((r, i) => (
                  <TableRow
                    key={r.scan_id}
                    className={cn(
                      i === 0 && flash && "animate-cell-flash",
                      r.cancelled && "text-muted-foreground line-through",
                    )}
                  >
                    <TableCell
                      className="num text-xs"
                      title={formatDateTime(r.at)}
                    >
                      {clock(r.at)}
                    </TableCell>
                    <TableCell>
                      <div className="num font-medium">{r.part_code}</div>
                      <div className="text-xs text-muted-foreground">
                        {r.part_name ?? r.qr_text}
                      </div>
                    </TableCell>
                    <TableCell className="num">{r.order_number}</TableCell>
                    <TableCell className="text-sm">
                      {r.employee ?? "—"}
                      {r.cancelled && (
                        <span className="ml-2 text-xs">bekor qilindi</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <EmptyRow colSpan={4}>Bu markazda hali skan yo'q.</EmptyRow>
              )}
            </TableBody>
          </Table>
        </TabsContent>

        {sozlamali && (
          <TabsContent value="sozlama" className={cn("mt-4", TAB_PANEL)}>
            <p className="mb-4 max-w-prose text-sm text-muted-foreground">
              Bu qiymatlar {post?.code} turidagi HAMMA stanokka tegishli:
              bittasini o'zgartirsang, qolganlari ham shu bo'yicha ishlaydi.
              O'zgarish saqlangan zahoti kuchga kiradi.
            </p>
            <div className="space-y-4 [&_p]:max-w-prose">
              {post?.code === "KROMKA" && <KromkaSettings machineId={id} />}
              {post?.code === "PRISADKA" && <IdealCycleCard />}
              {post?.code === "ROVER" && <RoverCycleCard />}
            </div>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}

function BackLink() {
  return (
    <Link
      to="/work-centers"
      className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" /> Ish markazlari
    </Link>
  )
}

function Fakt({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="num font-semibold">{children}</dd>
    </div>
  )
}

/** KROMKA kartalari sozlamalar ro'yxatini bir marta so'raydi — har karta alohida
 *  emas (ular bitta `system-settings` so'rovidan oziqlanadi). */
function KromkaSettings({ machineId }: { machineId: number }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system-settings"],
    queryFn: async () => (await SettingsService.readSystemSettings()).data,
  })
  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (isError || !data) return <QueryError onRetry={() => refetch()} />
  return (
    <>
      <KromkaBindCard settings={data} />
      <KromkaIdleCard settings={data} />
      <KromkaCycleCard />
      <KromkaKalCard machineId={machineId} />
      <p className="text-sm text-muted-foreground">
        Kalibrlash sessiyasi (etalon o'tkazib Pico'ga yangi qiymat yozish)
        alohida sahifada:{" "}
        <Link
          to="/system-settings"
          search={{ tab: "kalib" }}
          className="underline underline-offset-4"
        >
          Tizim sozlamalari → Kalibrlash
        </Link>
        .
      </p>
    </>
  )
}
