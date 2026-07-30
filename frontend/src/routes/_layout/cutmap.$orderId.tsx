// Kesish xaritalari — admin panel ko'rinishi (TZ 10.3): manager/texnolog ko'radi,
// brauzer print orqali PDF/qog'oz nusxa chop etadi (arrachiga yoki mijozga).

import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowLeft, Printer } from "lucide-react"
import { useRef } from "react"

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

  return (
    <div className="flex h-[calc(100dvh-6rem)] flex-col">
      <div className="print-hide mb-3 flex items-center gap-2">
        <Link
          to="/orders/$orderId"
          params={{ orderId }}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Buyurtma
        </Link>
        <Button
          variant="outline"
          size="sm"
          className="ml-auto"
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
