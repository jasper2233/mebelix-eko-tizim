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
  /** Sxemasida bu maydon yo'q post (KROMKA) bermaydi — o'shanda satr chizilmaydi */
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
      <div className="min-w-0">
        <div className="truncate text-lg font-black">{orderNumber}</div>
        {projectName && (
          <div className="truncate text-xs text-muted-foreground">
            {projectName}
          </div>
        )}
      </div>
      {children}
    </div>
  )
}
