import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import {
  ArrowLeft,
  CheckCheck,
  ClipboardList,
  Download,
  FileCode2,
  FileText,
  FileUp,
  Lock,
  Map as MapIcon,
  Play,
  Trash2,
  Truck,
  XCircle,
} from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { OrdersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SectionTitle } from "@/components/Common/SectionTitle"
import { StagePipeline } from "@/components/Common/StagePipeline"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { CustomRoutes } from "@/components/Orders/CustomRoutes"
import { EditOrder } from "@/components/Orders/EditOrder"
import { MachineAssign } from "@/components/Orders/MachineAssign"
import { OrderMatrix } from "@/components/Orders/OrderMatrix"
import { Button } from "@/components/ui/button"
import { Card, cardSurface } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import {
  AUDIT_ACTION_LABELS,
  deadlineTone,
  FILE_KIND_LABELS,
  formatBytes,
  formatDate,
  formatDateTime,
  formatMoney,
  isAdmin,
  isManager,
  isSuperuser,
  PRIORITY_BADGE_CLASSES,
  PRIORITY_LABELS,
  remainingPayment,
  TERMINAL_STATUSES,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  crudCallbacks,
  getOrderMatrixQueryOptions,
  getOrderQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"
import { API_BASE, extractErrorMessage, handleError } from "@/utils"

export const Route = createFileRoute("/_layout/orders/$orderId")({
  component: OrderDetailPage,
  head: () => ({ meta: [{ title: "Buyurtma | MebeliX" }] }),
})

function OrderDetailPage() {
  const { orderId } = Route.useParams()
  const id = Number(orderId)
  const queryClient = useQueryClient()
  const {
    data: order,
    isLoading,
    isError,
    refetch,
  } = useQuery(getOrderQueryOptions(id))
  // Tab yorlig'idagi nostandart detallar soni: `enabled: false` — so'rov ketmaydi (matritsani OrderMatrix
  // yuklaydi), lekin keshga OBUNA — yuklanganda/tahrirlanganda yorliq yangilanadi (`getQueryData` yo'q).
  const { data: matrix } = useQuery({
    ...getOrderMatrixQueryOptions(id),
    enabled: false,
  })
  const { data: posts } = useQuery(getPostsQueryOptions())
  const stagesSummary = useMemo(() => {
    const parts = matrix?.parts ?? []
    // BARCHA postlar (nostandart marshrutdagi Rover/Stolyarka/Bo'yoq va dum —
    // qadoqlash/TMO ham): dashboard bilan bir xil qamrov. Faqat standart uchtasi
    // bo'lsa nostandart detal qayerdaligi ko'rinmasdi.
    return (posts ?? [])
      .sort((a, b) => a.order_index - b.order_index)
      .map((p) => {
        let done = 0
        let total = 0
        for (const part of parts)
          for (const r of part.routes)
            if (r.post_id === p.id && r.is_enabled) {
              done += r.total_done
              total += r.total_required
            }
        return { code: p.code, done, total }
      })
      .filter((st) => st.total > 0)
  }, [posts, matrix])
  const { currentUser } = useCurrentUser()
  const fileInput = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [matrixToolbarEl, setMatrixToolbarEl] = useState<HTMLDivElement | null>(
    null,
  )
  const [dragOver, setDragOver] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const navigate = useNavigate()
  const [deliverOpen, setDeliverOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState("")

  const role = currentUser?.role
  const admin = isAdmin(currentUser)
  const canManage = isManager(currentUser)
  const isTexnolog = admin || role === "texnolog"

  // ["orders"] prefiksi ["orders", id] va ["orders", id, "matrix"] ni ham
  // qamraydi — qolgan ikki chaqiruv ortiqcha edi.
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["orders"] })
  const cb = (msg: string) => crudCallbacks(queryClient, ["orders"], msg)

  const upload = async (file: File) => {
    // In-flight qorovul: ikki ketma-ket tashlash (yoki yuklash paytida bosib
    // ikkinchi fayl tanlash) ikkita POST yuborardi — buyurtma ikki marta
    // ingest qilinar, unique indeks tufayli ikkinchisi 500 bilan tugardi.
    if (uploading) return
    setUploading(true)
    try {
      const { data: res } = await OrdersService.uploadOrderProject({
        path: { order_id: id },
        body: { file },
      })
      // Server javobida detal soni va tahlil ogohlantirishlari bor (kodsiz detal,
      // takroriy kod, xaritada joyi yo'q detal) — ilgari ular ko'rsatilmasdi.
      toast.success(res.message)
      invalidate()
    } catch (err) {
      toast.error(extractErrorMessage(err as never))
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ""
    }
  }

  const confirm = useMutation({
    mutationFn: () => OrdersService.confirmOrder({ path: { order_id: id } }),
    ...cb("Buyurtma tasdiqlandi — texnologga uzatildi"),
  })
  const start = useMutation({
    mutationFn: () =>
      OrdersService.startOrderProduction({ path: { order_id: id } }),
    ...cb("Ishlab chiqarishga uzatildi"),
  })
  const deliverCb = cb("Buyurtma topshirildi")
  const deliver = useMutation({
    mutationFn: () => OrdersService.deliverOrder({ path: { order_id: id } }),
    ...deliverCb,
    onSuccess: () => {
      deliverCb.onSuccess()
      setDeliverOpen(false)
    },
  })
  // O'chirish QAYTMAYDI: buyurtma, detallari va diskdagi fayllari ketadi.
  // Shuning uchun faqat superuser va faqat BEKOR QILINGAN buyurtmada. Muvaffaqiyatdan
  // keyin sahifa qoladigan joy yo'q — reestrga qaytamiz.
  const deleteCb = cb("Buyurtma o'chirildi")
  const remove = useMutation({
    mutationFn: () => OrdersService.deleteOrder({ path: { order_id: id } }),
    ...deleteCb,
    onSuccess: () => {
      deleteCb.onSuccess()
      setDeleteOpen(false)
      navigate({ to: "/orders" })
    },
  })
  const cancelCb = cb("Buyurtma bekor qilindi")
  const cancel = useMutation({
    mutationFn: () =>
      OrdersService.cancelOrder({
        path: { order_id: id },
        body: { reason: cancelReason },
      }),
    ...cancelCb,
    onSuccess: () => {
      cancelCb.onSuccess()
      setCancelOpen(false)
      setCancelReason("")
    },
  })
  // Eski buyurtmalarni yangi SCX nomlashga (nusxa QR = fayl nomi, Nanxing skan
  // mosligi) o'tkazish — .project saqlangan bo'lsa bir bosishda
  const regenScx = useMutation({
    mutationFn: () =>
      OrdersService.regenerateOrderScx({ path: { order_id: id } }),
    onSuccess: (r) => toast.success(r.data.message),
    onError: handleError,
    onSettled: invalidate,
  })

  if (isError)
    return (
      <QueryError
        message="Buyurtmani ochib bo'lmadi."
        onRetry={() => refetch()}
      />
    )
  if (isLoading || !order) return <Skeleton className="h-96 w-full" />

  // Tahrirlash huquqini BACKEND aytadi (`orders._edit_block_reason`): holat +
  // tsexda haqiqiy ish bor-yo'qligi. Bu yerda qayta hisoblab bo'lmaydi —
  // skanlar bu javobda yo'q, va ikki joyda hisoblansa ular ajralib ketardi.
  const canEdit = order.can_edit ?? false
  // Fayl qayta yuklash faqat texnologda: marshrutni u tuzadi.
  const canUpload = isTexnolog && canEdit
  const isTerminal = TERMINAL_STATUSES.includes(order.status)
  const scxFiles = (order.files ?? []).filter((f) => f.kind === "scx")
  const fileUrl = (name: string | number) =>
    `${API_BASE}/api/v1/orders/${id}/files/${name}`
  const customCount = (matrix?.parts ?? []).filter((p) => p.is_custom).length
  const deadlineToneValue = isTerminal ? "" : deadlineTone(order.deadline)

  // GibLab fayldagi typeId="simple" goodlar: petlya, yevrovint, dasta... (dona).
  // SKU kodlilar oldin: kodsizlar orasida dizaynerning 3D-model qoldiqlari ham
  // uchraydi ("Вычитание тел", "Гнутая") — haqiqiy furnitura ustun tursin.
  const hardware = (order.material_usage ?? [])
    .filter((m) => m.kind === "hardware")
    .sort(
      (a, b) =>
        (a.code ? 0 : 1) - (b.code ? 0 : 1) || a.name.localeCompare(b.name),
    )

  return (
    <div>
      <Link
        to="/orders"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Buyurtmalar
      </Link>
      {/* Sarlavha BITTA qator: raqam → holat → prioritet → bosqichlar (badge'lar
          terminal kartalari bilan bir tilda). Fayl nomi bu yerda emas — u
          «Fayllar» blokida; fayl yo'qligi esa amalga undaydi — description. */}
      <PageHeader
        title={order.number}
        titleAside={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={order.status} />
            <span
              className={`rounded-sm px-2 py-0.5 text-xs font-black uppercase tracking-wider ${
                PRIORITY_BADGE_CLASSES[order.priority] ??
                "bg-muted text-muted-foreground"
              }`}
            >
              {PRIORITY_LABELS[order.priority] ?? order.priority}
            </span>
            {/* Bosqichlar shu qatorda — «raqam → holat → qayerda turibdi» bitta
                satr; alohida qator vertikal joy olib, sarlavhadan uzilardi */}
            {stagesSummary.length > 0 && (
              <>
                <span className="mx-1 h-5 w-px bg-border" aria-hidden="true" />
                <StagePipeline stages={stagesSummary} showLabels />
              </>
            )}
          </div>
        }
        description={
          order.project_name ? undefined : "Project fayl hali yuklanmagan"
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {canManage && !isTerminal && <EditOrder order={order} />}
            {canManage && order.status === "draft" && (
              <LoadingButton
                loading={confirm.isPending}
                onClick={() => confirm.mutate()}
              >
                <CheckCheck /> Tasdiqlash
              </LoadingButton>
            )}
            {canUpload && (
              <>
                <input
                  ref={fileInput}
                  type="file"
                  accept=".project"
                  className="hidden"
                  onChange={(e) =>
                    e.target.files?.[0] && upload(e.target.files[0])
                  }
                />
                <LoadingButton
                  variant="outline"
                  loading={uploading}
                  onClick={() => fileInput.current?.click()}
                >
                  <FileUp /> Project fayl yuklash
                </LoadingButton>
              </>
            )}
            {/* Texnolog ham uzatadi: faylni va marshrutni u tayyorlaydi, ya'ni
                buyurtma tayyorligini birinchi bo'lib u biladi (backend ham
                `ManagerOrTexnologUser` bilan ochilgan). */}
            {(canManage || isTexnolog) &&
              order.status === "technical_review" &&
              order.project_uuid && (
                <LoadingButton
                  loading={start.isPending}
                  onClick={() => start.mutate()}
                >
                  <Play /> Ishlab chiqarishga uzatish
                </LoadingButton>
              )}
            <Button asChild variant="outline">
              <Link to="/anketa/$orderId" params={{ orderId }}>
                <ClipboardList /> Anketa
              </Link>
            </Button>
            {order.project_uuid != null && (
              <Button asChild variant="outline">
                <Link to="/cutmap/$orderId" params={{ orderId }}>
                  <MapIcon /> Kesish xaritalari
                </Link>
              </Button>
            )}
            {canManage && order.status === "completed" && (
              <Button onClick={() => setDeliverOpen(true)}>
                <Truck /> Topshirildi
              </Button>
            )}
            {/* Bekor qilish — buzg'unchi amal, asosiy tugmalar bilan bir xil
                og'irlikda emas (to'liq qizil har sahifada baqirardi); tasdiq
                dialogi bor. */}
            {canManage && !isTerminal && order.status !== "cancelled" && (
              <Button
                variant="outline"
                className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() => setCancelOpen(true)}
              >
                <XCircle /> Bekor qilish
              </Button>
            )}
            {isSuperuser(currentUser) &&
              !isTerminal &&
              order.status === "cancelled" && (
                <Button
                  variant="destructive"
                  onClick={() => setDeleteOpen(true)}
                >
                  <Trash2 /> O'chirish
                </Button>
              )}
          </div>
        }
      />

      {canUpload && (
        // biome-ignore lint/a11y/noStaticElementInteractions: drop zone — klaviatura uchun yonidagi tugma bor
        // biome-ignore lint/a11y/useKeyWithClickEvents: klaviatura yo'li headerdagi "Project fayl yuklash" tugmasi
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            const f = e.dataTransfer.files?.[0]
            if (!f) return
            if (!f.name.endsWith(".project")) {
              toast.error("Faqat .project fayl qabul qilinadi")
              return
            }
            upload(f)
          }}
          onClick={() => fileInput.current?.click()}
          className={`mb-6 flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/30 text-muted-foreground hover:border-primary/50"
          } ${uploading ? "opacity-60" : ""}`}
        >
          {/* Doimiy animatsiya YO'Q (shovqin); faqat fayl sudrab kelinganda
              javob: matn almashadi, ikonka sakraydi — «shu yerga» degani */}
          <FileUp className={`size-6 ${dragOver ? "animate-bounce" : ""}`} />
          <span className="font-medium">
            {uploading
              ? "Yuklanmoqda..."
              : dragOver
                ? "Qo'yib yuboring"
                : ".project faylni shu yerga tashlang yoki bosing"}
          </span>
          <span className="text-xs">
            GibLab eksport fayli — yuklangach tahlil avtomatik boshlanadi
          </span>
        </div>
      )}

      {/* Bekor qilingan buyurtma: sabab va kim — banner (kartada 2 katak sifatida
          yo'qolib ketardi). Kim bekor qilgani bazada bor edi, ko'rsatilmasdi. */}
      {order.status === "cancelled" && (
        <div className="mb-6 flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
          <div>
            <div className="font-medium">
              Bekor qilingan
              {order.cancelled_by_name ? ` — ${order.cancelled_by_name}` : ""}
            </div>
            {order.cancel_reason && (
              <div className="text-muted-foreground">{order.cancel_reason}</div>
            )}
          </div>
        </div>
      )}

      {isTexnolog && order.edit_blocked_reason && (
        <div className="mb-6 flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
          <Lock className="mt-0.5 size-4 shrink-0 text-amber-600" />
          <div>
            {/* Aniq NIMA qulflangani: menejerning «Tahrirlash»i (narx, muddat,
                prioritet) baribir ishlaydi — qulf faylga va marshrutga tegishli */}
            <div className="font-medium">
              Fayl va marshrutni o'zgartirib bo'lmaydi
            </div>
            <div className="text-muted-foreground">
              {order.edit_blocked_reason}
            </div>
          </div>
        </div>
      )}

      <Card className="mb-6 grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Meta label="Mijoz" value={order.client_name} />
        <Meta
          label="Topshirish sanasi"
          value={
            <span
              className={
                deadlineToneValue === "overdue"
                  ? "font-semibold text-destructive"
                  : deadlineToneValue === "today"
                    ? "font-semibold text-amber-600"
                    : ""
              }
            >
              {formatDate(order.deadline)}
              {deadlineToneValue === "overdue"
                ? " · muddati o'tgan"
                : deadlineToneValue === "today"
                  ? " · bugun"
                  : ""}
            </span>
          }
        />
        <Meta label="Umumiy narx" value={formatMoney(order.amount)} />
        <Meta
          label="Boshlang'ich to'lov"
          value={formatMoney(order.advance_payment)}
        />
        <Meta
          label="Qoldiq to'lov"
          value={
            order.amount != null ? formatMoney(remainingPayment(order)) : "—"
          }
        />
        {/* Birliklar bilan — «37 / 111» yalang'och raqam nimaligini aytmasdi */}
        <Meta
          label="Detallar"
          value={
            <>
              <span className="num">{order.parts_count}</span> xil ·{" "}
              <span className="num">{order.instances_count}</span> dona
            </>
          }
        />
        <Meta label="Ochilgan" value={formatDateTime(order.created_at)} />
        {/* DOIM 8 katak = 4 ustunda 2 to'liq qator: 9-chisi yolg'iz qatorda
            qolardi. «Fayl yuklangan» — Fayllar blokidagi qatorda sana bor;
            topshirilganda oxirgi tahrir o'rnida topshirish vaqti (u eng
            oxirgi voqea); bekor ma'lumoti tepadagi bannerda. */}
        {order.delivered_at ? (
          <Meta
            label="Topshirilgan"
            value={formatDateTime(order.delivered_at)}
          />
        ) : (
          // Oxirgi AMAL — audit logdan: qachon · kim, ostida nima («matritsa
          // tahrirlandi»). `updated_at` faqat vaqt edi — «kim?» ga javob yo'q edi.
          <Meta
            label="Oxirgi amal"
            value={
              order.last_action_at ? (
                <>
                  {formatDateTime(order.last_action_at)}
                  {order.last_action_by_name &&
                    ` · ${order.last_action_by_name}`}
                  {order.last_action && (
                    <div className="text-xs font-normal text-muted-foreground">
                      {AUDIT_ACTION_LABELS[order.last_action] ??
                        order.last_action}
                    </div>
                  )}
                </>
              ) : order.updated_at && order.updated_at !== order.created_at ? (
                formatDateTime(order.updated_at)
              ) : (
                "—"
              )
            }
          />
        )}
      </Card>

      {/* Texnolog ham tanlaydi: marshrutni u chizadi, ya'ni qaysi stanok
          qaysi ishni bajarishini yaxshiroq biladi. */}
      {(canManage || isTexnolog) && canEdit && order.project_uuid && (
        // key: buyurtma almashsa ichki `selection` holati qaytadan seed bo'lsin
        <MachineAssign key={order.id} order={order} />
      )}

      {isTexnolog ? (
        <Tabs defaultValue="matrix">
          {/* Tab'lar chapda, matritsa boshqaruvi (qidiruv, hisob, tahrir) o'sha
              qatorning o'ng tomonida — portal orqali; jadval ustida alohida
              qator yo'q. Slot faqat matritsa tabida to'ladi. */}
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <TabsList>
              <TabsTrigger value="matrix">Detallar matritsasi</TabsTrigger>
              <TabsTrigger value="custom">
                Nostandart detallar{customCount ? ` (${customCount})` : ""}
              </TabsTrigger>
              {hardware.length > 0 && (
                <TabsTrigger value="hardware">
                  Furnituralar ({hardware.length})
                </TabsTrigger>
              )}
            </TabsList>
            <div ref={setMatrixToolbarEl} className="empty:hidden" />
          </div>
          <TabsContent value="matrix">
            <OrderMatrix
              orderId={id}
              editable={canEdit}
              toolbarContainer={matrixToolbarEl}
            />
          </TabsContent>
          <TabsContent value="custom">
            <CustomRoutes orderId={id} editable={canEdit} />
          </TabsContent>
          <TabsContent value="hardware">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-36">Kod</TableHead>
                  <TableHead>Nomi</TableHead>
                  <TableHead className="w-24 text-right">Soni</TableHead>
                  <TableHead className="w-20">Birlik</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hardware.map((m, i) => (
                  <TableRow key={i}>
                    <TableCell className="num text-xs text-muted-foreground">
                      {m.code ?? "—"}
                    </TableCell>
                    <TableCell className="font-medium">{m.name}</TableCell>
                    <TableCell className="num text-right font-semibold">
                      {m.count}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {m.unit}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TabsContent>
        </Tabs>
      ) : (
        <>
          {/* Matritsani faqat texnolog tahrirlaydi — bu shox unga tegishli emas */}
          <SectionTitle>Detallar matritsasi</SectionTitle>
          <OrderMatrix orderId={id} editable={false} />
        </>
      )}

      {(order.files ?? []).length > 0 && (
        <div className="mt-8">
          <SectionTitle>Fayllar</SectionTitle>
          <ul className={cn(cardSurface, "divide-y")}>
            {(order.files ?? [])
              .filter((f) => f.kind !== "scx")
              .map((f) => (
                <li
                  key={f.id}
                  className="flex items-center gap-3 px-4 py-2.5 text-sm"
                >
                  <FileText className="size-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{f.filename}</div>
                    <div className="num text-xs text-muted-foreground">
                      {FILE_KIND_LABELS[f.kind] ?? f.kind} ·{" "}
                      {formatBytes(f.size)} · {formatDateTime(f.created_at)}
                    </div>
                  </div>
                  <Button
                    asChild
                    variant="outline"
                    size="icon-sm"
                    title="Yuklab olish"
                  >
                    <a href={fileUrl(f.id)} download>
                      <Download />
                    </a>
                  </Button>
                </li>
              ))}
            {scxFiles.length > 0 && (
              <li className="px-4 py-2.5 text-sm">
                <div className="flex items-center gap-3">
                  <FileCode2 className="size-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">SCX dasturlari</div>
                    <div className="num text-xs text-muted-foreground">
                      {scxFiles.length} ta · prisadka ·{" "}
                      {formatBytes(
                        scxFiles.reduce((sum, f) => sum + (f.size ?? 0), 0),
                      )}
                    </div>
                  </div>
                  {isTexnolog && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-muted-foreground"
                      disabled={regenScx.isPending}
                      title="Fayllarni nusxa QR'i bilan qayta nomlash (Nanxing skan mosligi)"
                      onClick={() => regenScx.mutate()}
                    >
                      {regenScx.isPending
                        ? "Yaratilmoqda..."
                        : "Qayta yaratish"}
                    </Button>
                  )}
                  <Button asChild variant="outline" size="sm">
                    <a href={fileUrl("scx.zip")} download>
                      <Download /> ZIP
                    </a>
                  </Button>
                </div>
                <details className="mt-1.5 pl-7">
                  <summary className="cursor-pointer text-xs text-muted-foreground">
                    Ro'yxatni ko'rsatish
                  </summary>
                  <ul className="mt-1 grid gap-x-6 gap-y-0.5 sm:grid-cols-2 lg:grid-cols-3">
                    {scxFiles.map((f) => (
                      <li key={f.id} className="truncate text-xs">
                        <a
                          className="text-primary hover:underline"
                          href={fileUrl(f.id)}
                          download
                        >
                          {f.filename}
                        </a>
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            )}
          </ul>
        </div>
      )}

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Buyurtmani butunlay o'chirish"
        description={`${order.number} — buyurtma, uning detallari, marshrutlari va diskdagi fayllari (.project, SCX, anketa rasmlari) BUTUNLAY o'chadi. Bu amalni QAYTARIB BO'LMAYDI. Bekor qilish tarixi (audit izi) saqlanadi.`}
        confirmText="BUTUNLAY O'CHIRISH"
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />

      <ConfirmDialog
        open={deliverOpen}
        onOpenChange={setDeliverOpen}
        title="Buyurtmani topshirish"
        description={`${order.number} mijozga topshirildi deb belgilanadi. Sana avtomatik yoziladi.`}
        confirmText="TOPSHIRILDI"
        loading={deliver.isPending}
        onConfirm={() => deliver.mutate()}
      />

      <Dialog
        open={cancelOpen}
        onOpenChange={(o) => {
          setCancelOpen(o)
          if (!o) setCancelReason("")
        }}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Buyurtmani bekor qilish</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Barcha terminallardan vazifalar darhol olib tashlanadi. Bajarilgan
            scanlar tarixda saqlanadi.
          </p>
          <Input
            placeholder="Bekor qilish sababi"
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
          />
          <DialogFooter>
            <LoadingButton
              variant="destructive"
              disabled={cancelReason.trim().length < 3}
              loading={cancel.isPending}
              onClick={() => cancel.mutate()}
            >
              Bekor qilish
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 text-sm font-medium">{value}</div>
    </div>
  )
}
