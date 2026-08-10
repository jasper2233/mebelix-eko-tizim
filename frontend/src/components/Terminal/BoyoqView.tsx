// BOYOQ post sahifasi: proyekt tanlangach bo'yashga kelgan NUSXALAR ro'yxati.
//
// Umumiy "Navbatdagi vazifalar" detal darajasida agregat berardi ("qoldiq 6/6") —
// bo'yoqchi oltita eshikning qaysi biri bo'yalganini undan bilolmasdi. Bu yerda
// har nusxa alohida qator, skan qilinganda ro'yxatdan chiqadi.

import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, Check } from "lucide-react"

import { TerminalService } from "@/client"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatSize } from "@/lib/mes"
import { cn } from "@/lib/utils"

export function BoyoqView({
  orderId,
  onBack,
}: {
  orderId: number
  onBack: () => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["terminal", "queue", orderId],
    queryFn: () => TerminalService.readTerminalPostQueue({ orderId }),
    refetchInterval: 30_000,
  })

  if (isLoading) return <Skeleton className="h-full w-full" />

  const rows = data?.rows ?? []
  const ready = rows.filter((r) => !r.done && r.ready)
  const waiting = rows.filter((r) => !r.done && !r.ready)
  const done = rows.filter((r) => r.done)

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
        <div className="num ml-auto text-base">
          Bo'yalgan: <b>{done.length}</b>/{rows.length}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="border-b px-4 py-2 text-base font-bold">
          Bo'yashga kelgan <span className="num">({ready.length})</span>
        </div>
        {!ready.length ? (
          <div className="p-6 text-center text-muted-foreground">
            {rows.length
              ? "Bo'yashga tayyor detal yo'q."
              : "Bu proyektda bo'yaladigan detal yo'q."}
          </div>
        ) : (
          <table className="w-full text-base">
            <tbody>
              {ready.map((r) => (
                <tr key={r.instance_id} className="border-b last:border-0">
                  <td className="num px-4 py-3 text-lg font-black">
                    {r.qr_text}
                  </td>
                  <td className="max-w-[260px] px-4 py-3">
                    <div className="truncate">{r.part_name}</div>
                    {/* Bo'yoqchi uchun material = RANG */}
                    {r.material && (
                      <div className="truncate text-sm font-semibold text-amber-800">
                        {r.material}
                      </div>
                    )}
                    {r.note && (
                      <div className="truncate text-sm text-muted-foreground">
                        {r.note}
                      </div>
                    )}
                    {!!r.assembly?.length && (
                      <div className="num text-sm font-semibold text-blue-800">
                        + {r.assembly.join(", ")}
                      </div>
                    )}
                  </td>
                  <td className="num whitespace-nowrap px-4 py-3 text-sm">
                    {formatSize(r.length, r.width, r.thickness)}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-muted-foreground">
                    {r.stage}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Hali kelmaganlar: ishi TUGAGAN post yoziladi — qayerda turgani ko'rinsin */}
        {!!waiting.length && (
          <>
            <div className="border-y bg-muted/40 px-4 py-2 text-sm font-bold text-muted-foreground">
              Sexda <span className="num">({waiting.length})</span>
            </div>
            <table className="w-full text-sm text-muted-foreground">
              <tbody>
                {waiting.map((r) => (
                  <tr key={r.instance_id} className="border-b last:border-0">
                    <td className="num px-4 py-1.5">{r.qr_text}</td>
                    <td className="max-w-[260px] truncate px-4 py-1.5">
                      {r.part_name}
                    </td>
                    <td className="px-4 py-1.5 text-right font-semibold text-amber-700">
                      {r.stage || "hali kesilmagan"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {!!done.length && (
          <>
            <div className="border-y bg-muted/40 px-4 py-2 text-sm font-bold text-muted-foreground">
              Bo'yalgan <span className="num">({done.length})</span>
            </div>
            <table className="w-full text-sm">
              <tbody>
                {done.map((r) => (
                  <tr
                    key={r.instance_id}
                    className={cn("border-b text-green-700 last:border-0")}
                  >
                    <td className="num px-4 py-1.5 font-semibold">
                      {r.qr_text}
                    </td>
                    <td className="max-w-[260px] truncate px-4 py-1.5">
                      {r.part_name}
                    </td>
                    <td className="px-4 py-1.5 text-right">
                      <Check className="ml-auto size-4" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}
