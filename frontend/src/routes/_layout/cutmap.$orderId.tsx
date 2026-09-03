// Kesish xaritalari — admin panel ko'rinishi: manager/texnolog ko'radi,
// brauzer print orqali PDF/qog'oz nusxa chop etadi (arrachiga yoki mijozga).

import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowLeft, Printer } from "lucide-react"
import { useRef, useState } from "react"

import { CutmapView } from "@/components/Terminal/CutmapView"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_layout/cutmap/$orderId")({
  component: AdminCutmapPage,
  head: () => ({ meta: [{ title: "Kesish xaritasi | MebeliX" }] }),
  // ?part=305201_01_014 — matritsadan "xaritada ko'rsat" sakrashi
  validateSearch: (s: Record<string, unknown>): { part?: string } =>
    typeof s.part === "string" && s.part ? { part: s.part } : {},
})

function AdminCutmapPage() {
  const { orderId } = Route.useParams()
  const { part } = Route.useSearch()
  const navigate = useNavigate()
  const printRef = useRef<(() => void) | null>(null)
  // Bitta sarlavha qatori (breadcrumb): "← Buyurtma" shu yerda, davomi —
  // buyurtma raqami › Listlar › №list + list tugmalari — CutmapView'dan
  // `statsContainer` portali orqali shu slotga tushadi.
  const [crumbEl, setCrumbEl] = useState<HTMLDivElement | null>(null)

  return (
    <div className="flex h-[calc(100dvh-6rem)] flex-col md:h-[calc(100dvh-4rem)]">
      <div className="print-hide mb-3 flex min-h-8 flex-wrap items-center gap-x-1.5 gap-y-1 text-sm">
        <Link
          to="/orders/$orderId"
          params={{ orderId }}
          className="inline-flex shrink-0 items-center gap-1 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Buyurtma
        </Link>
        <div
          ref={setCrumbEl}
          className="flex min-w-0 flex-1 items-center gap-2"
        />
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={() => printRef.current?.()}
        >
          <Printer /> PDF / Chop etish
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        <CutmapView
          orderId={Number(orderId)}
          admin
          focusPartKey={part}
          statsContainer={crumbEl}
          onBack={() =>
            navigate({ to: "/orders/$orderId", params: { orderId } })
          }
          registerPrint={(fn) => {
            printRef.current = fn
          }}
        />
      </div>
    </div>
  )
}
