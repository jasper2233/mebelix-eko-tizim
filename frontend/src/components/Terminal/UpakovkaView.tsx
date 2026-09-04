// QADOQLASH post sahifasi: proyekt tanlangach shu ekran ochiladi.
//
// Oqim: "Qadoq yaratish" -> detallarni birma-bir skanerlash -> "Qadoqni yakunlash".
// Tarkibni algoritm emas, qadoqlovchi belgilaydi. Tizim faqat taxminiy og'irlikni
// KO'RSATADI — hech narsani bloklamaydi, qaror hodimniki.
//
// Chap — OCHIQ qadoq (skan shu yerga tushadi), o'ng — buyurtmaning hamma detali
// boshqa postlardagi naqshda: bitta detal = bitta qator, nusxalar chip (kulrang —
// tayyor, ✓ — qadoqlangan, «+N yo'lda» — hali tsexda) va pastda yakunlangan
// qadoqlar. 2026-09-04 gacha o'ng ro'yxat nusxa-nusxa edi (981 nusxali buyurtmada
// 981 qator), sarlavhada QOLDIQ yo'q, qadoq jadvalida faqat Kod (uch nusxa —
// uch bir xil qator, qaysi birini chiqarishni bilib bo'lmasdi).
//
// Skan muvaffaqiyati O'Z xabarini bermaydi: skan boshqa postlardagidek terminalning
// yashil tasmasi (WS `scan.recorded`, BEKOR QILISH bilan) orqali ko'rinadi — ilgari
// tasma + toast + ikki «bip» chiqardi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { PackagePlus, Trash2 } from "lucide-react"
import { useEffect, useRef } from "react"
import { toast } from "sonner"

import type { PachkaItemRow, UpakovkaPending } from "@/client"
import { PachkaService } from "@/client"
import { QueryError } from "@/components/Common/QueryError"
import {
  playError,
  playSuccess,
  playWarning,
} from "@/components/Terminal/audio"
import { InstanceChip, instanceNo } from "@/components/Terminal/InstanceChip"
import { PostHeader } from "@/components/Terminal/PostHeader"
import { PostProgress } from "@/components/Terminal/PostProgress"
import { Serial } from "@/components/Terminal/Serial"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatSize } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { detailMessage, detailParts } from "@/utils"

/** Og'irlik TAXMINIY (hajm × zichlik); o'lchamsiz detalda 0 — «yengil» emas, noma'lum */
const kg = (w: number | undefined) => (w ? `~${w} kg` : "—")

type Inst = { instance_id: number; qr_text: string; packed: boolean }
type Group = {
  key: string
  name: string
  instances: Inst[] // tayyor yoki qadoqlangan — chip bo'ladiganlar
  waiting: number // oldingi bosqichi tugamagan — chip yo'q
}

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
  const key = ["terminal", "upakovka", orderId]
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: key,
    queryFn: async () =>
      (await PachkaService.readUpakovkaOrder({ path: { order_id: orderId } }))
        .data,
    refetchInterval: 30_000,
  })

  const put = (d: typeof data) => queryClient.setQueryData(key, d)
  // 30 s'lik fon so'rovi uchib turgan bo'lsa, uning ESKI javobi `put` natijasini
  // ustidan yozadi (TmoView'da tuzatilgan poyga) — avval fon so'rovi bekor qilinadi.
  const cancel = () => queryClient.cancelQueries({ queryKey: key })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: key })
  // Xatodan keyin holat serverdan qayta o'qiladi: boshqa terminal qadoqni yopgan
  // bo'lishi mumkin — ekran «ochiq» deb turaverardi
  const fail = (e: unknown) => {
    playError()
    toast.error(detailMessage(e))
    invalidate()
  }

  const create = useMutation({
    mutationFn: async () =>
      (await PachkaService.createPachka({ path: { order_id: orderId } })).data,
    onMutate: cancel,
    onSuccess: put,
    onError: fail,
  })
  const scan = useMutation({
    mutationFn: async (v: { pachkaId: number; qr: string }) =>
      (
        await PachkaService.scanIntoPachka({
          path: { pachka_id: v.pachkaId },
          body: { qr_text: v.qr },
        })
      ).data,
    onMutate: cancel,
    onSuccess: put,
    onError: (e) => {
      // E008 «allaqachon qadoqda» — ogohlantirish, qizil xato emas (boshqa
      // postlardagi takroriy skan bilan bir)
      if (detailParts(e).code === "E008") playWarning()
      else playError()
      toast.error(detailMessage(e))
      invalidate()
    },
  })
  const remove = useMutation({
    mutationFn: async (v: { pachkaId: number; instanceId: number }) =>
      (
        await PachkaService.removeFromPachka({
          path: { pachka_id: v.pachkaId, instance_id: v.instanceId },
        })
      ).data,
    onMutate: cancel,
    onSuccess: put,
    onError: fail,
  })
  // Yopiq qadoqni tuzatishning YAGONA yo'li: qayta ochib, tuzatib, qayta yakunlash
  // (yakunlash chekni navbatga yangidan qo'yadi).
  const reopen = useMutation({
    mutationFn: async (pachkaId: number) =>
      (await PachkaService.reopenPachka({ path: { pachka_id: pachkaId } }))
        .data,
    onMutate: cancel,
    onSuccess: put,
    onError: fail,
  })
  const close = useMutation({
    mutationFn: async (pachkaId: number) =>
      (await PachkaService.closePachka({ path: { pachka_id: pachkaId } })).data,
    onSuccess: (r) => {
      playSuccess()
      toast.success(r.message)
      invalidate()
    },
    onError: fail,
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

  const pending: UpakovkaPending[] = data?.pending ?? []
  const closed = pachkas.filter((p) => p.status !== "open")
  const packedItems: PachkaItemRow[] = pachkas.flatMap((p) => p.items ?? [])
  const ready = pending.filter((p) => p.ready).length
  const waiting = pending.length - ready
  const total = packedItems.length + pending.length

  // Detal bo'yicha guruh — qadoqlanganlar ham shu ro'yxatda (✓), qadoqlovchi
  // «№3 ni solganmidim?» degan savolga yopiq qadoqlarni ochmay javob oladi
  const groups = new Map<string, Group>()
  const add = (
    code: string,
    name: string,
    inst: Inst | null,
    waitingOne = false,
  ) => {
    let g = groups.get(code)
    if (!g) {
      g = { key: code, name, instances: [], waiting: 0 }
      groups.set(code, g)
    }
    if (inst) g.instances.push(inst)
    if (waitingOne) g.waiting++
  }
  for (const i of packedItems)
    add(i.part_code, i.part_name, {
      instance_id: i.instance_id,
      qr_text: i.qr_text,
      packed: true,
    })
  for (const p of pending)
    add(
      p.part_code,
      p.part_name,
      p.ready
        ? { instance_id: p.instance_id, qr_text: p.qr_text, packed: false }
        : null,
      !p.ready,
    )
  const tier = (g: Group) =>
    g.instances.some((i) => !i.packed) ? 0 : g.instances.length ? 2 : 1
  const rows = [...groups.values()]
    .filter((g) => g.instances.length > 0)
    .map((g) => ({
      ...g,
      instances: [...g.instances].sort(
        (a, b) => instanceNo(a.qr_text) - instanceNo(b.qr_text),
      ),
    }))
    .sort((a, b) => tier(a) - tier(b) || a.key.localeCompare(b.key))

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* CHAP: ochiq qadoq — skan shu yerga tushadi */}
      <div className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
        <PostHeader
          onBack={onBack}
          orderNumber={data?.order_number}
          projectName={data?.project_name}
        >
          <PostProgress
            className="ml-auto"
            done={packedItems.length}
            total={total}
          />
        </PostHeader>

        {!open ? (
          // Tugma ko'z qaragan joyda — sarlavhada o'chiq turgan tugma emas.
          // Tayyor detal bo'lmasa yaratib bo'lmaydi: bo'sh qadoq tuzoq edi
          // (yopib bo'lmaydi, yonida boshqasini ochib bo'lmaydi)
          <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
            <LoadingButton
              className="h-14 px-8 text-lg font-black"
              loading={create.isPending}
              disabled={ready === 0}
              onClick={() => create.mutate()}
            >
              <PackagePlus /> Qadoq yaratish
            </LoadingButton>
            <div className="text-muted-foreground">
              {ready ? (
                <>
                  Qadoqlashga tayyor:{" "}
                  <span className="num font-semibold text-foreground">
                    {ready}
                  </span>{" "}
                  detal
                </>
              ) : waiting ? (
                "Tayyor detal yo'q — hammasi hali tsexda."
              ) : (
                "Hammasi qadoqlangan."
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-3 border-b px-4 py-2">
              <span className="num text-xl font-black">{open.code}</span>
              <span className="text-base">
                <span className="num">{open.items?.length ?? 0}</span> detal
              </span>
              <span className="num ml-auto text-base text-muted-foreground">
                {kg(open.weight_kg)}
              </span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {!open.items?.length ? (
                <div className="p-6 text-center text-muted-foreground">
                  Detalni skanerlang — u shu qadoqqa tushadi.
                </div>
              ) : (
                <table className="w-full text-base">
                  <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
                    <tr>
                      <th className="px-4 py-2.5">Detal ID</th>
                      <th className="px-4 py-2.5">Nomi</th>
                      <th className="px-4 py-2.5">O'lchami</th>
                      <th className="px-4 py-2.5">Og'irligi</th>
                      <th className="px-4 py-2.5" />
                    </tr>
                  </thead>
                  <tbody>
                    {/* Oxirgi skanerlangan TEPADA: 10 qatordan keyin yangi qator
                        ekrandan tashqariga tushib, «qo'shildimi?» ko'rinmasdi */}
                    {[...open.items].reverse().map((i) => (
                      <tr
                        key={i.instance_id}
                        className="border-b last:border-0"
                      >
                        <td className="px-4 py-3 text-lg font-semibold">
                          <Serial code={i.qr_text} />
                        </td>
                        <td className="max-w-[220px] truncate px-4 py-3">
                          {i.part_name}
                        </td>
                        <td className="num whitespace-nowrap px-4 py-3 text-sm">
                          {formatSize(i.length, i.width, i.thickness)}
                        </td>
                        <td className="num whitespace-nowrap px-4 py-3 text-sm text-muted-foreground">
                          {kg(i.weight_kg)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {/* Chiqarish — UPAKOVKA skani ham bekor bo'ladi: qizil */}
                          <Button
                            variant="ghost"
                            className="h-11 w-11 text-destructive hover:bg-destructive/10 hover:text-destructive"
                            aria-label={`${i.qr_text} ni qadoqdan chiqarish`}
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

      {/* O'NG: buyurtma detallari (post navbati naqshi) + yakunlangan qadoqlar */}
      <div className="flex w-[38%] min-w-[300px] flex-col gap-3">
        <div className="flex min-h-0 flex-1 flex-col rounded-xl border bg-white">
          <div className="flex items-baseline justify-between border-b px-4 py-2">
            <span className="text-base font-bold">Detallar</span>
            <span className="text-2xs font-medium text-muted-foreground">
              kulrang — tayyor · ✓ qadoqlangan
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {!rows.length ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                {pending.length
                  ? "Tayyor detal yo'q — hammasi hali tsexda."
                  : "Bu buyurtmada qadoqlanadigan detal yo'q."}
              </div>
            ) : (
              rows.map((g) => {
                const finished = g.instances.every((i) => i.packed)
                return (
                  <div
                    key={g.key}
                    className={cn(
                      "flex items-center gap-3 border-b px-4 py-2 last:border-0",
                      finished && "bg-green-50",
                    )}
                  >
                    <div className="min-w-0 shrink-0">
                      <div className="num font-semibold">{g.key}</div>
                      <div className="max-w-40 truncate text-xs text-muted-foreground">
                        {g.name}
                      </div>
                    </div>
                    <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
                      {g.instances.map((i) => (
                        <InstanceChip
                          key={i.instance_id}
                          qr={i.qr_text}
                          done={i.packed}
                          many={g.instances.length > 1}
                          className="px-2 py-0.5 text-base"
                        />
                      ))}
                      {g.waiting > 0 && (
                        <span
                          className="num text-xs text-muted-foreground"
                          title="Hali oldingi bosqichdan chiqmagan nusxalar"
                        >
                          +{g.waiting} yo'lda
                        </span>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
          {/* YETIB KELMAGAN nusxa chip bo'lmaydi: skan baribir rad etiladi (E004) */}
          {!!waiting && (
            <div className="border-t px-4 py-2 text-sm text-muted-foreground">
              Yana <span className="num font-semibold">{waiting}</span> detal
              tsexda — shu bosqichga yetib kelgach chip bo'lib chiqadi.
            </div>
          )}
        </div>

        <div className="flex max-h-[38%] min-h-0 flex-col rounded-xl border bg-white">
          <div className="border-b px-4 py-2 text-base font-bold">
            Yakunlangan <span className="num">({closed.length})</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {closed.map((p) => (
              <div
                key={p.id}
                className="flex items-baseline gap-2 border-b px-4 py-2 text-sm last:border-0"
              >
                <span className="num font-semibold">{p.code}</span>
                <span className="text-muted-foreground">
                  <span className="num">{p.items?.length ?? 0}</span> detal
                </span>
                <span className="num ml-auto text-muted-foreground">
                  {kg(p.weight_kg)}
                </span>
                {/* Ochiq qadoq borida bloklanadi: buyurtmada bir vaqtda bitta
                    ochiq qadoq bo'ladi (backend ham 409 bilan rad etadi). */}
                <LoadingButton
                  variant="ghost"
                  className="h-11 px-3"
                  loading={reopen.isPending && reopen.variables === p.id}
                  disabled={!!open || reopen.isPending}
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
    </div>
  )
}
