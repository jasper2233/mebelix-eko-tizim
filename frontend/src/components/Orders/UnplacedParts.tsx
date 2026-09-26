// Kesish xaritasida joyi yo'q detallar — `.project` yuklagan texnologga ogohlantirish
// oynasi va buyurtma sahifasidagi doimiy banner.
//
// Arra terminali chekni FAQAT xaritadagi katakdan chiqaradi: GibLab listga
// joylamagan detalni arrachi ko'rmaydi. Ilgari bu haqdagi ogohlantirish 4
// soniyalik yashil toastda (va birinchi 3 tasigacha kesilib) chiqardi — 2026-09-26
// da B-2026-088 ning uchta stoleshnitsasi shu yo'l bilan arrada qotib qolgan.

import { MapPinOff, TriangleAlert } from "lucide-react"

import type { ProjectUploadResult } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

// Bu ikki ogohlantirish oynada ro'yxat bo'lib alohida chiqadi — matn sifatida takrorlanmasin
const TAKROR = ["Kesish xaritasida", "Marshrutida Arra bor"]

function PartList({ items }: { items: string[] }) {
  return (
    <ul className="mt-2 max-h-48 list-disc overflow-y-auto pl-5 font-mono text-xs">
      {items.map((p) => (
        <li key={p}>{p}</li>
      ))}
    </ul>
  )
}

/** Yuklashdan keyin — faqat xaritada joyi yo'q detal bo'lsa ochiladi, o'zi yopilmaydi. */
export function UploadWarningsDialog({
  result,
  onClose,
}: {
  result: ProjectUploadResult | null
  onClose: () => void
}) {
  const unplaced = result?.unplaced_parts ?? []
  const arra = result?.unplaced_arra_parts ?? []
  const other = (result?.warnings ?? []).filter(
    (w) => !TAKROR.some((t) => w.startsWith(t)),
  )
  // Serverdagi `message` kesilgan ogohlantirishlarni ham o'z ichiga oladi —
  // oynada faqat xulosa qismi, ro'yxatlar pastda to'liq
  const xulosa = (result?.message ?? "").split(" Diqqat (")[0]
  return (
    <Dialog open={!!result} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TriangleAlert className="size-5 shrink-0 text-amber-600" />
            Fayl qabul qilindi — diqqat qiling
          </DialogTitle>
          <DialogDescription>{xulosa}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          {arra.length > 0 && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
              <div className="font-medium text-destructive">
                Marshrutida Arra bor, lekin kesish xaritasida joyi yo'q (
                {arra.length} ta)
              </div>
              <div className="text-muted-foreground">
                Arrachi ularni ko'rmaydi va cheki chiqmaydi — buyurtmani ishlab
                chiqarishga uzatib bo'lmaydi.
              </div>
              <PartList items={arra} />
            </div>
          )}
          {unplaced.length > 0 && (
            <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
              <div className="font-medium">
                Kesish xaritasida joyi yo'q detallar ({unplaced.length} ta)
              </div>
              <div className="text-muted-foreground">
                GibLab ularni listga joylashtirmagan — arrachi ekranida
                ko'rinmaydi. Arrada kesilishi kerak bo'lsa (masalan
                stoleshnitsa), GibLab'da listga joylab faylni qayta yuklang.
                Listdan kesilmaydigan detal (masalan profil) bo'lsa — hammasi
                joyida.
              </div>
              <PartList items={unplaced} />
            </div>
          )}
          {other.length > 0 && (
            <div className="rounded-lg border p-3">
              <div className="font-medium">Boshqa ogohlantirishlar</div>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-muted-foreground">
                {other.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button className="h-11 px-5" onClick={onClose}>
            Tushunarli
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Buyurtma sahifasida — muammo bor ekan turadi (server har ochilishda qayta hisoblaydi). */
export function UnplacedArraBanner({
  parts,
  status,
  canEdit,
}: {
  parts: string[]
  status: string
  canEdit: boolean
}) {
  if (!parts.length || status === "cancelled") return null
  return (
    <div className="mb-6 flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
      <MapPinOff className="mt-0.5 size-4 shrink-0 text-destructive" />
      <div>
        <div className="font-medium">
          Arrachi {parts.length} ta detalni ko'rmaydi — kesish xaritasida joyi
          yo'q
        </div>
        <div className="text-muted-foreground">
          Marshrutida Arra bor, lekin kesish xaritasida katagi yo'q: cheki
          chiqmaydi va buyurtma arrada to'xtab qoladi.
          {status === "technical_review" &&
            " Shu holatda ishlab chiqarishga uzatib bo'lmaydi."}{" "}
          Yechim: GibLab'da listga joylab .project ni qayta yuklang. Detal
          Rover'da kesilsa — nostandart marshrutni Arra o'rniga Rover'dan
          boshlang (cheki rover sahifasidan chiqadi).
          {!canEdit &&
            " Fayl qulflangan (ish boshlangan) — adminga murojaat qiling."}
        </div>
        <PartList items={parts} />
      </div>
    </div>
  )
}
