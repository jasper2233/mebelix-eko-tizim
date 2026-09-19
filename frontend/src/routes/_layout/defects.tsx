// Brak: operator terminalda QAYD qiladi, menejer shu yerda tasdiqlaydi yoki «brak emas»
// deb rad etadi (docs/12-oee.md §7). Qaror ikki savolga javob beradi: KIM aybdor (marshrut
// QADAMI — post emas, chunki bitta post marshrutda ikki marta uchrashi mumkin) va QAYERDAN
// qayta boshlanadi. Qayta ishlab chiqarishning o'zi (`-B1` nusxa, yangi chek) hali yo'q.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Check, X } from "lucide-react"
import { useEffect, useState } from "react"

import { type DefectRow, type DefectStatus, DefectsService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
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
import { requireAccess } from "@/lib/guards"
import {
  DEFECT_STATUS_LABELS,
  formatDateTime,
  isManager,
  PROCESS_OPS,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import { crudCallbacks } from "@/queries/mes"

export const Route = createFileRoute("/_layout/defects")({
  component: DefectsPage,
  // Backend `ManagerUser` ning oynasi: admin/superuser + menejer (direktor EMAS)
  beforeLoad: requireAccess(isManager),
  head: () => ({ meta: [{ title: "Brak | MebeliX" }] }),
})

export const DEFECTS_KEY = ["defects"]

const TABS: { value: DefectStatus | "all"; label: string }[] = [
  { value: "pending", label: "Kutmoqda" },
  { value: "confirmed", label: "Tasdiqlangan" },
  { value: "rejected", label: "Rad etilgan" },
  { value: "all", label: "Hammasi" },
]

const STATUS_STYLE: Record<string, string> = {
  pending: "border-amber-300 bg-amber-50 text-amber-900",
  confirmed: "border-red-300 bg-red-50 text-red-900",
  rejected: "border-transparent bg-muted text-muted-foreground",
}

/** Qadam nomi: «3. Prisadka — Prisadka (Ali Valiyev)». Amal nomi postnikidan farq qilsa qo'shiladi. */
const stepLabel = (s: DefectRow["steps"][number]) => {
  const op = PROCESS_OPS[s.process_code]?.name
  const amal = op && op !== s.post_name ? ` · ${op}` : ""
  return `${s.seq}. ${s.post_name}${amal}`
}

function DefectsPage() {
  const [tab, setTab] = useState<DefectStatus | "all">("pending")
  const [review, setReview] = useState<DefectRow | null>(null)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [...DEFECTS_KEY, tab],
    queryFn: async () =>
      (
        await DefectsService.readDefects({
          query: tab === "all" ? {} : { status: tab },
        })
      ).data,
    // Terminal brak qo'shganda sahifa o'zi yangilansin (WS hodisasi yo'q — brak kam)
    refetchInterval: 60_000,
  })
  const rows = data ?? []

  return (
    <div>
      <PageHeader
        title="Brak"
        description="Operator terminalda belgilaydi, menejer tasdiqlaydi. Tasdiqlanganda detal tanlangan qadamdan QAYTA ochiladi — o'sha postning ro'yxatida bajarilmagan bo'lib paydo bo'ladi va keyingi postlarga tartib bilan o'tadi. «Brak emas» deb rad etilgani esa OEE Quality'dan chiqadi."
      />
      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as DefectStatus | "all")}
        className="mb-4"
      >
        <TabsList className="h-9">
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Vaqti</TableHead>
              <TableHead>Detal ID</TableHead>
              <TableHead>Buyurtma</TableHead>
              <TableHead>Qayerda</TableHead>
              <TableHead>Sabab</TableHead>
              <TableHead>Qaror</TableHead>
              <TableHead className="text-right">Amal</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length ? (
              rows.map((r) => {
                const blame = r.steps.find(
                  (s) => s.route_id === r.blame_route_id,
                )
                const restart = r.steps.find(
                  (s) => s.route_id === r.restart_route_id,
                )
                return (
                  <TableRow key={r.id}>
                    <TableCell className="num whitespace-nowrap text-sm">
                      {formatDateTime(r.created_at)}
                    </TableCell>
                    <TableCell className="num font-medium">
                      {r.qr_text}
                      <div className="text-xs font-normal text-muted-foreground">
                        {r.part_code} · {r.part_name}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Link
                        to="/orders/$orderId"
                        params={{ orderId: String(r.order_id) }}
                        className="font-medium underline underline-offset-2"
                      >
                        {r.order_number}
                      </Link>
                    </TableCell>
                    <TableCell className="text-sm">
                      {r.post_name}
                      <div className="text-xs text-muted-foreground">
                        {[r.machine_name, r.employee_name]
                          .filter(Boolean)
                          .join(" · ")}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      <span className="font-medium">{r.reason}</span>
                      {r.note && (
                        <div className="max-w-60 truncate text-xs text-muted-foreground">
                          {r.note}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">
                      <Badge
                        variant="outline"
                        className={cn("font-semibold", STATUS_STYLE[r.status])}
                      >
                        {DEFECT_STATUS_LABELS[r.status]}
                      </Badge>
                      {r.status === "confirmed" && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          Ayb: {blame ? stepLabel(blame) : "material nuqsoni"}
                          {r.blame_employee_name &&
                            ` — ${r.blame_employee_name}`}
                          <br />
                          Qaytadan: {restart ? stepLabel(restart) : "—"}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant={r.status === "pending" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setReview(r)}
                      >
                        {r.status === "pending"
                          ? "Ko'rib chiqish"
                          : "O'zgartirish"}
                      </Button>
                    </TableCell>
                  </TableRow>
                )
              })
            ) : (
              <EmptyRow colSpan={7}>
                {tab === "pending"
                  ? "Tasdiq kutayotgan brak yo'q."
                  : "Bu holatda brak yo'q."}
              </EmptyRow>
            )}
          </TableBody>
        </Table>
      )}

      <ReviewDialog defect={review} onClose={() => setReview(null)} />
    </div>
  )
}

/** Qaror oynasi: aybdor qadam (yoki material nuqsoni) va qayta boshlash nuqtasi. */
function ReviewDialog({
  defect,
  onClose,
}: {
  defect: DefectRow | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [blame, setBlame] = useState<number | null>(null)
  const [restart, setRestart] = useState<number | null>(null)
  useEffect(() => {
    if (!defect) return
    setBlame(defect.blame_route_id ?? null)
    // Sukut: brak topilgan qadamdan qayta boshlanadi — odatiy holat shu
    setRestart(
      defect.restart_route_id ??
        defect.steps.find((s) => s.post_name === defect.post_name)?.route_id ??
        null,
    )
  }, [defect])

  const decide = useMutation({
    mutationFn: (status: DefectStatus) =>
      DefectsService.reviewDefect({
        path: { defect_id: defect?.id ?? 0 },
        body: {
          status,
          blame_route_id: status === "confirmed" ? blame : null,
          restart_route_id: status === "confirmed" ? restart : null,
        },
      }),
    ...crudCallbacks(queryClient, DEFECTS_KEY, "Qaror saqlandi"),
    onSuccess: () => {
      crudCallbacks(queryClient, DEFECTS_KEY, "Qaror saqlandi").onSuccess()
      onClose()
    },
  })

  if (!defect) return null
  const pick = (
    label: string,
    value: number | null,
    onPick: (id: number | null) => void,
    withNone: string | null,
  ) => (
    <section className="space-y-2">
      <div className="text-sm font-semibold">{label}</div>
      <div className="grid gap-2 sm:grid-cols-2">
        {withNone && (
          <button
            type="button"
            onClick={() => onPick(null)}
            className={cn(
              "rounded-lg border-2 px-3 py-2 text-left text-sm font-medium",
              value === null
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card hover:border-primary/50",
            )}
          >
            {withNone}
          </button>
        )}
        {defect.steps.map((s) => (
          <button
            key={s.route_id}
            type="button"
            onClick={() => onPick(s.route_id)}
            className={cn(
              "rounded-lg border-2 px-3 py-2 text-left text-sm font-medium",
              value === s.route_id
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card hover:border-primary/50",
            )}
          >
            {stepLabel(s)}
            {s.employee_name && (
              <span className="block text-xs font-normal opacity-80">
                {s.employee_name}
              </span>
            )}
          </button>
        ))}
      </div>
    </section>
  )

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90vh] gap-5 overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-xl">
            {defect.qr_text} — {defect.reason}
          </DialogTitle>
          <DialogDescription>
            {defect.order_number} · {defect.part_code} {defect.part_name} ·{" "}
            {defect.post_name}
            {defect.employee_name && ` · ${defect.employee_name}`}
            {defect.note && (
              <span className="mt-1 block text-foreground">{defect.note}</span>
            )}
          </DialogDescription>
        </DialogHeader>

        {defect.steps.length === 0 ? (
          <p className="text-sm text-destructive">
            Bu detalning marshruti yo'q — qadam tanlab bo'lmaydi. Avval texnolog
            marshrutni chizsin.
          </p>
        ) : (
          <>
            {pick("Ayb kimda?", blame, setBlame, "Material nuqsoni (ayb yo'q)")}
            {pick("Qayerdan qayta boshlanadi?", restart, setRestart, null)}
          </>
        )}

        {/* Tasdiq nima qilishini ochiq aytish: bu qaytarib bo'lmaydigan amal —
            keyingi skanlar bekor qilinadi va ish qaytadan boshlanadi. */}
        <p className="text-sm text-muted-foreground">
          Tasdiqlansa shu qadamdan keyingi skanlar bekor qilinadi: detal o'sha
          postda qayta paydo bo'ladi (kesish xaritasida katak odatdagi rangga
          qaytadi), qadoqda bo'lsa undan chiqariladi, buyurtma esa «tayyor» dan
          «jarayonda» ga qaytadi. Rad etish hech narsani tiklamaydi.
        </p>
        <div className="flex items-center gap-3">
          <LoadingButton
            variant="outline"
            className="h-11"
            loading={decide.isPending}
            onClick={() => decide.mutate("rejected")}
          >
            <X /> Brak emas
          </LoadingButton>
          <LoadingButton
            className="ml-auto h-11 min-w-44 font-bold"
            loading={decide.isPending}
            disabled={restart === null}
            onClick={() => decide.mutate("confirmed")}
          >
            <Check /> Tasdiqlash
          </LoadingButton>
        </div>
        {restart === null && defect.steps.length > 0 && (
          <p className="text-sm text-muted-foreground">
            Tasdiqlash uchun qayta boshlash qadamini tanlang.
          </p>
        )}
      </DialogContent>
    </Dialog>
  )
}
