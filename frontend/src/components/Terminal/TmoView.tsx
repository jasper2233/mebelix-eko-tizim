// TMO (Tayyor Mahsulot Ombori) post sahifasi — marshrutning oxirgi qadami.
//
// Ro'yxat — umumiy `PostQueueView` (BOYOQ/STOLYARKA bilan bir naqsh): detal
// bo'yicha qator, nusxalar №n chip (kulrang — tayyor, qabul kutilmoqda; ✓ —
// qabul qilindi), hali tsexdagilar «+N yo'lda». Ilgari o'z ikki tabi bor edi:
// 981 nusxali buyurtmada 872 qatorli ro'yxat, bir xil sonlar sarlavhada uch
// joyda, hech qachon to'lmaydigan «Qadoq» ustuni. Umumiy navbat endpointi TMO
// uchun ham aynan shu holatni beradi (2026-09-04 da uch buyurtmada
// `TmoOrderState` bilan son-ma-son solishtirildi: 37/33/1/3, 981/0/872/109,
// 52/0/44/8).
//
// Bu yerda faqat SKAN qoladi: qadoq cheki (`PK-...`) detal QR'i emas — umumiy
// skan yo'li uni rad etardi; server ichidagi HAMMA nusxani birdan qabul qiladi
// (`accept_into_tmo`), ya'ni omborchi uchun chek va yakka detal bir xil.
//
// TMO buyurtmani TOPSHIRMAYDI. Hamma detal TMO dan o'tgach buyurtma o'zi
// TAYYOR (COMPLETED) bo'ladi, TOPSHIRILDI esa managerning amali
// (`/orders/{id}` sahifasidagi tugma, faqat TAYYOR holatdan).

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { toast } from "sonner"

import type { PostQueueState } from "@/client"
import { TmoService } from "@/client"
import {
  playError,
  playSuccess,
  playWarning,
} from "@/components/Terminal/audio"
import { PostQueueView } from "@/components/Terminal/PostQueueView"
import { detailMessage } from "@/utils"

export function TmoView({
  orderId,
  onBack,
  registerScan,
}: {
  orderId: number
  onBack: () => void
  /** Skanni shu ekran yozadi: qadoq QR'i umuman detal QR'i emas — umumiy skan
   *  yo'li uni rad etardi. */
  registerScan?: (fn: ((qr: string) => void) | null) => void
}) {
  const queryClient = useQueryClient()
  const key = ["terminal", "queue", orderId]

  const accept = useMutation({
    mutationFn: async (qr: string) =>
      (
        await TmoService.acceptIntoTmo({
          path: { order_id: orderId },
          body: { qr_text: qr },
        })
      ).data,
    // Muvaffaqiyat XABARI shu yerda tug'iladi: TMO skani `viewScanRef` orqali
    // ketadi va terminalning umumiy oqimini (ovoz + yashil banner) chetlab o'tadi.
    onSuccess: (d, qr) => {
      // Takroriy skan xato bermaydi (`client_event_id` barqaror, server 200) —
      // yangilik borligi qabul SONIDAN bilinadi: keshdagi ✓ chiplar vs javob.
      // Kesh hali yo'q bo'lsa (skan yuklanish paytida) — oddiy tasdiq.
      const cached = queryClient.getQueryData<PostQueueState>(key)
      queryClient.invalidateQueries({ queryKey: key })
      const yangi = cached
        ? d.accepted - cached.rows.filter((r) => r.done).length
        : 1
      // ID alohida qatorda: matn ichida u defisdan sinib ikkiga bo'linardi
      if (yangi <= 0) {
        playWarning()
        toast.error("Allaqachon qabul qilingan", { description: qr })
        return
      }
      playSuccess()
      if (yangi > 1) toast.success(`Qadoq qabul qilindi — ${yangi} detal`)
      else toast.success("Qabul qilindi", { description: qr })
    },
    onError: (e) => {
      playError()
      toast.error(detailMessage(e))
    },
  })

  useEffect(() => {
    registerScan?.((qr) => accept.mutate(qr))
    return () => registerScan?.(null)
  }, [registerScan, accept.mutate])

  return <PostQueueView orderId={orderId} onBack={onBack} />
}
