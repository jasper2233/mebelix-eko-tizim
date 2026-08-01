// KROMKA post sahifasi — ikki panel (TZ 7.2):
// chapda arradan chiqqan, kromkasi tugamagan detallar; QR skan (yoki chipni bosish)
// detalni o'ngdagi "tanlanganlar" ro'yxatiga oladi — hech narsa hali yozilmaydi.
// TASDIQLASH bosilgandagina skanlar serverga yoziladi (har tomon = bitta skan).
// Noto'g'ri detal qo'shilib qolsa X bilan chapga qaytariladi — iz qolmaydi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { ScansService, TerminalService } from "@/client"
import { playError, playSuccess } from "@/components/Terminal/audio"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { formatSize } from "@/lib/mes"
import { cn } from "@/lib/utils"

type KInstance = {
  instance_id: number
  instance_no: number
  qr_text: string
  done: number
  arra_passed: boolean
}
type KPart = {
  part_id: number
  code: string
  name: string
  length: number | null
  width: number | null
  thickness: number | null
  sides: number
  edges: Record<string, unknown>
  total_done: number
  total_required: number
  instances: KInstance[]
}

// GibLab qirra kalitlari — kromkachi tiliga (yorliqdagi bilan bir xil qisqartma)
const SIDE_LABELS: Record<string, string> = {
  l: "Chap",
  r: "O'ng",
  t: "Tepa",
  b: "Past",
}

export function KromkaView({
  orderId,
  onBack,
  registerScan,
  initialQr,
  onInitialQrApplied,
}: {
  orderId: number
  onBack: () => void
  /** Terminal skan inputi KROMKA rejimida QR'ni shu yerga uzatadi.
   * false qaytsa — QR bu proyektda topilmadi (terminal xato ko'rsatadi). */
  registerScan?: (fn: ((qr: string) => boolean) | null) => void
  /** Picker'da skan qilingan QR — sahifa ochilgach avtomatik tanlanadi */
  initialQr?: string | null
  onInitialQrApplied?: () => void
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data, isLoading } = useQuery({
    queryKey: ["terminal", "kromka", orderId],
    queryFn: () => TerminalService.readTerminalKromka({ orderId }),
    refetchInterval: 30_000,
  })
  // qr_text -> tanlangan (hali yozilmagan) tomonlar soni
  const [staged, setStaged] = useState<Record<string, number>>({})

  const parts = (data?.parts ?? []) as KPart[]

  // Skan handleri har renderda yangi data ko'radi, lekin terminal ro'yxatdan
  // bir marta o'tkazadi — shu uchun ref orqali
  const stageRef = useRef<(qr: string) => boolean>(() => false)
  stageRef.current = (qr: string): boolean => {
    for (const p of parts) {
      const inst = p.instances.find((i) => i.qr_text === qr)
      if (!inst) continue
      if (!inst.arra_passed) {
        playError()
        showErrorToast("Bu detal hali arradan chiqmagan.")
        return true
      }
      const pending = staged[qr] ?? 0
      if (inst.done + pending >= p.sides) {
        playError()
        showErrorToast(
          pending > 0
            ? "Bu detalning hamma tomoni allaqachon tanlangan."
            : "Bu detalning kromkasi allaqachon tugagan.",
        )
        return true
      }
      playSuccess()
      setStaged((prev) => ({ ...prev, [qr]: pending + 1 }))
      return true
    }
    return false
  }
  useEffect(() => {
    registerScan?.((qr) => stageRef.current(qr))
    return () => registerScan?.(null)
  }, [registerScan])

  // Picker'dan kelgan QR: ma'lumot yuklangach BIR MARTA tanlanadi
  const initApplied = useRef(false)
  useEffect(() => {
    if (!initialQr || !data || initApplied.current) return
    initApplied.current = true
    stageRef.current(initialQr)
    onInitialQrApplied?.()
  }, [initialQr, data, onInitialQrApplied])

  const confirmMutation = useMutation({
    mutationFn: async () => {
      // Har tomon = bitta skan yozuvi (mavjud /scans oqimi, backend o'zgarmagan)
      let ok = 0
      let fail = 0
      for (const [qr, n] of Object.entries(staged)) {
        for (let k = 0; k < n; k++) {
          try {
            await ScansService.recordScan({
              requestBody: {
                qr_text: qr,
                client_event_id: crypto.randomUUID(),
              },
            })
            ok++
          } catch {
            fail++
          }
        }
      }
      return { ok, fail }
    },
    onSuccess: ({ ok, fail }) => {
      if (ok) {
        playSuccess()
        showSuccessToast(`${ok} tomon tasdiqlandi`)
      }
      if (fail) {
        playError()
        showErrorToast(
          `${fail} tomon yozilmadi — ro'yxat yangilandi, qayta urining.`,
        )
      }
      setStaged({})
      queryClient.invalidateQueries({ queryKey: ["terminal"] })
    },
  })

  if (isLoading) return <Skeleton className="h-full w-full" />

  // Chap ro'yxat: faqat arradan chiqqan va kromkasi TUGAMAGAN nusxalar.
  // Tugamaguncha ro'yxatda qoladi (tanlangani ham ko'rinib turadi).
  const leftParts = parts
    .map((p) => ({
      ...p,
      instances: p.instances.filter((i) => i.arra_passed && i.done < p.sides),
    }))
    .filter((p) => p.instances.length > 0)
    .sort((a, b) => a.code.localeCompare(b.code))

  const stagedRows = Object.entries(staged)
    .map(([qr, n]) => {
      for (const p of parts) {
        const inst = p.instances.find((i) => i.qr_text === qr)
        if (inst) return { qr, n, part: p, inst }
      }
      return null
    })
    .filter(Boolean) as Array<{
    qr: string
    n: number
    part: KPart
    inst: KInstance
  }>
  const stagedTotal = stagedRows.reduce((s, r) => s + r.n, 0)

  const totDone = parts.reduce((s, p) => s + p.total_done, 0)
  const totReq = parts.reduce((s, p) => s + p.total_required, 0)

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* CHAP: arradan kelgan, kromkasi tugamagan detallar */}
      <div className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
        <div className="flex items-center gap-3 border-b px-4 py-2">
          <Button
            variant="outline"
            className="h-12 px-4 text-base font-bold"
            onClick={onBack}
          >
            <ArrowLeft /> Orqaga
          </Button>
          <div className="text-lg font-black">{data?.order_number}</div>
          <div className="num ml-auto text-base">
            Tomonlar: <b>{totDone}</b>/<b>{totReq}</b>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <table className="w-full text-base">
            <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <th className="px-4 py-2.5">Kod</th>
                <th className="px-4 py-2.5">Nomi</th>
                <th className="px-4 py-2.5">O'lchami</th>
                <th className="px-4 py-2.5">Kromka</th>
                <th className="px-4 py-2.5 text-right">Holat</th>
              </tr>
            </thead>
            <tbody>
              {leftParts.map((p) => (
                <tr key={p.part_id} className="border-b last:border-0">
                  <td className="num px-4 py-3 font-semibold">{p.code}</td>
                  <td className="max-w-[200px] truncate px-4 py-3">{p.name}</td>
                  <td className="num whitespace-nowrap px-4 py-3 text-sm">
                    {formatSize(p.length, p.width, p.thickness)}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <b>{p.sides} tomon</b>
                    <span className="ml-1.5 text-muted-foreground">
                      {Object.keys(p.edges)
                        .map((k) => SIDE_LABELS[k] ?? k)
                        .join(", ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {/* Chip bosilsa ham tanlanadi — QR o'qilmay qolgan holat uchun */}
                    <div className="flex flex-wrap items-center justify-end gap-1.5">
                      {p.instances.map((i) => {
                        const pending = staged[i.qr_text] ?? 0
                        return (
                          <button
                            type="button"
                            key={i.instance_id}
                            title={i.qr_text}
                            onClick={() => stageRef.current(i.qr_text)}
                            className={cn(
                              "num rounded-md px-2.5 py-1.5 text-lg font-black transition-all active:scale-95",
                              pending > 0
                                ? "bg-amber-500 text-white"
                                : i.done > 0
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-primary/10 text-primary",
                            )}
                          >
                            {p.instances.length > 1 && (
                              <span className="mr-1 text-xs font-bold opacity-70">
                                №{i.instance_no}
                              </span>
                            )}
                            {i.done}/{p.sides}
                            {pending > 0 && (
                              <span className="ml-1 text-sm">+{pending}</span>
                            )}
                          </button>
                        )
                      })}
                    </div>
                  </td>
                </tr>
              ))}
              {!leftParts.length && (
                <tr>
                  <td
                    colSpan={5}
                    className="h-32 text-center text-muted-foreground"
                  >
                    Arradan kelgan detal yo'q — hammasi tugagan yoki hali
                    kesilmagan
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* O'NG: tanlanganlar + TASDIQLASH */}
      <div className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
        <div className="border-b px-4 py-3 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Tanlanganlar{" "}
          {stagedTotal > 0 && (
            <span className="num ml-1 rounded-sm bg-primary/10 px-1.5 py-0.5 text-primary">
              {stagedTotal} tomon
            </span>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {stagedRows.map((r) => (
            <div
              key={r.qr}
              className="flex items-center gap-2 border-b px-3 py-2.5 last:border-0"
            >
              <div className="min-w-0 flex-1">
                <div className="num truncate font-semibold">{r.part.code}</div>
                <div className="truncate text-xs text-muted-foreground">
                  {r.part.name}
                  {r.part.instances.length > 1 && ` · №${r.inst.instance_no}`}
                </div>
              </div>
              <span className="num shrink-0 rounded-md bg-amber-100 px-2.5 py-1 text-base font-black text-amber-700">
                +{r.n}
              </span>
              {/* Noto'g'ri skan: hech narsa yozilmagan — shunchaki chapga qaytadi */}
              <Button
                variant="outline"
                size="icon"
                className="size-11 shrink-0 text-destructive hover:bg-destructive/10"
                title="Bekor qilish — chapga qaytarish"
                onClick={() => setStaged(({ [r.qr]: _, ...rest }) => rest)}
              >
                <X />
              </Button>
            </div>
          ))}
          {!stagedRows.length && (
            <p className="p-4 text-sm text-muted-foreground">
              QR skan qiling yoki chapdagi detalni bosing — shu yerga
              qo'shiladi. Tasdiqlamaguncha hech narsa yozilmaydi.
            </p>
          )}
        </div>
        <div className="border-t p-3">
          <LoadingButton
            className="h-16 w-full bg-green-600 text-lg font-black hover:bg-green-700"
            disabled={stagedTotal === 0}
            loading={confirmMutation.isPending}
            onClick={() => confirmMutation.mutate()}
          >
            TASDIQLASH{stagedTotal > 0 ? ` — ${stagedTotal} tomon` : ""}
          </LoadingButton>
        </div>
      </div>
    </div>
  )
}
