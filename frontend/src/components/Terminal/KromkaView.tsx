// KROMKA post sahifasi: proyekt detallari — faqat kromkali detallar, har nusxada
// tomon-progress (0/4 → 4/4, har QR skan +1) va arradan o'tganlik holati.

import { useQuery } from "@tanstack/react-query"
import { ArrowLeft } from "lucide-react"

import { TerminalService } from "@/client"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
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
}: {
  orderId: number
  onBack: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["terminal", "kromka", orderId],
    queryFn: () => TerminalService.readTerminalKromka({ orderId }),
    refetchInterval: 30_000,
  })

  if (isLoading) return <Skeleton className="h-full w-full" />

  const parts = ((data?.parts ?? []) as KPart[]).slice().sort((a, b) => {
    // Tugaganlar pastda; qolganlardan arradan kelganlari tepada (ish shu yerda)
    const fin = (p: KPart) => (p.total_done >= p.total_required ? 1 : 0)
    const cut = (p: KPart) => (p.instances.some((i) => i.arra_passed) ? 0 : 1)
    return fin(a) - fin(b) || cut(a) - cut(b) || a.code.localeCompare(b.code)
  })
  const totDone = parts.reduce((s, p) => s + p.total_done, 0)
  const totReq = parts.reduce((s, p) => s + p.total_required, 0)

  return (
    <div className="flex h-full flex-col rounded-xl border bg-white">
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
              <th className="px-4 py-2.5">Arra</th>
              <th className="px-4 py-2.5 text-right">Bajarildi</th>
            </tr>
          </thead>
          <tbody>
            {parts.map((p) => {
              const finished = p.total_done >= p.total_required
              const anyCut = p.instances.some((i) => i.arra_passed)
              return (
                <tr
                  key={p.part_id}
                  className={cn(
                    "border-b last:border-0",
                    finished && "bg-green-50/60 text-muted-foreground",
                    !finished && !anyCut && "opacity-50",
                  )}
                >
                  <td className="num px-4 py-3 font-semibold">{p.code}</td>
                  <td className="max-w-[220px] truncate px-4 py-3">{p.name}</td>
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
                  <td className="px-4 py-3">
                    {finished ? null : anyCut ? (
                      <span className="rounded-sm bg-green-100 px-2 py-0.5 text-xs font-bold text-green-700">
                        ARRADAN O'TDI
                      </span>
                    ) : (
                      <span className="rounded-sm bg-muted px-2 py-0.5 text-xs font-bold text-muted-foreground">
                        KESILMAGAN
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {/* Har nusxa alohida chip: №nusxa done/tomonlar — skan sayin +1 */}
                    <div className="flex flex-wrap items-center justify-end gap-1.5">
                      {p.instances.map((i) => (
                        <span
                          key={i.instance_id}
                          title={i.qr_text}
                          className={cn(
                            "num rounded-md px-2.5 py-1 text-lg font-black",
                            i.done >= p.sides
                              ? "bg-green-600 text-white"
                              : i.done > 0
                                ? "bg-amber-100 text-amber-700"
                                : i.arra_passed
                                  ? "bg-primary/10 text-primary"
                                  : "bg-muted text-muted-foreground",
                          )}
                        >
                          {p.instances.length > 1 && (
                            <span className="mr-1 text-xs font-bold opacity-60">
                              №{i.instance_no}
                            </span>
                          )}
                          {i.done >= p.sides ? "✓" : `${i.done}/${p.sides}`}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              )
            })}
            {!parts.length && (
              <tr>
                <td
                  colSpan={6}
                  className="h-32 text-center text-muted-foreground"
                >
                  Bu buyurtmada kromkali detallar yo'q
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
