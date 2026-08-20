// Stanok to'xtashi — OEE ning Availability qismi shu yerdan yig'iladi.
//
// Ikki holat, ikki ko'rinish:
//   to'xtash YO'Q  -> chap ustunda "To'xtash" tugmasi, bosilsa sabab so'raladi
//   to'xtash BOR   -> ish maydonini bosib qizil panel turadi, vaqt sanaydi
//
// Panel butun ekranni egallashi ATAYLAB: to'xtash yozib qo'yilib, unutilib
// ketsa stanok soatlab "to'xtagan" bo'lib qolardi va ko'rsatkich yolg'on
// bo'lardi. Ekranni to'sib turgan panelni unutib bo'lmaydi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { OctagonPause, Play } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { type ActiveStop, TerminalService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { detailMessage } from "@/utils"

/** "1 soat 05 daqiqa" — to'xtash qancha davom etayotgani panelda katta turadi. */
function useElapsed(since: string): string {
  const [, tick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [])
  const total = Math.max(0, Math.floor((Date.now() - Date.parse(since)) / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
    : `${m}:${String(s).padStart(2, "0")}`
}

export function StopReasonDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const reasons = useQuery({
    queryKey: ["terminal", "stop-reasons"],
    queryFn: () => TerminalService.readStopReasons().then((r) => r.data),
    // Ro'yxat kamdan-kam o'zgaradi, monoblok esa uni har to'xtashda so'raydi
    staleTime: 30 * 60 * 1000,
    enabled: open,
  })
  const start = useMutation({
    mutationFn: (reasonId: number) =>
      TerminalService.startMachineStop({ body: { reason_id: reasonId } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["terminal", "context"] })
      onClose()
    },
    onError: (e) => toast.error(detailMessage(e)),
  })

  const rows = reasons.data ?? []
  const planned = rows.filter((r) => r.kind === "planned")
  const unplanned = rows.filter((r) => r.kind === "unplanned")

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Nega to'xtadi?</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4">
          {[
            { title: "Rejali", items: planned },
            { title: "Rejasiz", items: unplanned },
          ].map((group) => (
            <div key={group.title}>
              <div className="mb-2 text-2xs font-bold uppercase tracking-wide text-muted-foreground">
                {group.title}
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {group.items.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    disabled={start.isPending}
                    onClick={() => start.mutate(r.id)}
                    className="h-14 rounded-xl border-2 px-2 text-sm font-bold transition-colors hover:border-primary hover:bg-primary/5 active:scale-95 disabled:opacity-40"
                  >
                    {r.name}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function StopBanner({ stop }: { stop: ActiveStop }) {
  const elapsed = useElapsed(stop.started_at)
  const queryClient = useQueryClient()
  const [picking, setPicking] = useState(false)
  const end = useMutation({
    mutationFn: () => TerminalService.endMachineStop(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["terminal", "context"] })
      toast.success("Ish davom etmoqda")
    },
    onError: (e) => toast.error(detailMessage(e)),
  })

  return (
    <div className="absolute inset-0 z-40 flex flex-col items-center justify-center gap-6 bg-red-600 text-white">
      <OctagonPause className="size-16" />
      <div className="text-center">
        <div className="text-4xl font-black">{stop.reason_name}</div>
        <div className="mt-2 font-mono text-6xl font-black tabular-nums">
          {elapsed}
        </div>
      </div>
      <div className="flex gap-3">
        <Button
          size="lg"
          variant="secondary"
          className="h-16 px-8 text-lg font-black"
          disabled={end.isPending}
          onClick={() => end.mutate()}
        >
          <Play className="size-6" /> ISHNI DAVOM ETTIRISH
        </Button>
        {/* Sabab noto'g'ri tanlangani odatiy: "material yo'q" deb boshlanib,
            keyin nosozlik bo'lib chiqadi. Almashtirish eskisini yopadi. */}
        <Button
          size="lg"
          variant="ghost"
          className="h-16 px-6 text-base font-bold text-white hover:bg-white/15 hover:text-white"
          onClick={() => setPicking(true)}
        >
          Sababni almashtirish
        </Button>
      </div>
      <StopReasonDialog open={picking} onClose={() => setPicking(false)} />
    </div>
  )
}
