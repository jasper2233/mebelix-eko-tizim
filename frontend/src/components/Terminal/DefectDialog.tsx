// Brak belgilash — operator yaroqsiz detalni shu yerdan yuboradi.
//
// Detal ishlab chiqarishga QAYTMAYDI: yozuv menejerga ketadi. Aks holda har
// xato skan yangi nusxa yaratib, buyurtma miqdorini shishirardi.

import { useMutation } from "@tanstack/react-query"
import { useRef, useState } from "react"
import { toast } from "sonner"

import { DefectsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { detailMessage } from "@/utils"

/** Tez sabablar — qo'lqop bilan yozish qiyin, ro'yxatdan bosish bir harakat. */
const QUICK_REASONS = [
  "O'lcham noto'g'ri",
  "Kromka ko'chgan",
  "Teshik noto'g'ri joyda",
  "Yuza shikastlangan",
  "Material nuqsoni",
  "Rang mos emas",
]

export function DefectDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [qr, setQr] = useState("")
  const [reason, setReason] = useState("")
  const qrRef = useRef<HTMLInputElement>(null)

  const send = useMutation({
    mutationFn: () =>
      DefectsService.reportDefect({
        body: { qr_text: qr.trim(), reason: reason.trim() },
      }),
    onSuccess: (r) => {
      toast.success(r.data.message)
      setQr("")
      setReason("")
      onClose()
    },
    onError: (e) => toast.error(detailMessage(e)),
  })

  const valid = qr.trim().length > 0 && reason.trim().length > 2

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose()
      }}
    >
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Brak yuborish</DialogTitle>
          <DialogDescription>
            Detal ishlab chiqarishga darhol qaytmaydi — menejer ko'rib chiqadi
            va qaysi postdan qayta boshlashni belgilaydi
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <span className="text-sm font-medium">Detal QR</span>
            {/* Skaner shu maydonga yozadi — dialog ochilishi bilan fokus shu yerda */}
            <Input
              ref={qrRef}
              value={qr}
              onChange={(e) => setQr(e.target.value)}
              placeholder="QR scan qiling yoki kodni yozing"
              className="h-12 font-mono text-base"
              autoFocus
            />
          </div>

          <div className="grid gap-1.5">
            <span className="text-sm font-medium">Sabab</span>
            <div className="flex flex-wrap gap-2">
              {QUICK_REASONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setReason(r)}
                  className={`rounded-lg border-2 px-3 py-2 text-sm font-semibold transition-colors active:scale-95 ${
                    reason === r
                      ? "border-primary bg-primary/10"
                      : "hover:border-primary/40"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
            <Input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="yoki o'zingiz yozing"
              maxLength={200}
              className="h-11"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Bekor qilish
          </Button>
          <LoadingButton
            variant="destructive"
            disabled={!valid}
            loading={send.isPending}
            onClick={() => send.mutate()}
          >
            Brakni yuborish
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
