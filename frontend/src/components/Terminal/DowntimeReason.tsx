// To'xtash sababi — smenadagi hodim terminalda kiritadi (docs/12-oee.md §7).
// Doimiy tugma YO'Q (2026-08-21 dagi modul 1366×768 ekranga sig'magani uchun qaytarilgan):
// - Pico to'xtashi (qizil chiroq, hammasi o'chiq, sariq chiroq chegaradan uzoq) — oyna O'ZI chiqadi;
// - qulf tugmasi — avval sabab, "Saqlash va qulflash" dan keyin ekran qulflanadi.
// Faqat Pico ulangan ish markazida (`TerminalContext.has_andon`).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, Clock, Lock, PauseCircle, PowerOff } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import {
  type DowntimeReasonRead,
  type SessionRead,
  TerminalService,
} from "@/client"
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
import { DOWNTIME_KIND_LABELS } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

/** "Keyinroq" — oyna shuncha vaqt chiqmaydi */
const SNOOZE_MS = 10 * 60_000
export const PENDING_KEY = ["terminal", "downtimes", "pending"]

const KIND_VIEW = {
  fault: { icon: AlertTriangle, cls: "bg-red-600" },
  off: { icon: PowerOff, cls: "bg-zinc-600" },
  idle: { icon: PauseCircle, cls: "bg-amber-500" },
  lock: { icon: Lock, cls: "bg-amber-500" },
} as const

const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString("uz-UZ", {
    hour: "2-digit",
    minute: "2-digit",
  })
const minutes = (ms: number) => {
  const m = Math.max(0, Math.round(ms / 60_000))
  return m < 60 ? `${m} daq` : `${Math.floor(m / 60)} soat ${m % 60} daq`
}
const who = (crew: SessionRead[]) => crew.map((s) => s.employee_name).join(", ")

function useNow(ms: number) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(t)
  }, [ms])
  return now
}

function useReasons() {
  return (
    useQuery({
      queryKey: ["terminal", "downtime-reasons"],
      queryFn: async () =>
        (await TerminalService.readTerminalDowntimeReasons()).data,
      staleTime: 5 * 60_000,
    }).data ?? []
  )
}

/** Sabab tanlash maydoni — Pico oynasi va qulf oynasi uchun BITTA */
function ReasonGrid({
  reasons,
  reasonId,
  onPick,
  note,
  onNote,
  plannedFirst = false,
}: {
  reasons: DowntimeReasonRead[]
  reasonId: number | null
  onPick: (id: number) => void
  note: string
  onNote: (v: string) => void
  /** Qulflashda odatda rejali sabab (tushlik, sozlash) — tepada tursin */
  plannedFirst?: boolean
}) {
  const reason = reasons.find((r) => r.id === reasonId)
  return (
    <>
      {(plannedFirst ? [true, false] : [false, true]).map((planned) => {
        const group = reasons.filter((r) => r.is_planned === planned)
        if (!group.length) return null
        return (
          <section key={String(planned)} className="space-y-2">
            <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              {planned ? "Rejali" : "Rejasiz"}
            </div>
            <div className="grid grid-cols-4 gap-2">
              {group.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => onPick(r.id)}
                  className={cn(
                    "flex min-h-14 items-center justify-center rounded-xl border-2 px-3 py-2 text-center text-base font-bold leading-tight transition-colors",
                    reasonId === r.id
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card hover:border-primary/50",
                  )}
                >
                  {r.name}
                </button>
              ))}
            </div>
          </section>
        )
      })}
      {reason?.needs_note && (
        <Textarea
          autoFocus
          value={note}
          maxLength={500}
          onChange={(e) => onNote(e.target.value)}
          placeholder="Qisqacha yozing: nima bo'ldi?"
          className="min-h-16 text-base"
        />
      )}
    </>
  )
}

const ready = (
  reasons: DowntimeReasonRead[],
  id: number | null,
  note: string,
) => {
  const r = reasons.find((x) => x.id === id)
  return !!r && (!r.needs_note || !!note.trim())
}

function Who({ crew, extra }: { crew: SessionRead[]; extra?: string }) {
  return (
    <div className="shrink-0 pr-8 text-right text-sm text-muted-foreground">
      Kiritadi
      <div className="text-base font-bold text-foreground">{who(crew)}</div>
      {extra && (
        <div className="mt-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">
          {extra}
        </div>
      )}
    </div>
  )
}

/** Stanok o'zi to'xtaganda. Server to'xtashni Pico hodisalaridan yozadi (`services/downtimes.py`);
 *  terminal WS `andon.state` da ro'yxatni darhol qayta so'raydi. Chiqmaydi: smena ochilmagan,
 *  ekran qulflangan (sabab qulflashda aytilgan) yoki sabablar ro'yxati hali kiritilmagan. */
export function StopReasonPrompt({
  crew,
  suppressed,
  onVisibleChange,
}: {
  crew: SessionRead[]
  suppressed: boolean
  onVisibleChange: (visible: boolean) => void
}) {
  const queryClient = useQueryClient()
  const { data: pending = [] } = useQuery({
    queryKey: PENDING_KEY,
    queryFn: async () => (await TerminalService.readPendingDowntimes()).data,
    // Sariq chiroq chegarani o'tishi uchun yangi Pico hodisasi kelmaydi — davriy so'rov kerak
    refetchInterval: 30_000,
    enabled: crew.length > 0,
  })
  const reasons = useReasons()
  const now = useNow(1_000)
  const [snoozedUntil, setSnoozedUntil] = useState(0)
  const [reasonId, setReasonId] = useState<number | null>(null)
  const [note, setNote] = useState("")

  const current = pending[0]
  const visible =
    !!current &&
    crew.length > 0 &&
    reasons.length > 0 &&
    !suppressed &&
    now >= snoozedUntil
  useEffect(() => onVisibleChange(visible), [visible, onVisibleChange])

  const save = useMutation({
    mutationFn: () =>
      TerminalService.setDowntimeReason({
        path: { downtime_id: current?.id ?? 0 },
        body: { reason_id: reasonId ?? 0, note: note.trim() },
      }),
    onSuccess: () => {
      toast.success(
        `Sabab saqlandi: ${reasons.find((r) => r.id === reasonId)?.name}`,
      )
      setReasonId(null)
      setNote("")
      queryClient.invalidateQueries({ queryKey: PENDING_KEY })
    },
    onError: handleError,
  })

  if (!current) return null
  const view = KIND_VIEW[current.kind]
  const Icon = view.icon
  const end = current.ended_at ? Date.parse(current.ended_at) : now
  const snooze = () => setSnoozedUntil(Date.now() + SNOOZE_MS)

  return (
    <Dialog open={visible} onOpenChange={(v) => !v && snooze()}>
      <DialogContent className="gap-5 sm:max-w-4xl">
        <DialogHeader className="flex-row items-center gap-4 space-y-0">
          <div
            className={cn(
              "flex size-14 shrink-0 items-center justify-center rounded-xl text-white",
              view.cls,
            )}
          >
            <Icon className="size-8" />
          </div>
          <div className="min-w-0 flex-1 text-left">
            <DialogTitle className="text-2xl font-black">
              {current.kind === "fault"
                ? "Avariya — nima bo'ldi?"
                : "Stanok ishlamayapti — nima sababdan?"}
            </DialogTitle>
            <DialogDescription className="flex flex-wrap items-center gap-x-3 text-base">
              <span className="font-bold text-foreground">
                {DOWNTIME_KIND_LABELS[current.kind]}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="size-4" />
                {clock(current.started_at)}
                {current.ended_at ? `–${clock(current.ended_at)}` : " dan beri"}
              </span>
              <span className="num font-bold text-foreground">
                {minutes(end - Date.parse(current.started_at))}
              </span>
              {!current.ended_at && (
                <span className="animate-pulse font-bold text-red-600">
                  davom etmoqda
                </span>
              )}
            </DialogDescription>
          </div>
          <Who
            crew={crew}
            extra={
              pending.length > 1
                ? `yana ${pending.length - 1} ta to'xtash sababsiz`
                : undefined
            }
          />
        </DialogHeader>

        <ReasonGrid
          reasons={reasons}
          reasonId={reasonId}
          onPick={setReasonId}
          note={note}
          onNote={setNote}
        />

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="h-12 px-5 text-base"
            onClick={snooze}
          >
            Keyinroq (10 daq)
          </Button>
          <LoadingButton
            className="ml-auto h-12 min-w-44 text-base font-black"
            loading={save.isPending}
            disabled={!ready(reasons, reasonId, note)}
            onClick={() => save.mutate()}
          >
            Saqlash
          </LoadingButton>
        </div>
      </DialogContent>
    </Dialog>
  )
}

/** Qulf tugmasi: sabab so'raladi, "Saqlash va qulflash" dan keyin qulflanadi. To'xtash beyjik bilan
 *  qulf ochilguncha davom etadi (backend `open_badge_session` yopadi). Sabablar ro'yxati hali
 *  kiritilmagan bo'lsa — sababsiz qulflanadi: ro'yxat yo'qligi ishni to'sib qo'ymasin. */
export function LockReasonDialog({
  open,
  crew,
  onCancel,
  onLocked,
}: {
  open: boolean
  crew: SessionRead[]
  onCancel: () => void
  onLocked: (reasonName: string | null) => void
}) {
  const reasons = useReasons()
  const [reasonId, setReasonId] = useState<number | null>(null)
  const [note, setNote] = useState("")
  useEffect(() => {
    if (!open) return
    setReasonId(null)
    setNote("")
  }, [open])

  const save = useMutation({
    mutationFn: () =>
      TerminalService.lockWithDowntimeReason({
        body: { reason_id: reasonId ?? 0, note: note.trim() },
      }),
    onSuccess: () =>
      onLocked(reasons.find((r) => r.id === reasonId)?.name ?? null),
    onError: handleError,
  })
  const noReasons = reasons.length === 0

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent className="gap-5 sm:max-w-4xl">
        <DialogHeader className="flex-row items-center gap-4 space-y-0">
          <div className="flex size-14 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white">
            <Lock className="size-8" />
          </div>
          <div className="min-w-0 flex-1 text-left">
            <DialogTitle className="text-2xl font-black">
              Stanokni to'xtatyapsiz — nima sababdan?
            </DialogTitle>
            <DialogDescription className="text-base">
              {noReasons
                ? "Sabablar ro'yxati hali kiritilmagan — adminga ayting."
                : "Saqlangach ekran qulflanadi. Qaytganda beyjikni skanerlang."}
            </DialogDescription>
          </div>
          <Who crew={crew} />
        </DialogHeader>

        <ReasonGrid
          reasons={reasons}
          reasonId={reasonId}
          onPick={setReasonId}
          note={note}
          onNote={setNote}
          plannedFirst
        />

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="h-12 px-5 text-base"
            onClick={onCancel}
          >
            Bekor qilish
          </Button>
          {noReasons ? (
            <Button
              className="ml-auto h-12 min-w-56 text-base font-black"
              onClick={() => onLocked(null)}
            >
              <Lock /> Sababsiz qulflash
            </Button>
          ) : (
            <LoadingButton
              className="ml-auto h-12 min-w-56 text-base font-black"
              loading={save.isPending}
              disabled={crew.length === 0 || !ready(reasons, reasonId, note)}
              onClick={() => save.mutate()}
            >
              <Lock /> Saqlash va qulflash
            </LoadingButton>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
