/** Texnolog tomoni: Bazis modellari va yig'uvchiga beriladigan havola.
 *
 * Buyurtma sahifasidagi «3D model» tabi. Bitta buyurtmada bir nechta model
 * bo'ladi — har mahsulotga bittadan, chunki Bazis har mahsulotni alohida
 * faylga eksport qiladi.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangle,
  Check,
  Copy,
  Link2,
  Link2Off,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useRef, useState } from "react"
import { toast } from "sonner"
import { OrdersService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { LoadingButton } from "@/components/ui/loading-button"
import { API_BASE, handleError } from "@/utils"

const thumbUrl = (orderId: number, fileId: number) =>
  `${API_BASE}/api/v1/orders/${orderId}/bazis/${fileId}/thumb`

/** To'liq manzilni brauzer yig'adi: server o'z domenini bilmaydi. */
const shareUrl = (token: string) => `${window.location.origin}/3d/${token}`

function ShareBlock({
  orderId,
  token,
  canShare,
}: {
  orderId: number
  token: string | null
  canShare: boolean
}) {
  const qc = useQueryClient()
  const [copied, setCopied] = useState(false)
  const yangilash = () =>
    qc.invalidateQueries({ queryKey: ["order-bazis", orderId] })

  const open = useMutation({
    mutationFn: () =>
      OrdersService.openOrderShare({ path: { order_id: orderId } }),
    onSuccess: yangilash,
    onError: handleError,
  })
  const close = useMutation({
    mutationFn: () =>
      OrdersService.closeOrderShare({ path: { order_id: orderId } }),
    onSuccess: () => {
      toast.success("Havola yopildi")
      yangilash()
    },
    onError: handleError,
  })

  // Direktor havolani ochmaydi ham, yopmaydi ham — yo'q havola haqida
  // unga aytadigan gap yo'q (backendda ham `ManagerOrTexnologUser`).
  if (!token && !canShare) return null

  if (!token) {
    return (
      <Card className="flex flex-col items-start gap-3 p-4 sm:flex-row sm:items-center">
        <Link2 className="size-5 shrink-0 text-muted-foreground" />
        <div className="flex-1">
          <div className="font-medium">Yig'uvchi uchun havola</div>
          <div className="text-muted-foreground text-sm">
            Havolani ochsangiz, uni olgan har kim modelni ko'ra oladi — tizimga
            kirmasdan. Boshqa buyurtmalar ochilmaydi.
          </div>
        </div>
        <LoadingButton
          onClick={() => open.mutate()}
          loading={open.isPending}
          disabled={open.isPending}
        >
          <Link2 /> Havolani ochish
        </LoadingButton>
      </Card>
    )
  }

  const url = shareUrl(token)
  return (
    <Card className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
      {/* QR — ustaning telefoni bilan bir skanda ochiladi, havolani terib
          o'tirmaydi. Ekrandan ham, chop etilgan varaqdan ham ishlaydi. */}
      <div className="mx-auto shrink-0 rounded-xl border border-border bg-white p-2 sm:mx-0">
        <QRCodeSVG value={url} size={116} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-medium">Havola ochiq</div>
        <code className="mt-1 block truncate rounded-lg bg-muted px-2 py-1.5 font-mono text-xs">
          {url}
        </code>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              await navigator.clipboard.writeText(url)
              setCopied(true)
              setTimeout(() => setCopied(false), 1600)
            }}
          >
            {copied ? <Check /> : <Copy />}
            {copied ? "Nusxalandi" : "Nusxalash"}
          </Button>
          {canShare && (
            <>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => open.mutate()}
                disabled={open.isPending}
                // Yangilash — havola begonaga tushib qolgandagi yagona chora
                title="Eski havola ishlamay qoladi"
              >
                <RefreshCw /> Yangilash
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => close.mutate()}
                disabled={close.isPending}
              >
                <Link2Off /> Yopish
              </Button>
            </>
          )}
        </div>
      </div>
    </Card>
  )
}

export function BazisPanel({
  orderId,
  canUpload,
  canShare,
}: {
  orderId: number
  /** Faqat texnolog — `.project` bilan bir xil qoida */
  canUpload: boolean
  /** Menejer ham: havolani mijozga ko'pincha u uzatadi */
  canShare: boolean
}) {
  const qc = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [busy, setBusy] = useState(false)

  const state = useQuery({
    queryKey: ["order-bazis", orderId],
    queryFn: async () =>
      (await OrdersService.readOrderBazis({ path: { order_id: orderId } }))
        .data,
  })

  const remove = useMutation({
    mutationFn: (fileId: number) =>
      OrdersService.deleteOrderBazis({
        path: { order_id: orderId, file_id: fileId },
      }),
    onSuccess: () => {
      toast.success("Model o'chirildi")
      qc.invalidateQueries({ queryKey: ["order-bazis", orderId] })
    },
    onError: handleError,
  })

  /** Bir nechta faylni KETMA-KET yuboramiz: har biri serverda 1 soniyagacha
   * CPU oladi, bir vaqtda yuborilsa ishchilar band bo'lib qolardi. */
  const upload = async (files: File[]) => {
    const b3d = files.filter((f) => f.name.toLowerCase().endsWith(".b3d"))
    if (!b3d.length) {
      toast.error("Faqat Bazis .b3d fayli qabul qilinadi")
      return
    }
    setBusy(true)
    try {
      for (const file of b3d) {
        try {
          const { data } = await OrdersService.uploadOrderBazis({
            path: { order_id: orderId },
            body: { file },
          })
          toast.success(
            `${data.product_code} — ${data.panels} detal${data.matched ? "" : " (mahsulot topilmadi)"}`,
          )
        } catch (err) {
          handleError(err)
        }
      }
    } finally {
      setBusy(false)
      qc.invalidateQueries({ queryKey: ["order-bazis", orderId] })
    }
  }

  const models = state.data?.models ?? []

  return (
    <div className="space-y-4">
      <ShareBlock
        orderId={orderId}
        token={state.data?.share_token ?? null}
        canShare={canShare}
      />

      {canUpload && (
        // biome-ignore lint/a11y/noStaticElementInteractions: tashlash maydoni — klaviatura yo'li ichidagi tugma
        // biome-ignore lint/a11y/useKeyWithClickEvents: klaviatura yo'li ichidagi "Fayl tanlash" tugmasi
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            upload([...(e.dataTransfer.files ?? [])])
          }}
          onClick={() => fileInput.current?.click()}
          className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/30 text-muted-foreground hover:border-primary/50"
          } ${busy ? "opacity-60" : ""}`}
        >
          <Upload className={`size-6 ${dragOver ? "animate-bounce" : ""}`} />
          <span className="font-medium">
            {busy
              ? "Yuklanmoqda..."
              : dragOver
                ? "Qo'yib yuboring"
                : "Bazis .b3d fayllarini shu yerga tashlang"}
          </span>
          <span className="text-xs">
            Har mahsulotga bitta fayl — bir vaqtda bir nechtasini tanlash mumkin
          </span>
          <input
            ref={fileInput}
            type="file"
            accept=".b3d"
            multiple
            hidden
            onChange={(e) => {
              upload([...(e.target.files ?? [])])
              e.target.value = ""
            }}
          />
        </div>
      )}

      {models.length === 0 ? (
        <div className="rounded-xl border border-border border-dashed p-8 text-center text-muted-foreground text-sm">
          Hali model yuklanmagan.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {models.map((m) => (
            <Card key={m.file_id} className="flex gap-3 p-3">
              <img
                src={thumbUrl(orderId, m.file_id)}
                alt=""
                className="size-20 shrink-0 rounded-lg bg-muted object-contain"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{m.product_name}</div>
                    <div className="font-mono text-muted-foreground text-xs">
                      {m.product_code} · {m.panels} detal
                    </div>
                  </div>
                  {canUpload && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="-mt-1 -mr-1 size-8"
                      onClick={() => remove.mutate(m.file_id)}
                      disabled={remove.isPending}
                      aria-label="O'chirish"
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  )}
                </div>
                {m.warnings.map((w) => (
                  <div
                    key={w}
                    className="mt-2 flex items-start gap-1.5 text-amber-700 text-xs"
                  >
                    <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
