// Modelni SHU SAHIFADA ko'rish: texnolog ustaga aynan nima ketishini ochiq havolasiz
// tekshiradi. Ko'ruvchi — ochiq sahifadagi `ModelViewer`ning o'zi (bitta kod, bitta
// ko'rinish). three.js (~650 KB) buyurtma sahifasi chunk'iga TUSHMASIN — dialog
// birinchi ochilganda alohida yuklanadi (docs/13 §7).

import { useQuery } from "@tanstack/react-query"
import { ExternalLink, PackageX, TriangleAlert } from "lucide-react"
import { lazy, Suspense } from "react"
import { type BazisModelRead, OrdersService } from "@/client"
import { type BazisModel, MODEL_VERSIYA } from "@/components/Bazis/model"
import { BrandLoader } from "@/components/Common/BrandLoader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

const ModelViewer = lazy(() =>
  import("@/components/Bazis/ModelViewer").then((m) => ({
    default: m.ModelViewer,
  })),
)

function Markaz({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      {children}
    </div>
  )
}

function Korinish({
  orderId,
  model,
}: {
  orderId: number
  model: BazisModelRead
}) {
  const q = useQuery({
    queryKey: ["order-bazis-model", orderId, model.file_id],
    // Fayl `file_id` ga bog'langan: qayta yuklash YANGI qator beradi, ya'ni
    // bu javob hech qachon eskirmaydi
    staleTime: Number.POSITIVE_INFINITY,
    queryFn: async () =>
      (
        await OrdersService.readOrderBazisModel({
          path: { order_id: orderId, file_id: model.file_id },
        })
      ).data as unknown as BazisModel,
  })
  if (q.isPending)
    return (
      <Markaz>
        <BrandLoader size={72} />
      </Markaz>
    )
  if (q.isError) return <QueryError onRetry={() => q.refetch()} />
  if (q.data.v !== MODEL_VERSIYA)
    return (
      <Markaz>
        <PackageX className="size-8 text-muted-foreground" />
        <p className="max-w-xs text-muted-foreground text-sm">
          Bu model eskirgan — faylni qayta yuklang.
        </p>
      </Markaz>
    )
  return (
    <Suspense
      fallback={
        <Markaz>
          <BrandLoader size={72} />
        </Markaz>
      }
    >
      <ModelViewer model={q.data} bogLanmagan={!model.matched} />
    </Suspense>
  )
}

export function BazisPreviewDialog({
  orderId,
  model,
  shareToken,
  onClose,
}: {
  orderId: number
  /** `null` — dialog yopiq */
  model: BazisModelRead | null
  shareToken: string | null
  onClose: () => void
}) {
  return (
    <Dialog open={model !== null} onOpenChange={(ochiq) => !ochiq && onClose()}>
      <DialogContent
        className="flex h-[88vh] flex-col gap-3 p-4 sm:max-w-[min(1400px,96vw)]"
        // Qidiruvda yozuv bo'lsa Esc avval UNI tozalaydi (ochiq sahifadagi kabi) —
        // Radix Esc'ni oldinroq ushlab, qidiruv o'rniga butun oynani yopardi.
        // Bo'sh qidiruvda ikkinchi Esc oynani yopadi.
        onEscapeKeyDown={(e) => {
          const t = e.target
          if (t instanceof HTMLInputElement && t.value) e.preventDefault()
        }}
      >
        <DialogHeader className="flex-row items-center justify-between gap-3 space-y-0 pr-8">
          <DialogTitle className="min-w-0 truncate text-base">
            {model?.product_name}{" "}
            <span className="num font-normal text-muted-foreground">
              · {model?.product_code}
            </span>
          </DialogTitle>
          <DialogDescription className="sr-only">
            Bazis modelining 3D ko'rinishi — ustalar ochiq havolada aynan shuni
            ko'radi.
          </DialogDescription>
          {/* «Kesish xaritasi» dialogidagi «To'liq sahifada» bilan bir naqsh:
              yig'uvchi havolasi ochadigan sahifa, yangi oynada */}
          {shareToken && model && (
            <Button asChild variant="outline" size="sm" className="shrink-0">
              <a
                href={`/3d/${shareToken}`}
                target="_blank"
                rel="noreferrer"
                title="Yig'uvchi havolasi ochadigan sahifa — yangi oynada"
              >
                <ExternalLink /> To'liq sahifada
              </a>
            </Button>
          )}
        </DialogHeader>
        {model && !model.matched && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" />
            <span>
              Bu model buyurtmadagi mahsulotga bog'lanmagan — chekdagi Detal ID
              bilan qidiruv ishlamaydi.
            </span>
          </div>
        )}
        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border">
          {/* Faqat ochiqda: yopiqda model so'rovi va WebGL sahnasi yaratilmasin */}
          {model && <Korinish orderId={orderId} model={model} />}
        </div>
      </DialogContent>
    </Dialog>
  )
}
