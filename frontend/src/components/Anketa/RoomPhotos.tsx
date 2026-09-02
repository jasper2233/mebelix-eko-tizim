// Xona rasmlari — anketa JSONB'sida EMAS, `OrderFile(kind=DOCUMENT,
// meta.room_id)` da saqlanadi, shuning uchun avtosaqlash bilan aralashmaydi
// va o'z mutatsiyalarini yuritadi.

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ImagePlus, X } from "lucide-react"
import { useRef, useState } from "react"
import { toast } from "sonner"

import { type OrderFileRead, OrdersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { API_BASE, handleError } from "@/utils"

const MAX_PHOTOS = 6
const MAX_PHOTO_MB = 5
// Backend ro'yxati bilan bir xil: orders/survey.py `_ROOM_PHOTO_TYPES`
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"]

/** Xona uchun taxminiy ko'rinish rasmlari — mijoz ko'rsatgan namuna/render.
 *  Butun panel drop-zona; rasm bosilsa to'liq hajmda ochiladi. */
export function RoomPhotos({
  orderId,
  roomId,
  photos,
  canEdit,
}: {
  orderId: number
  roomId: string
  photos: OrderFileRead[]
  canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [preview, setPreview] = useState<OrderFileRead | null>(null)
  const [toRemove, setToRemove] = useState<OrderFileRead | null>(null)
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["orders", orderId] })

  const upload = useMutation({
    mutationFn: (file: File) =>
      OrdersService.uploadRoomPhoto({
        path: { order_id: orderId },
        body: { room_id: roomId, file },
      }),
    onSuccess: refresh,
    onError: handleError,
  })
  const remove = useMutation({
    mutationFn: (fileId: number) =>
      OrdersService.deleteRoomPhoto({
        path: { order_id: orderId, file_id: fileId },
      }),
    onSuccess: () => {
      setToRemove(null)
      refresh()
    },
    onError: handleError,
  })

  // Serverga bormasdan tekshiramiz — menejer xatoni darhol ko'rsin
  const add = (files: FileList | null) => {
    const list = Array.from(files ?? [])
    let free = MAX_PHOTOS - photos.length
    for (const f of list) {
      if (!ACCEPTED.includes(f.type)) {
        toast.error(`${f.name}: faqat JPG, PNG yoki WEBP`)
        continue
      }
      if (f.size > MAX_PHOTO_MB * 1024 * 1024) {
        toast.error(`${f.name}: ${MAX_PHOTO_MB} MB dan katta`)
        continue
      }
      if (free <= 0) {
        toast.error(`Bitta xonaga ${MAX_PHOTOS} tadan ko'p rasm sig'maydi`)
        break
      }
      free--
      upload.mutate(f)
    }
  }

  if (!canEdit && !photos.length) return null

  const src = (fileId: number) =>
    `${API_BASE}/api/v1/orders/${orderId}/files/${fileId}`
  const full = photos.length >= MAX_PHOTOS

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-muted-foreground text-sm">
          Xona rasmi{" "}
          <span className="text-xs">(mijoz ko'rsatgan taxminiy ko'rinish)</span>
        </span>
        {photos.length > 0 && (
          <span className="text-muted-foreground text-xs num">
            {photos.length}/{MAX_PHOTOS}
          </span>
        )}
      </div>

      {/* biome-ignore lint/a11y/noStaticElementInteractions: faqat drag&drop — klaviatura yo'li "Rasm qo'shish" tugmasi */}
      <div
        onDragOver={
          canEdit
            ? (e) => {
                e.preventDefault()
                setDragOver(true)
              }
            : undefined
        }
        onDragLeave={canEdit ? () => setDragOver(false) : undefined}
        onDrop={
          canEdit
            ? (e) => {
                e.preventDefault()
                setDragOver(false)
                add(e.dataTransfer.files)
              }
            : undefined
        }
        className={`rounded-lg border-2 border-dashed p-3 transition-colors ${
          dragOver ? "border-primary bg-primary/5" : "border-transparent"
        }`}
      >
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {photos.map((p) => (
            <div key={p.id} className="group relative">
              <button
                type="button"
                onClick={() => setPreview(p)}
                className="block w-full overflow-hidden rounded-md border focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
                aria-label={`${p.filename} — kattalashtirish`}
              >
                <img
                  src={src(p.id)}
                  alt={p.filename}
                  crossOrigin="use-credentials"
                  className="aspect-square w-full object-cover transition-transform duration-200 group-hover:scale-105"
                />
              </button>
              {canEdit && (
                <button
                  type="button"
                  aria-label={`${p.filename} — o'chirish`}
                  onClick={() => setToRemove(p)}
                  className="absolute top-1 right-1 rounded-full border bg-background/90 p-1.5 text-destructive shadow-sm backdrop-blur focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
                >
                  <X className="size-4" />
                </button>
              )}
            </div>
          ))}

          {canEdit && !full && (
            <>
              <input
                ref={input}
                type="file"
                accept={ACCEPTED.join(",")}
                multiple
                className="hidden"
                onChange={(e) => {
                  add(e.target.files)
                  e.target.value = ""
                }}
              />
              <button
                type="button"
                disabled={upload.isPending}
                onClick={() => input.current?.click()}
                className="flex aspect-square flex-col items-center justify-center gap-1 rounded-md border border-dashed p-1 text-center text-muted-foreground text-xs transition-colors hover:border-primary/60 hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 disabled:opacity-50"
              >
                {upload.isPending ? (
                  "Yuklanmoqda..."
                ) : (
                  <>
                    <ImagePlus className="size-5" />
                    Rasm qo'shish
                  </>
                )}
              </button>
            </>
          )}
        </div>

        {canEdit && (
          <p className="mt-2 text-muted-foreground text-xs">
            {full
              ? `Xonaga ${MAX_PHOTOS} ta rasm yuklangan — yangisini qo'shish uchun birortasini o'chiring.`
              : `Sudrab tashlang yoki tanlang · JPG, PNG, WEBP · ${MAX_PHOTO_MB} MB gacha`}
          </p>
        )}
      </div>

      <Dialog open={!!preview} onOpenChange={(v) => !v && setPreview(null)}>
        <DialogContent className="gap-2 p-3 sm:max-w-4xl">
          <DialogHeader className="px-1">
            <DialogTitle className="truncate text-base">
              {preview?.filename}
            </DialogTitle>
          </DialogHeader>
          {preview && (
            <img
              src={src(preview.id)}
              alt={preview.filename}
              crossOrigin="use-credentials"
              className="max-h-[75vh] w-full rounded-md object-contain"
            />
          )}
          <a
            href={preview ? src(preview.id) : "#"}
            target="_blank"
            rel="noreferrer"
            className="px-1 text-muted-foreground text-xs underline-offset-2 hover:underline"
          >
            Asl hajmda yangi oynada ochish
          </a>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!toRemove}
        onOpenChange={(v) => !v && setToRemove(null)}
        title="Rasm o'chirilsinmi?"
        description={`${toRemove?.filename ?? "Rasm"} serverdan butunlay o'chadi — anketa rasmlari tarix uchun saqlanmaydi.`}
        confirmText="O'chirish"
        destructive
        loading={remove.isPending}
        onConfirm={() => toRemove && remove.mutate(toRemove.id)}
      />
    </div>
  )
}
