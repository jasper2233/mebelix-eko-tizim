/** Buyurtma sahifasidagi «3D model» tabi (menejer va direktorda — matritsa ostidagi blok).
 *
 * Uch QADAMLI oqim (2-qadam project fayl yuklangach ochiladi, 3-si birinchi modeldan keyin chiqadi):
 * 1) Project fayl — mahsulotlar undan keladi; yuklanmagan bo'lsa shu yerda aytiladi.
 * 2) Bazis fayllar — HAR MAHSULOTGA bitta, yuklash o'sha mahsulot QATORIDA: fayl aynan
 *    shu mahsulotga tekshiriladi va xato qator ostida qoladi (toast kabi yo'qolmaydi).
 * 3) Yig'uvchi uchun havola — kamida bitta model bo'lgandagina chiqadi.
 *
 * Nomlash: tab — natija («3D model», ochiq sahifa ham shunday ataladi), qadamlar —
 * manba fayllar («Project fayl», «Bazis fayllar»; sahifadagi «Project fayl yuklash»
 * bilan bir so'z).
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
  type OrderFileRead,
  OrdersService,
} from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { QueryError } from "@/components/Common/QueryError"
import { BazisPreviewDialog } from "@/components/Orders/BazisPreview"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { API_BASE, extractErrorMessage, handleError } from "@/utils"

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

/** Oqimning bitta qadami: raqam (bajarilganda — belgi), sarlavha, o'ngda holat.
 * Kutilayotgan qadam xira — undan oldingisini bajarish kerakligi ko'rinib tursin. */
function Qadam({
  n,
  title,
  bajarildi,
  kutilmoqda = false,
  holat,
  children,
}: {
  n: number
  title: string
  bajarildi: boolean
  kutilmoqda?: boolean
  holat?: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <section className={cn(cardSurface, "p-4", kutilmoqda && "bg-muted/40")}>
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "num flex size-7 shrink-0 items-center justify-center rounded-full font-semibold text-sm",
            bajarildi
              ? "bg-primary text-primary-foreground"
              : kutilmoqda
                ? "border border-border text-muted-foreground"
                : "border-2 border-primary text-primary",
          )}
          aria-hidden
        >
          {bajarildi ? <Check className="size-4" /> : n}
        </span>
        <h3
          className={cn(
            "min-w-0 flex-1 font-medium",
            kutilmoqda && "text-muted-foreground",
          )}
        >
          {title}
        </h3>
        {holat}
      </div>
      {children && <div className="mt-3 sm:pl-10">{children}</div>}
    </section>
  )
}

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

  if (!token) {
    return (
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
        <p className="flex-1 text-muted-foreground text-sm">
          Havolani ochsangiz, uni olgan usta modelni ko'ra oladi — tizimga
          kirmasdan. Boshqa buyurtmalar ochilmaydi.
        </p>
        <LoadingButton
          onClick={() => open.mutate()}
          loading={open.isPending}
          disabled={open.isPending}
        >
          <Link2 /> Havolani ochish
        </LoadingButton>
      </div>
    )
  }

  const url = shareUrl(token)
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      {/* QR — ustaning telefoni bilan bir skanda ochiladi, havolani terib
          o'tirmaydi. Ekrandan ham, chop etilgan varaqdan ham ishlaydi. */}
      <div className="mx-auto shrink-0 rounded-xl border border-border bg-white p-2 sm:mx-0">
        <QRCodeSVG value={url} size={116} />
      </div>
      <div className="min-w-0 flex-1">
        <code className="block truncate rounded-lg bg-muted px-2 py-1.5 font-mono text-xs">
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
    </div>
  )
}

/** Qator ostidagi izoh — amber (ogohlantirish) yoki qizil (yuklanmadi) */
function Izoh({
  xato = false,
  children,
}: {
  xato?: boolean
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        "mt-1 flex items-start gap-1.5 text-xs",
        xato ? "text-destructive" : "text-amber-700",
      )}
    >
      <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </div>
  )
}

function ModelQatori({
  orderId,
  qator,
  canUpload,
  yuklanmoqda,
  xato,
  onUpload,
  onPreview,
  onDelete,
}: {
  orderId: number
  qator: Qator
  canUpload: boolean
  /** Shu qatorga fayl ketmoqda */
  yuklanmoqda: boolean
  /** Oxirgi urinish rad etilgan bo'lsa — server xabari */
  xato: string | undefined
  onUpload: (product: BazisProductRead, file?: File) => void
  onPreview: (m: BazisModelRead) => void
  onDelete: (m: BazisModelRead) => void
}) {
  const { product, model } = qator
  const bogLanmagan = model !== undefined && !model.matched
  const [ustida, setUstida] = useState(false)
  // Faylni o'sha QATORGA tashlasa ham bo'ladi — qaysi mahsulotniki ekani aniq
  const tashlash =
    canUpload && product
      ? {
          onDragOver: (e: React.DragEvent) => {
            e.preventDefault()
            setUstida(true)
          },
          onDragLeave: () => setUstida(false),
          onDrop: (e: React.DragEvent) => {
            e.preventDefault()
            setUstida(false)
            const f = e.dataTransfer.files?.[0]
            if (f) onUpload(product, f)
          },
        }
      : {}
  return (
    <li
      {...tashlash}
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-3 transition-colors sm:flex-nowrap",
        ustida && "bg-primary/5 ring-2 ring-primary/30 ring-inset",
      )}
    >
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
          <Izoh>
            Bu Bazis fayli project faylga tegishli emas — ustalar chekdagi Detal
            ID bilan detal joyini topa olmaydi. O'chiring.
          </Izoh>
        )}
        {model?.warnings.map((w) => (
          <Izoh key={w}>{w}</Izoh>
        ))}
        {xato && <Izoh xato>Yuklanmadi: {xato}</Izoh>}
      </div>
      {/* Telefonda holat va amallar ikkinchi qatorga, matn ostiga tushadi */}
      <div className="flex w-full shrink-0 flex-wrap items-center gap-2 pl-[4.25rem] sm:w-auto sm:flex-nowrap sm:pl-0">
        {!model ? (
          canUpload && product ? (
            <LoadingButton
              variant="outline"
              size="sm"
              loading={yuklanmoqda}
              onClick={() => onUpload(product)}
            >
              <FileUp /> Bazis fayl yuklash
            </LoadingButton>
          ) : (
            <Badge variant="outline" className="text-muted-foreground">
              Model yo'q
            </Badge>
          )
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
        {model && canUpload && product && (
          <LoadingButton
            variant="ghost"
            size="sm"
            loading={yuklanmoqda}
            onClick={() => onUpload(product)}
            title="Bazisdan qayta eksport qilingan faylni yuklash"
          >
            Almashtirish
          </LoadingButton>
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
  projectFile,
  onUploadProject,
}: {
  orderId: number
  /** Faqat texnolog — `.project` bilan bir xil qoida */
  canUpload: boolean
  /** Menejer ham: havolani mijozga ko'pincha u uzatadi */
  canShare: boolean
  /** 1-qadam holati uchun: yuklangan `.project` (nomi, sanasi) */
  projectFile: OrderFileRead | undefined
  /** Project faylni SHU yerdan yuklash (faqat tahrirlash mumkin bo'lganda) */
  onUploadProject?: () => void
}) {
  const qc = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  /** Tanlash oynasi qaysi mahsulot qatoridan ochilgani */
  const nishon = useRef<BazisProductRead | null>(null)
  const [yuklanayotgan, setYuklanayotgan] = useState<string | null>(null)
  const [xatolar, setXatolar] = useState<Record<string, string>>({})
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

  /** Bitta faylni bitta MAHSULOTGA yuklaydi: server fayldagi kod va nomni aynan shu
   * mahsulot bilan solishtiradi. Rad etilsa xabar qator ostida qoladi — texnolog
   * nima noto'g'ri ekanini o'qib, to'g'ri faylni tanlaydi. Bir vaqtda bitta fayl:
   * har biri serverda 1.7 s gacha CPU oladi. */
  const yukla = async (product: BazisProductRead, file: File) => {
    if (yuklanayotgan !== null) return
    const kalit = product.code
    if (!file.name.toLowerCase().endsWith(".b3d")) {
      setXatolar((x) => ({
        ...x,
        [kalit]: "faqat Bazis .b3d fayli qabul qilinadi.",
      }))
      return
    }
    setYuklanayotgan(kalit)
    setXatolar(({ [kalit]: _, ...qolgan }) => qolgan)
    try {
      const { data } = await OrdersService.uploadOrderBazis({
        path: { order_id: orderId },
        query: { product_code: product.code },
        body: { file },
      })
      toast.success(`«${product.name}» — ${data.panels} detal yuklandi`)
    } catch (err) {
      setXatolar((x) => ({ ...x, [kalit]: extractErrorMessage(err) }))
    } finally {
      setYuklanayotgan(null)
      qc.invalidateQueries({ queryKey: bazisKey(orderId) })
    }
  }
  const tanla = (product: BazisProductRead, file?: File) => {
    if (file) {
      yukla(product, file)
      return
    }
    nishon.current = product
    fileInput.current?.click()
  }

  // Holat kelmaguncha havola bloki CHIZILMAYDI: ilgari yuklanish va xato
  // paytida "havola yo'q" kartochkasi chiqardi, uning «Havolani ochish»
  // tugmasi esa YANGI token berib, ustalardagi ishlab turgan havolani o'ldirardi.
  if (state.isPending) return <Skeleton className="h-48 w-full" />
  if (state.isError) return <QueryError onRetry={() => state.refetch()} />

  const holat = bazisHolati(state.data)
  const token = state.data.share_token ?? null
  const projectBor = holat.mahsulotlar > 0
  // Havola model bo'lgandagina ma'noli; ochiq qolgan bo'lsa (modellar o'chirilgan)
  // uni yopish imkoni qolishi kerak. Direktor ochmaydi — faqat ochiqni ko'radi.
  const havolaQadami =
    (holat.modellar > 0 || token !== null) && (canShare || token !== null)

  return (
    <div className="space-y-3">
      <Qadam
        n={1}
        title="Project fayl"
        bajarildi={projectBor}
        holat={
          projectBor ? (
            <span className="num text-muted-foreground text-sm">
              {holat.mahsulotlar} ta mahsulot
            </span>
          ) : undefined
        }
      >
        {projectBor ? (
          projectFile && (
            <p className="truncate text-muted-foreground text-sm">
              {projectFile.filename} · {formatDateTime(projectFile.created_at)}
            </p>
          )
        ) : (
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
            <p className="flex-1 text-muted-foreground text-sm">
              Bazis fayllar project fayldagi mahsulotlarga bog'lanadi — avval
              uni yuklang.
            </p>
            {onUploadProject && (
              <Button variant="outline" onClick={onUploadProject}>
                <FileUp /> Project fayl yuklash
              </Button>
            )}
          </div>
        )}
      </Qadam>

      <Qadam
        n={2}
        title="Bazis fayllar — har mahsulotga bitta"
        // Bog'lanmagan fayl turgan bo'lsa qadam tugamagan — uni o'chirish kerak
        bajarildi={
          projectBor &&
          holat.modelliMahsulot === holat.mahsulotlar &&
          holat.bogLanmagan === 0
        }
        kutilmoqda={!projectBor}
        holat={
          projectBor ? (
            <span className="num text-muted-foreground text-sm">
              {holat.modelliMahsulot}/{holat.mahsulotlar}
            </span>
          ) : undefined
        }
      >
        {!projectBor && holat.modellar === 0 ? (
          <p className="text-muted-foreground text-sm">
            Project fayl yuklangach ochiladi.
          </p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {holat.qatorlar.map((q) => (
              <ModelQatori
                key={q.key}
                orderId={orderId}
                qator={q}
                canUpload={canUpload}
                yuklanmoqda={
                  q.product !== null && yuklanayotgan === q.product.code
                }
                xato={q.product ? xatolar[q.product.code] : undefined}
                onUpload={tanla}
                onPreview={setKorish}
                onDelete={setOchiriladi}
              />
            ))}
          </ul>
        )}
        {canUpload && (
          <input
            ref={fileInput}
            type="file"
            accept=".b3d"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f && nishon.current) yukla(nishon.current, f)
              e.target.value = ""
            }}
          />
        )}
      </Qadam>

      {havolaQadami && (
        <Qadam n={3} title="Yig'uvchi uchun havola" bajarildi={token !== null}>
          <ShareBlock orderId={orderId} token={token} canShare={canShare} />
        </Qadam>
      )}

      <BazisPreviewDialog
        orderId={orderId}
        model={korish}
        shareToken={token}
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
