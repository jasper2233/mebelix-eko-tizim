import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  ArrowLeft,
  CheckCheck,
  ClipboardList,
  FileUp,
  Map as MapIcon,
  Play,
  Truck,
  XCircle,
} from "lucide-react"
import { useRef, useState } from "react"
import { toast } from "sonner"

import { OpenAPI, OrdersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SectionTitle } from "@/components/Common/SectionTitle"
import { StatusBadge } from "@/components/Common/StatusBadge"
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
  formatDate,
  formatDateTime,
  formatMoney,
  isAdmin,
  PRIORITY_LABELS,
  remainingPayment,
  TERMINAL_STATUSES,
} from "@/lib/mes"
import { cn } from "@/lib/utils"
import { crudCallbacks, getOrderQueryOptions } from "@/queries/mes"
import { extractErrorMessage, handleError } from "@/utils"

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
  const { currentUser } = useCurrentUser()
  const fileInput = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [deliverOpen, setDeliverOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState("")

  const role = currentUser?.role
  const admin = isAdmin(currentUser)
  const isManager = admin || role === "manager"
  const isTexnolog = admin || role === "texnolog"

  // ["orders"] prefiksi ["orders", id] va ["orders", id, "matrix"] ni ham
  // qamraydi — qolgan ikki chaqiruv ortiqcha edi.
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["orders"] })
  const cb = (msg: string) => crudCallbacks(queryClient, ["orders"], msg)

  const upload = async (file: File) => {
    setUploading(true)
    try {
      const res = await OrdersService.uploadOrderProject({
        orderId: id,
        formData: { file: file as unknown as string },
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
    mutationFn: () => OrdersService.confirmOrder({ orderId: id }),
    ...cb("Buyurtma tasdiqlandi — texnologga uzatildi"),
  })
  const start = useMutation({
    mutationFn: () => OrdersService.startOrderProduction({ orderId: id }),
    ...cb("Ishlab chiqarishga uzatildi"),
  })
  const deliverCb = cb("Buyurtma topshirildi")
  const deliver = useMutation({
    mutationFn: () => OrdersService.deliverOrder({ orderId: id }),
    ...deliverCb,
    onSuccess: () => {
      deliverCb.onSuccess()
      setDeliverOpen(false)
    },
  })
  const cancelCb = cb("Buyurtma bekor qilindi")
  const cancel = useMutation({
    mutationFn: () =>
      OrdersService.cancelOrder({
        orderId: id,
        requestBody: { reason: cancelReason },
      }),
    ...cancelCb,
    onSuccess: () => {
      cancelCb.onSuccess()
      setCancelOpen(false)
    },
  })
  // Eski buyurtmalarni yangi SCX nomlashga (nusxa QR = fayl nomi, Nanxing skan
  // mosligi) o'tkazish — .project saqlangan bo'lsa bir bosishda
  const regenScx = useMutation({
    mutationFn: () => OrdersService.regenerateOrderScx({ orderId: id }),
    onSuccess: (r) => toast.success(r.message),
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

  const editableStatus =
    order.status === "draft" || order.status === "technical_review"
  const scxFiles = (order.files ?? []).filter((f) => f.kind === "scx")
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
      <PageHeader
        title={order.number}
        description={
          order.project_name
            ? `Fayl nomi: ${order.project_name}`
            : "Project fayl hali yuklanmagan"
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {isManager &&
              !(TERMINAL_STATUSES as readonly string[]).includes(
                order.status,
              ) && <EditOrder order={order} onSaved={invalidate} />}
            {isManager && order.status === "draft" && (
              <LoadingButton
                loading={confirm.isPending}
                onClick={() => confirm.mutate()}
              >
                <CheckCheck /> Tasdiqlash
              </LoadingButton>
            )}
            {isTexnolog && order.status === "technical_review" && (
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
            {isManager &&
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
            {isManager && order.status === "completed" && (
              <Button onClick={() => setDeliverOpen(true)}>
                <Truck /> TOPSHIRILDI
              </Button>
            )}
            {isManager &&
              !(TERMINAL_STATUSES as readonly string[]).includes(
                order.status,
              ) && (
                <Button
                  variant="destructive"
                  onClick={() => setCancelOpen(true)}
                >
                  <XCircle /> Bekor qilish
                </Button>
              )}
          </div>
        }
      />

      {isTexnolog && order.status === "technical_review" && (
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
          }`}
        >
          <FileUp className="size-6" />
          <span className="font-medium">
            {uploading
              ? "Yuklanmoqda..."
              : ".project faylni shu yerga tashlang yoki bosing"}
          </span>
          <span className="text-xs">
            GibLab eksport fayli — yuklangach tahlil avtomatik boshlanadi
          </span>
        </div>
      )}

      <Card className="mb-6 grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
        <Meta label="Holat" value={<StatusBadge status={order.status} />} />
        <Meta label="Mijoz" value={order.client_name} />
        <Meta label="Topshirish sanasi" value={formatDate(order.deadline)} />
        <Meta
          label="Prioritet"
          value={PRIORITY_LABELS[order.priority] ?? order.priority}
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
        <Meta
          label="Detallar / nusxalar"
          value={`${order.parts_count} / ${order.instances_count}`}
        />
        <Meta label="Ochilgan" value={formatDateTime(order.created_at)} />
        <Meta
          label="Oxirgi tahrir"
          value={
            order.updated_at && order.updated_at !== order.created_at
              ? formatDateTime(order.updated_at)
              : "—"
          }
        />
        <Meta
          label="Fayl yuklangan"
          value={
            order.project_loaded_at
              ? formatDateTime(order.project_loaded_at)
              : "—"
          }
        />
        {order.cancel_reason && (
          <Meta label="Bekor sababi" value={order.cancel_reason} />
        )}
        {order.delivered_at && (
          <Meta
            label="Topshirilgan"
            value={formatDateTime(order.delivered_at)}
          />
        )}
      </Card>

      {isManager && editableStatus && order.project_uuid && (
        <MachineAssign order={order} onSaved={invalidate} />
      )}

      {hardware.length > 0 && isTexnolog ? (
        <Tabs defaultValue="matrix">
          <TabsList>
            <TabsTrigger value="matrix">Detallar matritsasi</TabsTrigger>
            <TabsTrigger value="hardware">
              Furnituralar ({hardware.length})
            </TabsTrigger>
          </TabsList>
          <TabsContent value="matrix">
            <OrderMatrix orderId={id} editable={isTexnolog && editableStatus} />
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
          <SectionTitle>Detallar matritsasi</SectionTitle>
          <OrderMatrix orderId={id} editable={isTexnolog && editableStatus} />
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
                  className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm"
                >
                  <span className="truncate font-medium">{f.filename}</span>
                  <span className="text-xs uppercase text-muted-foreground">
                    {f.kind}
                  </span>
                  <a
                    className="shrink-0 text-primary hover:underline"
                    href={`${OpenAPI.BASE}/api/v1/orders/${id}/files/${f.id}`}
                    download
                  >
                    Yuklab olish
                  </a>
                </li>
              ))}
            {scxFiles.length > 0 && (
              <li className="px-4 py-2.5 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">
                    SCX dasturlari ({scxFiles.length} ta)
                  </span>
                  <span className="text-xs uppercase text-muted-foreground">
                    prisadka
                  </span>
                  {isTexnolog && (
                    <button
                      type="button"
                      className="shrink-0 rounded-sm text-xs text-muted-foreground hover:text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50"
                      disabled={regenScx.isPending}
                      title="Fayllarni nusxa QR'i bilan qayta nomlash (Nanxing skan mosligi)"
                      onClick={() => regenScx.mutate()}
                    >
                      {regenScx.isPending
                        ? "Yaratilmoqda..."
                        : "Qayta yaratish"}
                    </button>
                  )}
                  <a
                    className="shrink-0 font-medium text-primary hover:underline"
                    href={`${OpenAPI.BASE}/api/v1/orders/${id}/files/scx.zip`}
                    download
                  >
                    Hammasini yuklab olish (ZIP)
                  </a>
                </div>
                <details className="mt-1.5">
                  <summary className="cursor-pointer text-xs text-muted-foreground">
                    Ro'yxatni ko'rsatish
                  </summary>
                  <ul className="mt-1 grid gap-x-6 gap-y-0.5 sm:grid-cols-2 lg:grid-cols-3">
                    {scxFiles.map((f) => (
                      <li key={f.id} className="truncate text-xs">
                        <a
                          className="text-primary hover:underline"
                          href={`${OpenAPI.BASE}/api/v1/orders/${id}/files/${f.id}`}
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
        open={deliverOpen}
        onOpenChange={setDeliverOpen}
        title="Buyurtmani topshirish"
        description={`${order.number} mijozga topshirildi deb belgilanadi. Sana avtomatik yoziladi.`}
        confirmText="TOPSHIRILDI"
        loading={deliver.isPending}
        onConfirm={() => deliver.mutate()}
      />

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
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
