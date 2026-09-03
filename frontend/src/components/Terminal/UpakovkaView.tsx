// QADOQLASH post sahifasi (TZ Upakovka): proyekt tanlangach shu ekran ochiladi.
//
// Oqim: "Qadoq yaratish" -> detallarni birma-bir skanerlash -> "Yakunlash".
// Tarkibni algoritm emas, qadoqlovchi belgilaydi. Tizim faqat taxminiy og'irlikni
// KO'RSATADI — hech narsani bloklamaydi, qaror hodimniki.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { PackagePlus, Trash2 } from "lucide-react"
import { useEffect, useRef } from "react"
import { toast } from "sonner"

import { PachkaService } from "@/client"
import { QueryError } from "@/components/Common/QueryError"
import {
  playError,
  playSuccess,
  playWarning,
} from "@/components/Terminal/audio"
import { PostHeader } from "@/components/Terminal/PostHeader"
import { Serial } from "@/components/Terminal/Serial"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatSize } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { detailMessage } from "@/utils"

export function UpakovkaView({
  orderId,
  onBack,
  registerScan,
}: {
  orderId: number
  onBack: () => void
  /** Skanni shu ekran o'zi yozadi — terminalning umumiy skan yo'li chetlab o'tiladi:
   *  detal qaysi QADOQqa tushishini faqat shu ekran biladi. */
  registerScan?: (fn: ((qr: string) => void) | null) => void
}) {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["terminal", "upakovka", orderId],
    queryFn: async () =>
      (await PachkaService.readUpakovkaOrder({ path: { order_id: orderId } }))
        .data,
    refetchInterval: 30_000,
  })

  const put = (d: typeof data) =>
    queryClient.setQueryData(["terminal", "upakovka", orderId], d)

  const create = useMutation({
    mutationFn: async () =>
      (await PachkaService.createPachka({ path: { order_id: orderId } })).data,
    onSuccess: put,
    onError: (e) => {
      playError()
      toast.error(detailMessage(e))
    },
  })
  const scan = useMutation({
    mutationFn: async (v: { pachkaId: number; qr: string }) =>
      (
        await PachkaService.scanIntoPachka({
          path: { pachka_id: v.pachkaId },
          body: { qr_text: v.qr },
        })
      ).data,
    // Javob XABARI shu yerda tug'iladi: qadoqlash skani `registerScan` orqali
    // ketadi va terminalning umumiy oqimini (ovoz + banner) chetlab o'tadi.
    // Ilgari bu yerda faqat `put` bor edi — operator hech qanday javob olmasdi.
    onSuccess: (d, v) => {
      put(d)
      playSuccess()
      toast.success(`Qadoqqa qo'shildi: ${v.qr}`)
    },
    onError: (e) => {
      playError()
      toast.error(detailMessage(e))
    },
  })
  const remove = useMutation({
    mutationFn: async (v: { pachkaId: number; instanceId: number }) =>
      (
        await PachkaService.removeFromPachka({
          path: { pachka_id: v.pachkaId, instance_id: v.instanceId },
        })
      ).data,
    onSuccess: put,
    onError: (e) => {
      playError()
      toast.error(detailMessage(e))
    },
  })
  // Yopiq qadoqni tuzatishning YAGONA yo'li: qayta ochib, tuzatib, qayta yakunlash
  // (yakunlash chekni navbatga yangidan qo'yadi).
  const reopen = useMutation({
    mutationFn: async (pachkaId: number) =>
      (await PachkaService.reopenPachka({ path: { pachka_id: pachkaId } }))
        .data,
    onSuccess: put,
    onError: (e) => {
      playError()
      toast.error(detailMessage(e))
    },
  })
  const close = useMutation({
    mutationFn: async (pachkaId: number) =>
      (await PachkaService.closePachka({ path: { pachka_id: pachkaId } })).data,
    onSuccess: (r) => {
      toast.success(r.message)
      queryClient.invalidateQueries({ queryKey: ["terminal", "upakovka"] })
    },
    onError: (e) => {
      playError()
      toast.error(detailMessage(e))
    },
  })

  const pachkas = data?.pachkas ?? []
  const open = pachkas.find((p) => p.status === "open")

  // Skan ochiq qadoqqa ketadi. Ref orqali: terminal callback'ni bir marta
  // ro'yxatga oladi, ochiq qadoq esa har javobdan keyin o'zgaradi.
  const openRef = useRef<number | null>(null)
  openRef.current = open?.id ?? null
  useEffect(() => {
    registerScan?.((qr) => {
      const id = openRef.current
      if (id == null) {
        playWarning()
        toast.error("Avval qadoq yarating")
        return
      }
      scan.mutate({ pachkaId: id, qr })
    })
    return () => registerScan?.(null)
  }, [registerScan, scan.mutate])

  if (isLoading) return <Skeleton className="h-full w-full" />
  // Xatoni yutib bo'lmaydi: aks holda kiosk "Ochiq qadoq yo'q" va "Hammasi
  // qadoqlangan." deb yolg'on tinch holat ko'rsatardi.
  if (isError) return <QueryError onRetry={() => refetch()} />

  const pending = data?.pending ?? []
  const closed = pachkas.filter((p) => p.status !== "open")

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* CHAP: ochiq qadoq — skan shu yerga tushadi */}
      <div className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
        <PostHeader
          onBack={onBack}
          orderNumber={data?.order_number}
          projectName={data?.project_name}
        >
          <LoadingButton
            className="ml-auto h-12 px-4 text-base font-bold"
            loading={create.isPending}
            disabled={!!open}
            onClick={() => create.mutate()}
          >
            <PackagePlus /> Qadoq yaratish
          </LoadingButton>
        </PostHeader>

        {!open ? (
          <div className="flex flex-1 items-center justify-center p-6 text-center text-muted-foreground">
            Ochiq qadoq yo'q — "Qadoq yaratish" bilan boshlang.
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-3 border-b px-4 py-2">
              <span className="num text-xl font-black">{open.code}</span>
              <span className="text-base">{open.items?.length ?? 0} detal</span>
              {/* Og'irlik TAXMINIY (hajm × zichlik) — chegara emas, mo'ljal */}
              <span className="num ml-auto text-base text-muted-foreground">
                ~{open.weight_kg} kg
              </span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {!open.items?.length ? (
                <div className="p-6 text-center text-muted-foreground">
                  Detalni skanerlang — u shu qadoqqa tushadi.
                </div>
              ) : (
                <table className="w-full text-base">
                  <thead className="bg-muted/60">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                        Kod
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                        Nomi
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                        O'lchami
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground">
                        Og'irligi
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-bold uppercase tracking-wider text-muted-foreground" />
                    </tr>
                  </thead>
                  <tbody>
                    {open.items.map((i) => (
                      <tr
                        key={i.instance_id}
                        className="border-b last:border-0"
                      >
                        <td className="num whitespace-nowrap px-4 py-3 font-semibold">
                          {i.part_code}
                        </td>
                        <td className="max-w-[220px] truncate px-4 py-3">
                          {i.part_name}
                        </td>
                        <td className="num whitespace-nowrap px-4 py-3 text-sm">
                          {formatSize(i.length, i.width, i.thickness)}
                        </td>
                        <td className="num px-4 py-3 text-sm text-muted-foreground">
                          ~{i.weight_kg} kg
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            variant="ghost"
                            className="h-11 w-11"
                            aria-label={`${i.part_code} ni chiqarish`}
                            // Ikki marta bosilsa ikkinchi DELETE 404 berardi
                            disabled={remove.isPending}
                            onClick={() =>
                              remove.mutate({
                                pachkaId: open.id,
                                instanceId: i.instance_id,
                              })
                            }
                          >
                            <Trash2 />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div className="border-t p-3">
              <LoadingButton
                className="h-14 w-full text-lg font-black"
                loading={close.isPending}
                disabled={!open.items?.length}
                onClick={() => close.mutate(open.id)}
              >
                Qadoqni yakunlash
              </LoadingButton>
            </div>
          </>
        )}
      </div>

      {/* O'NG: qadoqlanmagan detallar + yopilgan qadoqlar */}
      <div className="flex w-[38%] min-w-[300px] flex-col gap-3">
        <div className="flex min-h-0 flex-1 flex-col rounded-xl border bg-white">
          <div className="border-b px-4 py-2 text-base font-bold">
            Qadoqlanmagan <span className="num">({pending.length})</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {pending.map((p) => (
              <div
                key={p.instance_id}
                className={cn(
                  "flex items-center gap-2 border-b px-4 py-2 text-sm last:border-0",
                  // Tayyor emas = oldingi bosqichi tugamagan; skan baribir rad etiladi
                  !p.ready && "text-muted-foreground",
                )}
              >
                <Serial code={p.qr_text} className="shrink-0 font-semibold" />
                <span className="min-w-0 truncate">{p.part_name}</span>
                {!p.ready && (
                  <span className="ml-auto whitespace-nowrap text-xs">
                    tayyor emas
                  </span>
                )}
              </div>
            ))}
            {!pending.length && (
              <div className="p-4 text-center text-sm text-muted-foreground">
                Hammasi qadoqlangan.
              </div>
            )}
          </div>
        </div>

        <div className="max-h-[38%] min-h-0 overflow-y-auto rounded-xl border bg-white">
          <div className="border-b px-4 py-2 text-base font-bold">
            Yakunlangan <span className="num">({closed.length})</span>
          </div>
          {closed.map((p) => (
            <div
              key={p.id}
              className="flex items-baseline gap-2 border-b px-4 py-2 text-sm last:border-0"
            >
              <span className="num font-semibold">{p.code}</span>
              <span className="text-muted-foreground">
                {p.items?.length ?? 0} detal
              </span>
              <span className="num ml-auto text-muted-foreground">
                ~{p.weight_kg} kg
              </span>
              {/* Ochiq qadoq borida bloklanadi: buyurtmada bir vaqtda bitta
                  ochiq qadoq bo'ladi (backend ham 409 bilan rad etadi). */}
              <LoadingButton
                variant="ghost"
                className="h-11 px-3"
                loading={reopen.isPending}
                disabled={!!open}
                onClick={() => reopen.mutate(p.id)}
              >
                Qayta ochish
              </LoadingButton>
            </div>
          ))}
          {!closed.length && (
            <div className="p-4 text-center text-sm text-muted-foreground">
              Hali yakunlangan qadoq yo'q.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
