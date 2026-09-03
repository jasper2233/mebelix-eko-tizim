// TMO (Tayyor Mahsulot Ombori) post sahifasi — marshrutning oxirgi qadami.
//
// Ikki tab, chunki ikki xil ish: QABULGA KELGAN (skanerlanadi) va QABUL
// QILINGAN (serverdagi yozuv, sahifa yangilansa ham qoladi). Alohida
// "Qadoqlar" tabi yo'q — qadoq cheki (`PK-...`) ham shu QABUL oqimidan o'tadi.
//
// TMO buyurtmani TOPSHIRMAYDI. Hamma detal TMO dan o'tgach buyurtma o'zi
// TAYYOR (COMPLETED) bo'ladi, TOPSHIRILDI esa managerning amali
// (`/orders/{id}` sahifasidagi tugma, faqat TAYYOR holatdan).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, PackageCheck } from "lucide-react"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { TmoService } from "@/client"
import { QueryError } from "@/components/Common/QueryError"
import {
  playError,
  playSuccess,
  playWarning,
} from "@/components/Terminal/audio"
import { PostHeader } from "@/components/Terminal/PostHeader"
import { PostProgress } from "@/components/Terminal/PostProgress"
import { Serial } from "@/components/Terminal/Serial"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { detailMessage } from "@/utils"

/** "14:32" — omborchi uchun soat yetarli, sana kerak emas: ro'yxat shu buyurtmaniki. */
function shortTime(value: string): string {
  const d = new Date(value)
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" })
}

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
  const [tab, setTab] = useState<"kelgan" | "qilingan">("kelgan")
  const { data, isLoading, isError, refetch } = useQuery({
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
    // 30 s'lik fon so'rovi uchib turgan bo'lsa, uning ESKI javobi quyidagi
    // `put` natijasini ustidan yozadi — qabul qilingan detal yana kutayotganlar
    // ro'yxatiga qaytadi. Shuning uchun avval fon so'rovi bekor qilinadi.
    onMutate: () =>
      queryClient.cancelQueries({ queryKey: ["terminal", "tmo", orderId] }),
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

  useEffect(() => {
    registerScan?.((qr) => {
      // Har qanday skan — QABUL. Qadoq cheki (`PK-...`) bo'lsa server ichidagi
      // hamma nusxani birdan qabul qiladi (`accept_into_tmo`), ya'ni omborchi
      // uchun chek va yakka detal bir xil ishlaydi.
      accept.mutate(qr)
    })
    return () => registerScan?.(null)
  }, [registerScan, accept.mutate])

  if (isLoading) return <Skeleton className="h-full w-full" />
  // Xato JIM yutilmasin: busiz `data` undefined qolib, bo'sh ro'yxat yashil
  // "Hammasi qabul qilindi." ga aylanardi va omborchi ishni tugagan deb o'qirdi.
  if (isError) return <QueryError onRetry={() => refetch()} />

  const pending = data?.pending ?? []
  const done = data?.done ?? []
  const delivered = data?.order_status === "delivered"
  // Omborchining ISH ro'yxati — faqat oxirgi bosqichdan o'tib kelganlar.
  // Qolganlari hali tsexda; har biriga ishi TUGAGAN post yoziladi, ya'ni
  // omborchi detalni jismonan qaysi postdan olishini biladi.
  const arrived = pending.filter((p) => p.ready)
  const inShop = pending.filter((p) => !p.ready)

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border bg-white">
      <PostHeader
        onBack={onBack}
        orderNumber={data?.order_number}
        projectName={data?.project_name}
      >
        {/* Uchta son ATAYLAB alohida: omborchi "nechtasi keldi" va "nechtasini
            men skanerladim" ni ajratishi kerak. Bitta progress bar faqat
            skanerlanganini ko'rsatardi — kelgan-u hali qabul qilinmagani
            ko'rinmasdi, ya'ni oldida qancha ish turgani bilinmasdi. */}
        <div className="ml-auto flex items-center gap-4">
          <span className="text-sm font-bold">
            <span className="text-muted-foreground">TMO ga keldi: </span>
            <span className="num text-base">{data?.arrived ?? 0}</span>
            <span className="text-muted-foreground">/{data?.total ?? 0}</span>
          </span>
          <span className="text-sm font-bold">
            <span className="text-muted-foreground">Qabul qilindi: </span>
            <span className="num text-base text-green-700">
              {data?.accepted ?? 0}
            </span>
            <span className="text-muted-foreground">/{data?.total ?? 0}</span>
          </span>
          <PostProgress done={data?.accepted ?? 0} total={data?.total ?? 0} />
        </div>
        {delivered && (
          <span className="rounded-sm bg-green-100 px-2 py-1 text-sm font-black text-green-700">
            TOPSHIRILGAN
          </span>
        )}
      </PostHeader>

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as typeof tab)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList className="mx-4 mt-3 h-14 w-fit">
          <TabsTrigger value="kelgan" className="h-12 px-6 text-base font-bold">
            <PackageCheck /> Qabulga kelgan ({arrived.length})
          </TabsTrigger>
          <TabsTrigger
            value="qilingan"
            className="h-12 px-6 text-base font-bold"
          >
            <Check /> Qabul qilingan ({done.length})
          </TabsTrigger>
        </TabsList>

        {/* QABULGA KELGAN: TMO da turgan, hali skanerlanmagan nusxalar.
            Qadoq cheki (`PK-...`) skanerlansa ichidagi HAMMA nusxa birdan
            "Qabul qilingan" ga o'tadi — alohida "Qadoqlar" ro'yxati kerak emas,
            omborchi baribir DETAL ro'yxatini ko'radi. */}
        <TabsContent value="kelgan" className="min-h-0 flex-1 overflow-y-auto">
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
                    <td className="px-4 py-2.5 text-lg font-semibold">
                      <Serial code={p.qr_text} />
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
                      <td className="px-4 py-1.5">
                        <Serial code={p.qr_text} />
                      </td>
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

        {/* QABUL QILINGAN: serverdan keladi, ya'ni sahifa yangilansa ham qoladi.
            Ilgari bu ro'yxat faqat React state'da edi (shu smenadagi skanlar) —
            omborchi sahifani yangilasa o'zi qabul qilgan detallar ko'rinmasdi. */}
        <TabsContent
          value="qilingan"
          className="min-h-0 flex-1 overflow-y-auto"
        >
          {!done.length ? (
            <div className="p-8 text-center text-lg font-bold text-muted-foreground">
              Hali hech narsa qabul qilinmagan.
            </div>
          ) : (
            <table className="w-full text-base">
              <tbody>
                {done.map((d) => (
                  <tr
                    key={d.instance_id}
                    className="border-b bg-green-50/40 last:border-0"
                  >
                    <td className="w-10 py-2.5 pl-4 text-green-700">
                      <Check className="size-5" />
                    </td>
                    <td className="py-2.5 pr-4 font-semibold text-green-900">
                      <Serial code={d.qr_text} />
                    </td>
                    <td className="max-w-[280px] truncate px-4 py-2.5 text-green-900">
                      {d.part_name}
                    </td>
                    {/* Qadoq cheki bilan kelgan bo'lsa — qaysi chek ekani */}
                    <td className="num px-4 py-2.5 text-sm font-semibold text-blue-800">
                      {d.pachka_code ?? ""}
                    </td>
                    <td className="num px-4 py-2.5 text-right text-sm text-muted-foreground">
                      {shortTime(d.accepted_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
