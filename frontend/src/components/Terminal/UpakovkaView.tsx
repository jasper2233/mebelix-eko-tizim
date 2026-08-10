// QADOQLASH post sahifasi (TZ Upakovka): proyekt tanlangach shu ekran ochiladi.
//
// Oqim: "Qadoq yaratish" -> detallarni birma-bir skanerlash -> "Yakunlash".
// Tarkibni algoritm emas, qadoqlovchi belgilaydi. Tizim faqat taxminiy og'irlikni
// KO'RSATADI — hech narsani bloklamaydi, qaror hodimniki.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, PackagePlus, Trash2 } from "lucide-react"
import { useEffect, useRef } from "react"
import { toast } from "sonner"

import { PachkaService } from "@/client"
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
  const { data, isLoading } = useQuery({
    queryKey: ["terminal", "upakovka", orderId],
    queryFn: () => PachkaService.readUpakovkaOrder({ orderId }),
    refetchInterval: 30_000,
  })

  const put = (d: typeof data) =>
    queryClient.setQueryData(["terminal", "upakovka", orderId], d)

  const create = useMutation({
    mutationFn: () => PachkaService.createPachka({ orderId }),
    onSuccess: put,
    onError: (e) => toast.error(detailMessage(e)),
  })
  const scan = useMutation({
    mutationFn: (v: { pachkaId: number; qr: string }) =>
      PachkaService.scanIntoPachka({
        pachkaId: v.pachkaId,
        requestBody: { qr_text: v.qr },
      }),
    onSuccess: put,
    onError: (e) => toast.error(detailMessage(e)),
  })
  const remove = useMutation({
    mutationFn: (v: { pachkaId: number; instanceId: number }) =>
      PachkaService.removeFromPachka({
        pachkaId: v.pachkaId,
        instanceId: v.instanceId,
      }),
    onSuccess: put,
    onError: (e) => toast.error(detailMessage(e)),
  })
  const close = useMutation({
    mutationFn: (pachkaId: number) => PachkaService.closePachka({ pachkaId }),
    onSuccess: (r) => {
      toast.success(r.message)
      queryClient.invalidateQueries({ queryKey: ["terminal", "upakovka"] })
    },
    onError: (e) => toast.error(detailMessage(e)),
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
        toast.error("Avval qadoq yarating")
        return
      }
      scan.mutate({ pachkaId: id, qr })
    })
    return () => registerScan?.(null)
  }, [registerScan, scan.mutate])

  if (isLoading) return <Skeleton className="h-full w-full" />

  const pending = data?.pending ?? []
  const closed = pachkas.filter((p) => p.status !== "open")

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* CHAP: ochiq qadoq — skan shu yerga tushadi */}
      <div className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
        <div className="flex items-center gap-3 border-b px-4 py-2">
          <Button
            variant="outline"
            className="h-12 px-4 text-base font-bold"
            onClick={onBack}
          >
            <ArrowLeft /> Orqaga
          </Button>
          <div className="min-w-0">
            <div className="truncate text-lg font-black">
              {data?.order_number}
            </div>
            {data?.project_name && (
              <div className="truncate text-xs text-muted-foreground">
                {data.project_name}
              </div>
            )}
          </div>
          <LoadingButton
            className="ml-auto h-12 px-4 text-base font-bold"
            loading={create.isPending}
            disabled={!!open}
            onClick={() => create.mutate()}
          >
            <PackagePlus /> Qadoq yaratish
          </LoadingButton>
        </div>

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
                  <tbody>
                    {open.items.map((i) => (
                      <tr
                        key={i.instance_id}
                        className="border-b last:border-0"
                      >
                        <td className="num px-4 py-3 font-semibold">
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
                            size="sm"
                            aria-label={`${i.part_code} ni chiqarish`}
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
                <span className="num font-semibold">{p.qr_text}</span>
                <span className="truncate">{p.part_name}</span>
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
