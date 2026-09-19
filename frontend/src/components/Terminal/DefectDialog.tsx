// BRAK: skanerlangan nusxa yaroqsiz chiqqanda operator sababni tanlaydi (OEE Quality).
// Doimiy tugma YO'Q — tugma skan tasmasida, oxirgi skan turganda ko'rinadi; oyna esa
// faqat o'sha tugma bosilganda ochiladi (docs/12-oee.md §7: 1366×768 ekranga
// doimiy tugmalar sig'magani uchun oldingi modul qaytarilgan).
//
// Brak SKANNI bekor qilmaydi va marshrutni qayta ochmaydi — hozir u faqat o'lchanadi.

import { useMutation, useQuery } from "@tanstack/react-query"
import { TriangleAlert } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { type SessionRead, TerminalService } from "@/client"
import { Serial } from "@/components/Terminal/Serial"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

/** Sabablar ro'yxati — Tizim sozlamalaridan. Bo'sh bo'lsa BRAK tugmasi umuman chizilmaydi
 *  (to'xtash sabablaridagi bilan bir xil qoida: kiritilmagan ro'yxat ishni to'smaydi). */
export function useDefectReasons(): string[] {
  return (
    useQuery({
      queryKey: ["terminal", "defect-reasons"],
      queryFn: async () =>
        (await TerminalService.readTerminalDefectReasons()).data,
      staleTime: 5 * 60_000,
    }).data ?? []
  )
}

export function DefectDialog({
  scan,
  crew,
  reasons,
  onClose,
}: {
  /** Belgilanayotgan skan — dialog OCHILGANDA suratga olinadi (`undoFor` bilan bir naqsh):
   *  keyingi skan kelib tasmani almashtirsa ham oyna boshqa detalga o'tib ketmasin. */
  scan: { scanId: number; code: string } | null
  crew: SessionRead[]
  reasons: string[]
  onClose: () => void
}) {
  const [reason, setReason] = useState<string | null>(null)
  const [note, setNote] = useState("")
  useEffect(() => {
    if (!scan) return
    setReason(null)
    setNote("")
  }, [scan])

  const save = useMutation({
    mutationFn: () =>
      TerminalService.markDefect({
        body: {
          scan_id: scan?.scanId ?? 0,
          reason: reason ?? "",
          note: note.trim(),
        },
      }),
    onSuccess: () => {
      toast.warning(`Brak qayd etildi: ${reason}`)
      onClose()
    },
    onError: handleError,
  })

  return (
    <Dialog open={!!scan} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="gap-5 sm:max-w-3xl">
        <DialogHeader className="flex-row items-center gap-4 space-y-0">
          <div className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-red-600 text-white">
            <TriangleAlert className="size-8" />
          </div>
          <div className="min-w-0 flex-1 text-left">
            <DialogTitle className="text-2xl font-black">
              Brak — nima bo'ldi?
            </DialogTitle>
            <DialogDescription className="text-base">
              {scan && <Serial code={scan.code} className="font-bold" />} —
              detal yaroqsiz deb belgilanadi. Skan bekor qilinmaydi: detal qayta
              chiqarilishi kerak bo'lsa texnologga ayting.
            </DialogDescription>
          </div>
          <div className="shrink-0 pr-8 text-right text-sm text-muted-foreground">
            Kiritadi
            <div className="text-base font-bold text-foreground">
              {crew.map((s) => s.employee_name).join(", ")}
            </div>
          </div>
        </DialogHeader>

        <div className="grid grid-cols-3 gap-2">
          {reasons.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setReason(r)}
              className={cn(
                "flex min-h-14 items-center justify-center rounded-xl border-2 px-3 py-2 text-center text-base font-bold leading-tight transition-colors",
                reason === r
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card hover:border-primary/50",
              )}
            >
              {r}
            </button>
          ))}
        </div>
        {/* Izoh ixtiyoriy: tsexda klaviatura yo'q, ekran klaviaturasi esa sekin —
            majburiy qilinsa operator eng oson sababni bosib ketardi. */}
        <Textarea
          value={note}
          maxLength={500}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Izoh (ixtiyoriy)"
          className="min-h-14 text-base"
        />

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="h-12 px-5 text-base"
            onClick={onClose}
          >
            Bekor qilish
          </Button>
          <LoadingButton
            variant="destructive"
            className="ml-auto h-12 min-w-44 text-base font-black"
            loading={save.isPending}
            disabled={!reason || crew.length === 0}
            onClick={() => save.mutate()}
          >
            Brak deb belgilash
          </LoadingButton>
        </div>
      </DialogContent>
    </Dialog>
  )
}
