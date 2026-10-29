// Terminal (arra / kromka / oval): buyurtmaning SHU postga kerakli materiali va «Material so'rash»
// (EKO TZ §4.4, 2.3b). Ikki yo'l teng: hodim so'raydi yoki omborchi oldindan yetkazadi — so'rov
// majburiy emas. Kromkachi sexdagi rulon amalda tugaganini shu yerdan belgilaydi.
// Jarayon hodimi ekrani: katta yozuv, katta tugmalar, brauzer `confirm()` yo'q (ikki bosqichli tasdiq).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Package, Send } from "lucide-react"
import { useState } from "react"

import { OmborService } from "@/client"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { formatDateTime } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { fmtQty, num } from "@/lib/warehouse"
import { handleError } from "@/utils"

export function MaterialButton({
  orderId,
  post,
}: {
  orderId: number
  post: string
}) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [tasdiq, setTasdiq] = useState<string | null>(null)
  const key = ["ombor", "sex", orderId, post]
  const { data } = useQuery({
    queryKey: key,
    queryFn: async () =>
      (
        await OmborService.readSexMaterial({
          path: { order_id: orderId },
          query: { post },
        })
      ).data,
    refetchInterval: 30_000,
  })
  const sora = useMutation({
    mutationFn: () =>
      OmborService.createMaterialSorov({
        path: { order_id: orderId },
        body: { post, izoh: "" },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
    onError: handleError,
  })
  const tugadi = useMutation({
    mutationFn: (barkod: string) =>
      OmborService.sexRulonTugadi({ path: { barkod } }),
    onSuccess: () => {
      setTasdiq(null)
      queryClient.invalidateQueries({ queryKey: key })
    },
    onError: handleError,
  })

  const lines = data?.lines ?? []
  const hammasi = lines.length > 0 && lines.every((l) => num(l.qoldi) <= 0)

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "fixed right-6 bottom-6 z-30 flex items-center gap-2 rounded-2xl px-5 py-4 text-lg font-bold shadow-lg active:scale-95",
          data?.sorov
            ? "bg-amber-500 text-white"
            : hammasi
              ? "bg-green-600 text-white"
              : "bg-primary text-primary-foreground",
        )}
      >
        <Package className="size-7" />
        {data?.sorov
          ? "So'rov yuborilgan"
          : hammasi
            ? "Material berilgan"
            : "Material"}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-2xl">
              {data?.order_number} — material
            </DialogTitle>
          </DialogHeader>
          {lines.length === 0 ? (
            <p className="text-lg text-muted-foreground">
              Bu post uchun material ro'yxati yo'q (rezerv qurilmagan).
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {lines.map((l) => (
                <div
                  key={l.line_id}
                  className={cn(
                    "rounded-xl border p-3",
                    num(l.qoldi) <= 0 && "bg-green-50",
                  )}
                >
                  <div className="flex items-baseline gap-3">
                    <span className="flex-1 text-lg font-semibold">
                      {l.nom}
                    </span>
                    <span className="num text-xl font-bold">
                      {fmtQty(l.berilgan)} / {fmtQty(l.kerak)} {l.unit ?? ""}
                    </span>
                  </div>
                  <div className="text-base text-muted-foreground">
                    {num(l.qoldi) > 0
                      ? `Yana ${fmtQty(l.qoldi)} ${l.unit ?? ""} kerak`
                      : "To'liq berilgan"}
                  </div>
                  {l.sexda.map((u) => (
                    <div
                      key={u.id}
                      className="mt-2 flex items-center gap-3 rounded-lg bg-emerald-50 p-2"
                    >
                      <span className="flex-1 text-base">
                        Sexdagi rulon <b className="font-mono">{u.barkod}</b> ·
                        hisobda <b className="num">{fmtQty(u.qoldiq)} m</b>
                      </span>
                      {tasdiq === u.barkod ? (
                        <>
                          <LoadingButton
                            size="lg"
                            variant="destructive"
                            loading={tugadi.isPending}
                            onClick={() => tugadi.mutate(u.barkod as string)}
                          >
                            Ha, tugadi
                          </LoadingButton>
                          <button
                            type="button"
                            className="px-3 text-base underline"
                            onClick={() => setTasdiq(null)}
                          >
                            Yo'q
                          </button>
                        </>
                      ) : (
                        <LoadingButton
                          size="lg"
                          variant="outline"
                          onClick={() => setTasdiq(u.barkod)}
                        >
                          Rulon tugadi
                        </LoadingButton>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
          {data?.tosiq && (
            <p className="text-base font-semibold text-amber-700">
              Material hali berilmaydi: {data.tosiq}
            </p>
          )}
          {data?.sorov ? (
            <div className="rounded-xl bg-amber-100 p-4 text-lg font-semibold text-amber-900">
              So'rov yuborilgan ({formatDateTime(data.sorov.created_at)}) —
              omborchi olib keladi.
            </div>
          ) : (
            !hammasi &&
            lines.length > 0 && (
              <LoadingButton
                className="h-16 text-xl"
                loading={sora.isPending}
                onClick={() => sora.mutate()}
              >
                <Send className="size-6" /> Material so'rash
              </LoadingButton>
            )
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
