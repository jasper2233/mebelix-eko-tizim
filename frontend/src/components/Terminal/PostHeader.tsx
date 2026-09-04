// Post ekranlarining umumiy sarlavhasi ("Orqaga" + buyurtma + loyiha): besh ekran uni so'zma-so'z
// ko'chirib yozgan va bir-biridan uzoqlashgan edi. O'ngdagi farqlar — `children`.

import { ArrowLeft } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function PostHeader({
  onBack,
  orderNumber,
  projectName,
  className,
  children,
}: {
  onBack: () => void
  orderNumber?: string
  /** Bo'lmasa (loyiha nomsiz buyurtma) sarlavha raqamning o'zi */
  projectName?: string | null
  className?: string
  children?: ReactNode
}) {
  return (
    <div
      className={cn("flex items-center gap-3 border-b px-4 py-2", className)}
    >
      <Button
        variant="outline"
        className="h-12 px-4 text-base font-bold"
        onClick={onBack}
      >
        <ArrowLeft /> Orqaga
      </Button>
      {/* Loyiha nomi KATTA: chekda ham u sarlavha (labels.py), ishchi
          buyurtmani «Farhod parta» deb biladi. Raqam xira — Detal ID
          prefiksi (B-2026-072_) bilan solishtirish uchun yetadi. */}
      <div className="min-w-0">
        <div className="truncate text-lg font-black">
          {projectName || orderNumber}
        </div>
        {projectName && (
          <div className="num truncate text-xs text-muted-foreground">
            {orderNumber}
          </div>
        )}
      </div>
      {children}
    </div>
  )
}
