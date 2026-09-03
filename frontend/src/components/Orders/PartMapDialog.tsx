// Detalning kesish xaritasini SHU SAHIFADA ko'rish: matritsa qatori va nostandart
// kartochkasidagi xarita ikonkasi sahifaga olib ketmaydi — katta dialogda haqiqiy
// `CutmapView` ochiladi (detalning listi + katagi belgilangan, zoom/pan ishlaydi),
// Esc/tashqariga bosish yopadi. Tahrir holati (marshrut, bosqichlar) saqlanib
// qoladi — dialog matritsaning qo'shnisi. «Bosib turish» varianti rad etildi:
// sichqonchani ushlab turib zoom qilib bo'lmaydi, jest taxmin qilinmaydi.

import { Link } from "@tanstack/react-router"
import { ExternalLink, Map as MapIcon } from "lucide-react"
import { useState } from "react"

import { CutmapView } from "@/components/Terminal/CutmapView"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

export function PartMapButton({
  orderId,
  partKey,
}: {
  orderId: number
  /** `${product_code}_${code}` — xaritadagi katak kaliti (matritsa `part.key`) */
  partKey: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        className="text-muted-foreground/50 hover:text-primary"
        title="Kesish xaritasida ko'rsatish"
        onClick={(e) => {
          e.stopPropagation()
          setOpen(true)
        }}
      >
        <MapIcon className="size-3.5" />
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="flex h-[88vh] flex-col gap-3 p-4 sm:max-w-[min(1400px,96vw)]">
          <DialogHeader className="flex-row items-center justify-between gap-3 space-y-0 pr-8">
            <DialogTitle className="text-base">
              Kesish xaritasi ·{" "}
              <span className="num font-semibold">{partKey}</span>
            </DialogTitle>
            <Button asChild variant="outline" size="sm">
              <Link
                to="/cutmap/$orderId"
                params={{ orderId: String(orderId) }}
                search={{ part: partKey }}
              >
                <ExternalLink /> To'liq sahifada
              </Link>
            </Button>
          </DialogHeader>
          <div className="min-h-0 flex-1">
            {/* Faqat ochiqda: yopiqda xarita so'rovi/render'i ketmasin */}
            {open && (
              <CutmapView
                orderId={orderId}
                admin
                focusPartKey={partKey}
                onBack={() => setOpen(false)}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
