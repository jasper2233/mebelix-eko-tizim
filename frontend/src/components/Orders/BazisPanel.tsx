/** Buyurtma sahifasidagi «3D model» tabi (menejer va direktorda — matritsa ostidagi blok).
 *
 * Tartib ish ketma-ketligi bilan bir xil: 1) xulosa va «Bazis fayl yuklash»;
 * 2) mahsulotlar — har biriga model bormi, u buyurtmaga bog'langanmi; 3) yig'uvchiga
 * havola — OXIRIDA, chunki u model tayyor bo'lgandan keyingi qadam (model yo'q
 * bo'lsa havola bo'sh sahifa ochardi). Bitta buyurtmada bir nechta model bo'ladi —
 * har mahsulotga bittadan, chunki Bazis har mahsulotni alohida faylga eksport qiladi.
 *
 * Nomlash: tab — foydalanuvchi ko'radigan narsa («3D model», ochiq sahifa ham shunday
 * ataladi), fayl amallari — manba fayl («Bazis fayl», `.project` dagi «Project fayl»
 * bilan bir xil).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Box,
  Check,
  Copy,
  FileUp,
  Link2,
  Link2Off,
  RefreshCw,
  Rotate3d,
  Trash2,
  TriangleAlert,
} from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useRef, useState } from "react"
import { toast } from "sonner"
import {
  type BazisModelRead,
  type BazisProductRead,
  type BazisState,
  OrdersService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { QueryError } from "@/components/Common/QueryError"
import { BazisPreviewDialog } from "@/components/Orders/BazisPreview"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, cardSurface } from "@/components/ui/card"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { API_BASE, handleError } from "@/utils"

const thumbUrl = (orderId: number, fileId: number) =>
  `${API_BASE}/api/v1/orders/${orderId}/bazis/${fileId}/thumb`

/** To'liq manzilni brauzer yig'adi: server o'z domenini bilmaydi. */
const shareUrl = (token: string) => `${window.location.origin}/3d/${token}`

/** `["orders", id]` OSTIDA: `.project` qayta yuklansa (mahsulotlar almashadi) va WS
 * `order.*` hodisasida sahifa `["orders"]` ni invalidatsiya qiladi — bog'lanish holati
 * va tab yorlig'idagi hisob ham shu bilan yangilanadi */
const bazisKey = (orderId: number) => ["orders", orderId, "bazis"] as const

/** Panel va tab sarlavhasi BITTA so'rovni ulashadi (bir xil kalit — ikkinchi so'rov ketmaydi) */
export const useOrderBazis = (orderId: number, enabled = true) =>
  useQuery({
    queryKey: bazisKey(orderId),
    enabled,
    queryFn: async () =>
      (await OrdersService.readOrderBazis({ path: { order_id: orderId } }))
        .data,
  })

/** Ro'yxat qatori: buyurtma mahsuloti va uning modeli, yoki buyurtmada kodi yo'q model */
type Qator = {
  key: string
  product: BazisProductRead | null
  model: BazisModelRead | undefined
}

/** Qatorlar va ularning hisobi — panel ham, tab sarlavhasi ham shundan o'qiydi */
export function bazisHolati(state: BazisState) {
  const byCode = new Map(state.models.map((m) => [m.product_code, m]))
  const bogLanmagan = state.models.filter((m) => !m.matched)
  const qatorlar: Qator[] = [
    // Muammo birinchi: bog'lanmagan model — ustaga ishlamaydigan yagona holat
    ...bogLanmagan.map((m) => ({
      key: `m${m.file_id}`,
      product: null,
      model: m,
    })),
    ...state.products.map((p, i) => ({
      key: `p${i}`,
      product: p,
      model: byCode.get(p.code),
    })),
  ]
  return {
    qatorlar,
    mahsulotlar: state.products.length,
    modelliMahsulot: state.products.filter((p) => byCode.has(p.code)).length,
    bogLanmagan: bogLanmagan.length,
    modellar: state.models.length,
  }
}

function ShareBlock({
  orderId,
  token,
  canShare,
  hasModels,
}: {
  orderId: number
  token: string | null
  canShare: boolean
  hasModels: boolean
}) {
  const qc = useQueryClient()
  const [copied, setCopied] = useState(false)
  /** Ikkalasi ham ustalardagi havolani O'LDIRADI — bir bosishda emas, so'rab */
  const [tasdiq, setTasdiq] = useState<"yangilash" | "yopish" | null>(null)
  const yangilash = () => qc.invalidateQueries({ queryKey: bazisKey(orderId) })

  const open = useMutation({
    mutationFn: () =>
      OrdersService.openOrderShare({ path: { order_id: orderId } }),
    onSuccess: () => {
      setTasdiq(null)
      yangilash()
    },
    onError: handleError,
  })
  const close = useMutation({
    mutationFn: () =>
      OrdersService.closeOrderShare({ path: { order_id: orderId } }),
    onSuccess: () => {
      toast.success("Havola yopildi")
      setTasdiq(null)
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
            {hasModels
              ? "Havolani ochsangiz, uni olgan har kim modelni ko'ra oladi — tizimga kirmasdan. Boshqa buyurtmalar ochilmaydi."
              : "Model yuklangandan keyin ochiladi — hozir havola bo'sh sahifa ochardi."}
          </div>
        </div>
        <LoadingButton
          onClick={() => open.mutate()}
          loading={open.isPending}
          disabled={open.isPending || !hasModels}
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
        <div className="font-medium">Yig'uvchi uchun havola ochiq</div>
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
              {/* Yangilash — havola begonaga tushib qolgandagi yagona chora */}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setTasdiq("yangilash")}
                disabled={open.isPending}
              >
                <RefreshCw /> Yangilash
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setTasdiq("yopish")}
                disabled={close.isPending}
              >
                <Link2Off /> Yopish
              </Button>
            </>
          )}
        </div>
      </div>
      <ConfirmDialog
        open={tasdiq !== null}
        onOpenChange={(ochiq) => !ochiq && setTasdiq(null)}
        title={tasdiq === "yopish" ? "Havolani yopish" : "Havolani yangilash"}
        description={
          tasdiq === "yopish"
            ? "Havola va QR shu zahoti ishlamay qoladi — ustalar modelni ocholmaydi."
            : "Eski havola va QR endi ochilmaydi — ustalarga yangisini berish kerak bo'ladi."
        }
        confirmText={tasdiq === "yopish" ? "Yopish" : "Yangilash"}
        destructive
        loading={open.isPending || close.isPending}
        onConfirm={() => (tasdiq === "yopish" ? close.mutate() : open.mutate())}
      />
    </Card>
  )
}

/** Amber ogohlantirish qatori — sahifadagi boshqa ogohlantirishlar bilan bir shakl */
function Ogoh({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-1 flex items-start gap-1.5 text-amber-700 text-xs">
      <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </div>
  )
}

function ModelQatori({
  orderId,
  qator,
  canUpload,
  onPreview,
  onDelete,
}: {
  orderId: number
  qator: Qator
  canUpload: boolean
  onPreview: (m: BazisModelRead) => void
  onDelete: (m: BazisModelRead) => void
}) {
  const { product, model } = qator
  const bogLanmagan = model !== undefined && !model.matched
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 sm:flex-nowrap">
      {model ? (
        <button
          type="button"
          onClick={() => onPreview(model)}
          title="3D ko'rinishni ochish"
          className="shrink-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <img
            src={thumbUrl(orderId, model.file_id)}
            alt=""
            className="size-14 rounded-lg bg-muted object-contain"
          />
        </button>
      ) : (
        <div className="flex size-14 shrink-0 items-center justify-center rounded-lg border border-dashed text-muted-foreground/50">
          <Box className="size-5" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium">
          {product?.name ?? model?.product_name}
        </div>
        <div className="num text-muted-foreground text-xs">
          {product?.code ?? model?.product_code}
          {product && ` · ${product.count} dona`}
          {model && ` · ${model.panels} detal`}
        </div>
        {bogLanmagan && (
          <Ogoh>
            Buyurtmada bu kodli mahsulot yo'q — ustalar chekdagi Detal ID bilan
            detal joyini topa olmaydi. Fayl boshqa buyurtmaniki bo'lishi mumkin:
            o'chiring va buyurtmaning o'z Bazis faylini yuklang.
          </Ogoh>
        )}
        {model?.warnings.map((w) => (
          <Ogoh key={w}>{w}</Ogoh>
        ))}
      </div>
      {/* Telefonda holat va amallar ikkinchi qatorga, matn ostiga tushadi */}
      <div className="flex w-full shrink-0 items-center gap-2 pl-[4.25rem] sm:w-auto sm:pl-0">
        {!model ? (
          <Badge variant="outline" className="text-muted-foreground">
            Model yo'q
          </Badge>
        ) : bogLanmagan ? (
          <Badge
            variant="outline"
            className="border-amber-500/40 bg-amber-500/10 text-amber-700"
          >
            <TriangleAlert /> Bog'lanmagan
          </Badge>
        ) : (
          <Badge>Model bor</Badge>
        )}
        {model && (
          <Button variant="outline" size="sm" onClick={() => onPreview(model)}>
            <Rotate3d /> Ko'rish
          </Button>
        )}
        {model && canUpload && (
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={() => onDelete(model)}
            aria-label="Modelni o'chirish"
            title="Modelni o'chirish"
          >
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>
    </li>
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
  const [ochiriladi, setOchiriladi] = useState<BazisModelRead | null>(null)
  const [korish, setKorish] = useState<BazisModelRead | null>(null)

  const state = useOrderBazis(orderId)

  const remove = useMutation({
    mutationFn: (fileId: number) =>
      OrdersService.deleteOrderBazis({
        path: { order_id: orderId, file_id: fileId },
      }),
    onSuccess: () => {
      toast.success("Model o'chirildi")
      setOchiriladi(null)
      qc.invalidateQueries({ queryKey: bazisKey(orderId) })
    },
    onError: handleError,
  })

  /** Bir nechta faylni KETMA-KET yuboramiz: har biri serverda 1.7 s gacha
   * CPU oladi, bir vaqtda yuborilsa ishchilar band bo'lib qolardi.
   *
   * Buyurtmaga mos bo'lmagan fayl (kodi yoki nomi `.project` dagidan boshqa)
   * serverda 409 bilan rad etiladi — xabar o'z toast'ida, qolganlari davom etadi. */
  const inFlight = useRef(false)
  const upload = async (files: File[]) => {
    const b3d = files.filter((f) => f.name.toLowerCase().endsWith(".b3d"))
    if (!b3d.length) {
      toast.error("Faqat Bazis .b3d fayli qabul qilinadi")
      return
    }
    // Yuklash davomida yangi tashlash/tanlash YUTILADI ($orderId.tsx dagi `.project`
    // bilan bir xil): parallel partiya ketma-ketlikni buzar va birining 409 dialogini
    // ikkinchisining bo'sh ro'yxati yopib yuborardi
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    try {
      for (const file of b3d) {
        try {
          const { data } = await OrdersService.uploadOrderBazis({
            path: { order_id: orderId },
            body: { file },
          })
          toast.success(`${data.product_code} — ${data.panels} detal`)
        } catch (err) {
          handleError(err)
        }
      }
    } finally {
      inFlight.current = false
      setBusy(false)
      qc.invalidateQueries({ queryKey: bazisKey(orderId) })
    }
  }

  // Holat kelmaguncha havola bloki CHIZILMAYDI: ilgari yuklanish va xato
  // paytida "havola yo'q" kartochkasi chiqardi, uning «Havolani ochish»
  // tugmasi esa YANGI token berib, ustalardagi ishlab turgan havolani o'ldirardi.
  if (state.isPending) return <Skeleton className="h-48 w-full" />
  if (state.isError) return <QueryError onRetry={() => state.refetch()} />

  const holat = bazisHolati(state.data)
  // Fayl buyurtma mahsulotiga bog'lanishi SHART — mahsulotsiz (`.project` yo'q)
  // buyurtmada yuklash ma'nosiz, server ham rad etadi
  const yuklash = canUpload && holat.mahsulotlar > 0
  const drop = yuklash
    ? {
        onDragOver: (e: React.DragEvent) => {
          e.preventDefault()
          setDragOver(true)
        },
        onDragLeave: () => setDragOver(false),
        onDrop: (e: React.DragEvent) => {
          e.preventDefault()
          setDragOver(false)
          upload([...(e.dataTransfer.files ?? [])])
        },
      }
    : {}

  return (
    <div className="space-y-4">
      {/* Xulosa + yuklash: `.project` dagi «Project fayl yuklash» bilan bir shakl */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-muted-foreground text-sm">
          {holat.mahsulotlar > 0
            ? holat.modellar === 0
              ? `${holat.mahsulotlar} ta mahsulot — 3D model hali yuklanmagan`
              : holat.modelliMahsulot === 0
                ? `${holat.mahsulotlar} ta mahsulotning hech birida mos 3D model yo'q`
                : holat.modelliMahsulot === holat.mahsulotlar
                  ? `${holat.mahsulotlar} ta mahsulotning hammasida 3D model bor`
                  : `${holat.mahsulotlar} ta mahsulotdan ${holat.modelliMahsulot} tasida 3D model bor`
            : holat.modellar > 0
              ? `${holat.modellar} ta model`
              : "Buyurtmada hali mahsulot yo'q — avval .project yuklanadi"}
          {holat.bogLanmagan > 0 && (
            <span className="font-medium text-amber-700">
              {` · ${holat.bogLanmagan} ta model bog'lanmagan`}
            </span>
          )}
        </p>
        {canUpload && (
          <>
            <LoadingButton
              variant="outline"
              loading={busy}
              disabled={!yuklash}
              title={yuklash ? undefined : "Avval .project faylini yuklang"}
              onClick={() => fileInput.current?.click()}
            >
              <FileUp /> Bazis fayl yuklash
            </LoadingButton>
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
          </>
        )}
      </div>

      {/* Model hali yo'q — katta tashlash maydoni asosiy harakat. Model bor
          bo'lsa u keraksiz joy egallardi: ro'yxatning o'zi tashlash maydoni */}
      {yuklash && holat.modellar === 0 && (
        // biome-ignore lint/a11y/noStaticElementInteractions: tashlash maydoni — klaviatura yo'li tepadagi «Bazis fayl yuklash» tugmasi
        // biome-ignore lint/a11y/useKeyWithClickEvents: klaviatura yo'li tepadagi «Bazis fayl yuklash» tugmasi
        <div
          {...drop}
          onClick={() => fileInput.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed p-6 text-center transition-colors",
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/30 text-muted-foreground hover:border-primary/50",
            busy && "opacity-60",
          )}
        >
          <FileUp className={cn("size-6", dragOver && "animate-bounce")} />
          <span className="font-medium">
            {busy
              ? "Yuklanmoqda..."
              : dragOver
                ? "Qo'yib yuboring"
                : "Bazis fayllarini (.b3d) shu yerga tashlang yoki bosing"}
          </span>
          <span className="text-xs">
            Har mahsulotga bitta fayl — kodi va nomi buyurtmadagi mahsulot bilan
            bir xil bo'lishi shart
          </span>
        </div>
      )}

      {holat.qatorlar.length > 0 ? (
        <ul
          {...(holat.modellar > 0 ? drop : {})}
          className={cn(
            cardSurface,
            "divide-y transition-colors",
            dragOver &&
              holat.modellar > 0 &&
              "border-primary bg-primary/5 ring-2 ring-primary/30",
          )}
        >
          {holat.qatorlar.map((q) => (
            <ModelQatori
              key={q.key}
              orderId={orderId}
              qator={q}
              canUpload={canUpload}
              onPreview={setKorish}
              onDelete={setOchiriladi}
            />
          ))}
        </ul>
      ) : (
        !canUpload && (
          <div className="rounded-xl border border-border border-dashed p-8 text-center text-muted-foreground text-sm">
            Hali model yuklanmagan.
          </div>
        )
      )}

      <ShareBlock
        orderId={orderId}
        token={state.data.share_token ?? null}
        canShare={canShare}
        hasModels={holat.modellar > 0}
      />

      <BazisPreviewDialog
        orderId={orderId}
        model={korish}
        shareToken={state.data.share_token ?? null}
        onClose={() => setKorish(null)}
      />

      <ConfirmDialog
        open={ochiriladi !== null}
        onOpenChange={(ochiq) => !ochiq && setOchiriladi(null)}
        title="Modelni o'chirish"
        description={`${ochiriladi?.product_code ?? ""} modeli fayllari bilan o'chiriladi — uni qayta yuklash kerak bo'ladi. Havola ochiq qolsa, qolgan modellar ko'rinaveradi.`}
        confirmText="O'chirish"
        destructive
        loading={remove.isPending}
        onConfirm={() => ochiriladi && remove.mutate(ochiriladi.file_id)}
      />
    </div>
  )
}
