// Storno (EKO 2.4): tasdiqlangan ombor hujjati o'chirilmaydi va tahrirlanmaydi — teskari STORNO hujjati
// bilan bekor qilinadi. Faqat direktor: bu moliyaviy tuzatish. Sabab majburiy (jurnalda qoladi).

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Undo2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { StockService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { handleError } from "@/utils"

export function StornoButton({ docId, no }: { docId: number; no: string }) {
  const { currentUser: u } = useCurrentUser()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [sabab, setSabab] = useState("")
  const mutation = useMutation({
    mutationFn: async () =>
      (
        await StockService.stornoStockDoc({
          path: { doc_id: docId },
          body: { sabab: sabab.trim() },
        })
      ).data,
    onSuccess: (st) => {
      toast.success(`${no} bekor qilindi — ${st.no}`)
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ["stock"] })
      queryClient.invalidateQueries({ queryKey: ["catalog"] })
    },
    onError: handleError,
  })
  if (!(u?.is_superuser || u?.role === "director")) return null
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Undo2 /> Storno
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{no} — storno</DialogTitle>
            <DialogDescription>
              Hujjat o'chirilmaydi: uning ta'siri teskari STORNO hujjati bilan
              qaytariladi, ikkalasi ham jurnalda qoladi. Kirim faqat undan hali
              hech narsa sotilmagan yoki sarflanmagan bo'lsa bekor qilinadi.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            autoFocus
            placeholder="Sabab (majburiy)"
            maxLength={200}
            value={sabab}
            onChange={(e) => setSabab(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Bekor
            </Button>
            <LoadingButton
              variant="destructive"
              loading={mutation.isPending}
              disabled={!sabab.trim()}
              onClick={() => mutation.mutate()}
            >
              Storno qilish
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
