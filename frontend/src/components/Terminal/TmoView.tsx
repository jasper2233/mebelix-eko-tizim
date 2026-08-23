// TMO (Tayyor Mahsulot Ombori) post sahifasi — marshrutning oxirgi qadami.
//
// Ikki tab, chunki ikki xil ish: QABUL (kelganini skanerlash) va TOPSHIRISH
// (mijozga berish). Bir ekranda aralashsa omborchi tasodifan topshirilmagan
// narsani topshirilgan deb belgilab qo'yardi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Check, PackageCheck, Truck } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { TmoService } from "@/client"
import {
  playError,
  playSuccess,
  playWarning,
} from "@/components/Terminal/audio"
import { PostProgress } from "@/components/Terminal/PostProgress"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { detailMessage } from "@/utils"

export function TmoView({
  orderId,
  onBack,
  registerScan,
}: {
  orderId: number
  onBack: () => void
  /** Skanni shu ekran yozadi: aktiv tabga qarab qabul yoki topshirish bo'ladi,
   *  qadoq QR'i esa umuman detal QR'i emas — umumiy skan yo'li uni rad etardi. */
  registerScan?: (fn: ((qr: string) => void) | null) => void
}) {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<"qabul" | "topshirish">("qabul")
  //: Shu smenada qabul qilinganlar. Server javobida ular `pending` dan
  //: CHIQIB KETADI (tmo.py: qabul qilingan nusxa ro'yxatga qo'shilmaydi), ya'ni
  //: skanerlangan detal ekrandan jimgina yo'qolardi va omborchi skan
  //: o'tgan-o'tmaganini bilolmasdi. Endi ular ro'yxat oxirida belgi bilan
  //: turadi — bu ish emas, TASDIQ.
  const [qabulQilingan, setQabulQilingan] = useState<
    { instance_id: number; qr_text: string; part_name: string }[]
  >([])
  const { data, isLoading } = useQuery({
    queryKey: ["terminal", "tmo", orderId],
    queryFn: async () =>
      (await TmoService.readTmoOrder({ path: { order_id: orderId } })).data,
    refetchInterval: 30_000,
  })

  const put = (d: typeof data) =>
    queryClient.setQueryData(["terminal", "tmo", orderId], d)

  const accept = useMutation({
    mutationFn: async (qr: string) =>
      (
        await TmoService.acceptIntoTmo({
          path: { order_id: orderId },
          body: { qr_text: qr },
        })
      ).data,
    // Muvaffaqiyat XABARI shu yerda tug'iladi: TMO skani `viewScanRef` orqali
    // ketadi va terminalning umumiy oqimini (ovoz + yashil banner) chetlab
    // o'tadi. Ilgari bu yerda faqat `put` bor edi — operator hech qanday
    // javob olmasdi.
    onSuccess: (d, qr) => {
      const oldin = queryClient.getQueryData<typeof data>([
        "terminal",
        "tmo",
        orderId,
      ])
      const qoldi = new Set((d?.pending ?? []).map((p) => p.instance_id))
      const yangi = (oldin?.pending ?? []).filter(
        (p) => !qoldi.has(p.instance_id),
      )
      put(d)
      // Takroriy skan xato bermaydi: `client_event_id` barqaror
      // (`wh-{order}-{qr}`), ya'ni server 200 qaytaradi va ro'yxat o'zgarmaydi.
      if (!yangi.length) {
        playWarning()
        toast.error(`Allaqachon qabul qilingan: ${qr}`)
        return
      }
      setQabulQilingan((oldingi) => [...oldingi, ...yangi])
      playSuccess()
      toast.success(
        yangi.length > 1
          ? `Qadoq qabul qilindi — ${yangi.length} detal`
          : `Qabul qilindi: ${yangi[0].qr_text}`,
      )
    },
    onError: (e) => {
      playError()
      toast.error(detailMessage(e))
    },
  })
  const ship = useMutation({
    mutationFn: async (code: string) =>
      (
        await TmoService.shipPachka({
          path: { order_id: orderId },
          body: { qr_text: code },
        })
      ).data,
    onSuccess: (d) => {
      put(d)
      toast.success("Qadoq topshirildi")
    },
    onError: (e) => toast.error(detailMessage(e)),
  })
  const deliver = useMutation({
    mutationFn: async () =>
      (await TmoService.deliverTmoOrder({ path: { order_id: orderId } })).data,
    onSuccess: (r) => {
      toast.success(r.message)
      queryClient.invalidateQueries({ queryKey: ["terminal", "tmo"] })
    },
    onError: (e) => toast.error(detailMessage(e)),
  })

  // Skan aktiv tabga ketadi. Ref: terminal callback'ni bir marta ro'yxatga
  // oladi, tab esa keyin ham o'zgaradi.
  const tabRef = useRef(tab)
  tabRef.current = tab
  useEffect(() => {
    registerScan?.((qr) => {
      if (tabRef.current === "qabul") accept.mutate(qr)
      else if (qr.toUpperCase().startsWith("PK-")) ship.mutate(qr)
      else toast.error("Topshirish uchun qadoq QR'ini skanerlang")
    })
    return () => registerScan?.(null)
  }, [registerScan, accept.mutate, ship.mutate])

  if (isLoading) return <Skeleton className="h-full w-full" />

  const pending = data?.pending ?? []
  const pachkas = data?.pachkas ?? []
  const delivered = data?.order_status === "delivered"
  const shipped = pachkas.filter((p) => p.shipped_at)
  // Omborchining ISH ro'yxati — faqat oxirgi bosqichdan o'tib kelganlar.
  // Qolganlari hali tsexda; har biriga ishi TUGAGAN post yoziladi, ya'ni
  // omborchi detalni jismonan qaysi postdan olishini biladi.
  const arrived = pending.filter((p) => p.ready)
  const inShop = pending.filter((p) => !p.ready)

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border bg-white">
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
        <PostProgress
          className="ml-auto"
          done={data?.accepted ?? 0}
          total={data?.total ?? 0}
        />
        {delivered && (
          <span className="rounded-sm bg-green-100 px-2 py-1 text-sm font-black text-green-700">
            TOPSHIRILGAN
          </span>
        )}
      </div>

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as typeof tab)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList className="mx-4 mt-3 h-12 w-fit">
          <TabsTrigger value="qabul" className="h-10 px-6 text-base font-bold">
            <PackageCheck /> Qabul ({arrived.length})
          </TabsTrigger>
          <TabsTrigger
            value="topshirish"
            className="h-10 px-6 text-base font-bold"
          >
            <Truck /> Topshirish ({shipped.length}/{pachkas.length})
          </TabsTrigger>
        </TabsList>

        {/* QABUL: skanerlanmagan nusxalar. Qadoq QR'i bittada hammasini yopadi. */}
        <TabsContent value="qabul" className="min-h-0 flex-1 overflow-y-auto">
          {!arrived.length ? (
            <div className="p-8 text-center text-lg font-bold">
              {pending.length ? (
                <span className="text-amber-700">
                  TMO ga yetib kelgan detal yo'q — hammasi hali tsexda.
                </span>
              ) : (
                <span className="text-green-700">Hammasi qabul qilindi.</span>
              )}
            </div>
          ) : (
            <table className="w-full text-base">
              <tbody>
                {arrived.map((p) => (
                  <tr key={p.instance_id} className="border-b last:border-0">
                    <td className="num px-4 py-2.5 font-semibold">
                      {p.qr_text}
                    </td>
                    <td className="max-w-[280px] truncate px-4 py-2.5">
                      {p.part_name}
                    </td>
                    <td className="num px-4 py-2.5 text-sm font-semibold text-blue-800">
                      {p.pachka_code ?? ""}
                    </td>
                    {/* Detal shu postdan keyin turibdi — omborchi o'sha yerdan oladi */}
                    <td className="px-4 py-2.5 text-right text-sm font-semibold">
                      {p.stage}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Shu smenada qabul qilinganlar — ro'yxat oxirida, belgi bilan.
              Ular serverning `pending` ro'yxatidan chiqib ketgan; bu yerda
              faqat TASDIQ uchun turadi va sahifa yangilanganda ketadi. */}
          {!!qabulQilingan.length && (
            <table className="w-full border-t text-base">
              <tbody>
                {qabulQilingan.map((p) => (
                  <tr
                    key={`ok${p.instance_id}`}
                    className="border-b bg-green-50 last:border-0"
                  >
                    <td className="w-10 py-2.5 pl-4 text-green-700">
                      <Check className="size-5" />
                    </td>
                    <td className="num py-2.5 pr-4 font-semibold text-green-800">
                      {p.qr_text}
                    </td>
                    <td className="max-w-[280px] truncate px-4 py-2.5 text-green-800">
                      {p.part_name}
                    </td>
                    <td className="px-4 py-2.5 text-right text-sm font-bold text-green-700">
                      qabul qilindi
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Hali tsexdagilar: qaysi postda turgani yozilgan — omborchi qidirib yurmasin */}
          {!!inShop.length && (
            <div className="mt-3 border-t">
              <div className="px-4 py-2 text-sm font-bold text-muted-foreground">
                Tsexda <span className="num">({inShop.length})</span>
              </div>
              <table className="w-full text-sm text-muted-foreground">
                <tbody>
                  {inShop.map((p) => (
                    <tr key={p.instance_id} className="border-b last:border-0">
                      <td className="num px-4 py-1.5">{p.qr_text}</td>
                      <td className="max-w-[280px] truncate px-4 py-1.5">
                        {p.part_name}
                      </td>
                      <td className="px-4 py-1.5 text-right font-semibold text-amber-700">
                        {p.stage || "hali kesilmagan"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        {/* TOPSHIRISH: qadoq bo'yicha. Qadoqsiz buyurtmada butun buyurtma birdan. */}
        <TabsContent
          value="topshirish"
          className="min-h-0 flex-1 overflow-y-auto"
        >
          {data?.packaging ? (
            <table className="w-full text-base">
              <tbody>
                {pachkas.map((p) => {
                  const full = p.accepted_count >= p.item_count
                  return (
                    <tr key={p.id} className="border-b last:border-0">
                      <td className="num px-4 py-3 text-lg font-black">
                        {p.code}
                      </td>
                      <td className="num px-4 py-3">
                        {p.accepted_count}/{p.item_count} detal
                      </td>
                      <td className="num px-4 py-3 text-muted-foreground">
                        ~{p.weight_kg} kg
                      </td>
                      <td className="px-4 py-3 text-right">
                        {p.shipped_at ? (
                          <span className="font-bold text-green-700">
                            ✓ Topshirildi
                          </span>
                        ) : (
                          <LoadingButton
                            className="h-12 px-5 text-base font-bold"
                            loading={ship.isPending}
                            disabled={!full}
                            onClick={() => ship.mutate(p.code)}
                          >
                            {full ? "Topshirish" : "Qabul qilinmagan"}
                          </LoadingButton>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {!pachkas.length && (
                  <tr>
                    <td className="p-8 text-center text-muted-foreground">
                      Hali qadoq yo'q.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          ) : (
            <div className="flex flex-col items-center gap-4 p-8 text-center">
              <p className="text-base text-muted-foreground">
                Bu buyurtma qadoqlanmaydi — mahsulot detal bo'yicha qabul
                qilinadi va butunligicha topshiriladi.
              </p>
              <LoadingButton
                className="h-14 px-8 text-lg font-black"
                loading={deliver.isPending}
                disabled={!!pending.length || delivered}
                onClick={() => deliver.mutate()}
              >
                <Truck />
                {delivered ? "Topshirilgan" : "Buyurtmani topshirish"}
              </LoadingButton>
              {!!pending.length && (
                <p className="text-sm text-amber-700">
                  {pending.length} detal hali qabul qilinmagan.
                </p>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
