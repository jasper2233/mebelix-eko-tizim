import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import {
  ArrowLeft,
  CheckCheck,
  FileUp,
  Map as MapIcon,
  Play,
  Truck,
  XCircle,
} from "lucide-react"
import { useRef, useState } from "react"

import { OpenAPI, OrdersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { EditOrder } from "@/components/Orders/EditOrder"
import { MachineAssign } from "@/components/Orders/MachineAssign"
import { OrderMatrix } from "@/components/Orders/OrderMatrix"
import { Button } from "@/components/ui/button"
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
import useCurrentUser from "@/hooks/useCurrentUser"
import useCustomToast from "@/hooks/useCustomToast"
import {
  formatDate,
  formatDateTime,
  formatMoney,
  PRIORITY_LABELS,
} from "@/lib/mes"
import { getOrderQueryOptions } from "@/queries/mes"
import { extractErrorMessage, handleError } from "@/utils"

export const Route = createFileRoute("/_layout/orders/$orderId")({
  component: OrderDetailPage,
  head: () => ({ meta: [{ title: "Buyurtma | MebeliX" }] }),
})

function OrderDetailPage() {
  const { orderId } = Route.useParams()
  const id = Number(orderId)
  const queryClient = useQueryClient()
  const { data: order, isLoading } = useQuery(getOrderQueryOptions(id))
  const { currentUser } = useCurrentUser()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const fileInput = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [deliverOpen, setDeliverOpen] = useState(false)
  const [cancelReason, setCancelReason] = useState("")

  const role = currentUser?.role
  const isAdmin = currentUser?.is_superuser || role === "admin"
  const isManager = isAdmin || role === "manager"
  const isTexnolog = isAdmin || role === "texnolog"

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["orders"] })
    queryClient.invalidateQueries({ queryKey: ["orders", id] })
    queryClient.invalidateQueries({ queryKey: ["orders", id, "matrix"] })
  }

  const upload = async (file: File) => {
    setUploading(true)
    try {
      await OrdersService.uploadOrderProject({
        orderId: id,
        formData: { file: file as unknown as string },
      })
      showSuccessToast("Fayl qabul qilindi va tahlil qilindi")
      invalidate()
    } catch (err) {
      showErrorToast(extractErrorMessage(err as never))
    } finally {
      setUploading(false)
      if (fileInput.current) fileInput.current.value = ""
    }
  }

  const confirm = useMutation({
    mutationFn: () => OrdersService.confirmOrder({ orderId: id }),
    onSuccess: () => showSuccessToast("Buyurtma tasdiqlandi — texnologga uzatildi"),
    onError: handleError(showErrorToast),
    onSettled: invalidate,
  })
  const start = useMutation({
    mutationFn: () => OrdersService.startOrderProduction({ orderId: id }),
    onSuccess: () => showSuccessToast("Ishlab chiqarishga uzatildi"),
    onError: handleError(showErrorToast),
    onSettled: invalidate,
  })
  const deliver = useMutation({
    mutationFn: () => OrdersService.deliverOrder({ orderId: id }),
    onSuccess: () => {
      showSuccessToast("Buyurtma topshirildi")
      setDeliverOpen(false)
    },
    onError: handleError(showErrorToast),
    onSettled: invalidate,
  })
  const cancel = useMutation({
    mutationFn: () =>
      OrdersService.cancelOrder({
        orderId: id,
        requestBody: { reason: cancelReason },
      }),
    onSuccess: () => {
      showSuccessToast("Buyurtma bekor qilindi")
      setCancelOpen(false)
    },
    onError: handleError(showErrorToast),
    onSettled: invalidate,
  })

  if (isLoading || !order) return <Skeleton className="h-96 w-full" />

  const editableStatus =
    order.status === "draft" || order.status === "technical_review"

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
              !["delivered", "cancelled"].includes(order.status) && (
                <EditOrder order={order} onSaved={invalidate} />
              )}
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
              !["delivered", "cancelled"].includes(order.status) && (
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

      <div className="mb-6 grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
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
            order.amount != null
              ? formatMoney(
                  Number(order.amount) - Number(order.advance_payment ?? 0),
                )
              : "—"
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
      </div>

      {isManager && editableStatus && order.project_uuid && (
        <MachineAssign order={order} onSaved={invalidate} />
      )}

      <h2 className="mb-2 text-base font-semibold">Detallar matritsasi</h2>
      <OrderMatrix orderId={id} editable={isTexnolog && editableStatus} />

      {(order.files ?? []).length > 0 && (
        <div className="mt-8">
          <h2 className="mb-2 text-base font-semibold">Fayllar</h2>
          <ul className="divide-y rounded-xl border bg-card">
            {(order.files ?? []).map((f) => (
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
        <DialogContent className="max-w-sm">
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
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 text-sm font-medium">{value}</div>
    </div>
  )
}
