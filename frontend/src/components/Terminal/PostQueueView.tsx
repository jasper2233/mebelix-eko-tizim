// Post navbati sahifasi (BOYOQ, STOLYARKA): proyekt tanlangach shu postga
// YETIB KELGAN nusxalar ro'yxati.
//
// Umumiy "Navbatdagi vazifalar" detal darajasida agregat berardi ("qoldiq 6/6")
// va navbatni hisobga olmasdi: operator hali arradan chiqmagan detalni ko'rib,
// skanerlab E004 olardi. Bu yerda har nusxa alohida qator va faqat bajarish
// mumkin bo'lganlari chiqadi; skan qilinganda qator "Bajarilgan" ga o'tadi.

import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, Check } from "lucide-react"

import { TerminalService } from "@/client"
import { OperationChips } from "@/components/Common/OperationChips"
import { PostProgress } from "@/components/Terminal/PostProgress"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatSize } from "@/lib/mes"
import { cn } from "@/lib/utils"

//: Post nomiga moslangan sarlavhalar — "bo'yalgan" stolyarkada mos kelmaydi.
const LABELS: Record<string, { ready: string; done: string }> = {
  BOYOQ: { ready: "Bo'yashga kelgan", done: "Bo'yalgan" },
  STOLYARKA: { ready: "Stolyarkaga kelgan", done: "Bajarilgan" },
}

export function PostQueueView({
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
  const label = LABELS[data?.post_code ?? ""] ?? {
    ready: "Ishga tayyor",
    done: "Bajarilgan",
  }

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
          done={done.length}
          total={rows.length}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="border-b px-4 py-2 text-base font-bold">
          {label.ready} <span className="num">({ready.length})</span>
        </div>
        {!ready.length ? (
          <div className="p-6 text-center text-muted-foreground">
            {rows.length
              ? "Bu postga yetib kelgan detal yo'q."
              : "Bu proyektda bu postga tegishli detal yo'q."}
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
                    {/* Bitta postda bir nechta amal bor (stolyarkada olti xil) */}
                    <OperationChips
                      processCode={r.process_code}
                      postCode={data?.post_code}
                    />
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

        {/* YETIB KELMAGAN detal ro'yxatda ko'rsatilmaydi: uni skanerlab
            bo'lmaydi (E004) va operator uni izlab vaqt yo'qotardi. Faqat nechta
            detal yo'lda ekani yoziladi. */}
        {!!waiting.length && (
          <div className="border-t px-4 py-2 text-sm text-muted-foreground">
            Yana <span className="num font-semibold">{waiting.length}</span>{" "}
            detal sexda — shu bosqichga yetib kelgach ro'yxatda chiqadi.
          </div>
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
