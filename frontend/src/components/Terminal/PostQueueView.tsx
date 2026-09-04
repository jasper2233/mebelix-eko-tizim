// Post navbati sahifasi (BOYOQ, STOLYARKA): proyekt tanlangach shu postga
// YETIB KELGAN nusxalar — DETAL bo'yicha guruhlab, nusxalar chip sifatida.
//
// Umumiy "Navbatdagi vazifalar" detal darajasida agregat berardi ("qoldiq 6/6")
// va navbatni hisobga olmasdi: operator hali arradan chiqmagan detalni ko'rib,
// skanerlab E004 olardi. Keyin har nusxa alohida qator bo'ldi — lekin 16 ta
// bir xil «01_001 tom · Utalshonka · LDSP · +yig'ma» qatori 2 ekran bo'lib
// ketardi (stolyarkada bitta detalning 16 nusxasi). Endi Kromka bilan bir
// naqsh: bitta detal = bitta qator, nusxalar №1…№16 chip (kulrang — navbatda,
// yashil ✓ — bajarildi); faqat bajarish mumkin bo'lganlari chip bo'ladi.

import { useQuery } from "@tanstack/react-query"

import type { PostQueueRow } from "@/client"
import { TerminalService } from "@/client"
import { OperationChips } from "@/components/Common/OperationChips"
import { QueryError } from "@/components/Common/QueryError"
import { PostHeader } from "@/components/Terminal/PostHeader"
import { PostProgress } from "@/components/Terminal/PostProgress"
import { Skeleton } from "@/components/ui/skeleton"
import { formatSize } from "@/lib/mes"
import { cn } from "@/lib/utils"

//: Post nomiga moslangan sarlavhalar — "bo'yalgan" stolyarkada mos kelmaydi.
const LABELS: Record<string, { ready: string; done: string }> = {
  BOYOQ: { ready: "Bo'yashga kelgan", done: "Bo'yalgan" },
  STOLYARKA: { ready: "Stolyarkaga kelgan", done: "Bajarilgan" },
}

/** Nusxa raqami — chekdagi ID dumi (`…_01_001_10` → 10); dumsiz yagona nusxa → 1 */
const instanceNo = (qr: string): number => {
  const m = /_(\d+)$/.exec(qr)
  return m ? Number(m[1]) : 1
}

type Group = {
  key: string
  first: PostQueueRow
  instances: PostQueueRow[] // ready yoki done — chip bo'ladiganlar, raqam bo'yicha
  waiting: number // hali yetib kelmagan nusxalar (chip yo'q)
}

export function PostQueueView({
  orderId,
  onBack,
}: {
  orderId: number
  onBack: () => void
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["terminal", "queue", orderId],
    queryFn: async () =>
      (
        await TerminalService.readTerminalPostQueue({
          path: { order_id: orderId },
        })
      ).data,
    refetchInterval: 30_000,
  })

  if (isLoading) return <Skeleton className="h-full w-full" />
  // Xato JIM yutilmasin: busiz `rows` bo'sh qolib, operator "Bu proyektda bu
  // postga tegishli detal yo'q." ni o'qib postni ishsiz deb tashlab ketardi.
  if (isError) return <QueryError onRetry={() => refetch()} />

  const rows = data?.rows ?? []
  const label = LABELS[data?.post_code ?? ""] ?? {
    ready: "Ishga tayyor",
    done: "Bajarilgan",
  }

  // Detal bo'yicha guruh: bir detal ikki xil amal bilan kelishi mumkin
  // (stolyarkada) — kalitga amal kodi ham kiradi
  const groups = new Map<string, Group>()
  for (const r of rows) {
    const key = `${r.part_code}|${r.process_code}`
    let g = groups.get(key)
    if (!g) {
      g = { key, first: r, instances: [], waiting: 0 }
      groups.set(key, g)
    }
    if (r.done || r.ready) g.instances.push(r)
    else g.waiting++
  }
  const doneTotal = rows.filter((r) => r.done).length
  const waitingTotal = rows.filter((r) => !r.done && !r.ready).length
  // Tartib: ishi bor (navbatda nusxa) detallar tepada, tugaganlari pastda yashil
  const tier = (g: Group) =>
    g.instances.some((i) => !i.done) ? 0 : g.instances.length ? 2 : 1
  const sorted = [...groups.values()]
    .filter((g) => g.instances.length > 0)
    .map((g) => ({
      ...g,
      instances: [...g.instances].sort(
        (a, b) => instanceNo(a.qr_text) - instanceNo(b.qr_text),
      ),
    }))
    .sort((a, b) => tier(a) - tier(b) || a.key.localeCompare(b.key))

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border bg-white">
      <PostHeader
        onBack={onBack}
        orderNumber={data?.order_number}
        projectName={data?.project_name}
      >
        <PostProgress
          className="ml-auto"
          done={doneTotal}
          total={rows.length}
        />
      </PostHeader>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!sorted.length ? (
          <div className="p-6 text-center text-muted-foreground">
            {rows.length
              ? "Bu postga yetib kelgan detal yo'q."
              : "Bu proyektda bu postga tegishli detal yo'q."}
          </div>
        ) : (
          <table className="w-full text-base">
            {/* Sarlavha lug'ati hamma postda bir xil: «Kod» = detal turi,
                nusxalar chipda (chek ID dumi = raqam) */}
            <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <th className="px-4 py-2.5">Kod</th>
                <th className="px-4 py-2.5">Nomi</th>
                <th className="px-4 py-2.5">O'lchami</th>
                {/* Detal hozir qaysi postda turibdi — o'sha yerdan olinadi.
                    «Qayerda» emas, «Qayerdan olish»: ustun amalni aytsin */}
                <th className="whitespace-nowrap px-4 py-2.5">
                  Qayerdan olish
                </th>
                <th className="px-4 py-2.5 text-right">
                  Nusxalar
                  <span className="block whitespace-nowrap text-2xs font-medium normal-case tracking-normal">
                    kulrang — navbatda · ✓ {label.done.toLowerCase()}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((g) => {
                const r = g.first
                const doneN = g.instances.filter((i) => i.done).length
                const finished = doneN === g.instances.length
                return (
                  <tr
                    key={g.key}
                    className={cn(
                      "border-b last:border-0",
                      finished && "bg-green-50",
                    )}
                  >
                    <td className="num whitespace-nowrap px-4 py-3 font-semibold">
                      {r.part_code}
                    </td>
                    <td className="max-w-[360px] px-4 py-3">
                      <div className="truncate">{r.part_name}</div>
                      {/* Bitta postda bir nechta amal bor (stolyarkada olti xil) */}
                      <OperationChips
                        processCode={r.process_code}
                        postCode={data?.post_code}
                      />
                      {/* Har qator YORLIQLI: sariq/ko'k matn yolg'iz o'zi nima
                          ekanini aytmasdi (material? yig'ma?). Bo'yoqchi uchun
                          material = RANG. */}
                      {r.material && (
                        <div className="truncate text-sm">
                          <span className="text-muted-foreground">
                            Material:{" "}
                          </span>
                          <span className="font-semibold text-amber-800">
                            {r.material}
                          </span>
                        </div>
                      )}
                      {r.note && (
                        <div className="truncate text-sm">
                          <span className="text-muted-foreground">Izoh: </span>
                          {r.note}
                        </div>
                      )}
                      {/* Yig'ma ro'yxati KESILMAYDI — stolyar aynan shuni o'qiydi
                          (qaysi mayda detallar bilan yig'iladi) */}
                      {!!r.assembly?.length && (
                        <div className="num text-sm">
                          <span className="text-muted-foreground">
                            Yig'ma:{" "}
                          </span>
                          <span className="font-semibold text-blue-800">
                            {r.assembly.join(", ")}
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="num whitespace-nowrap px-4 py-3 text-sm">
                      {formatSize(r.length, r.width, r.thickness)}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {r.stage}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center justify-end gap-1.5">
                        {g.instances.map((i) => (
                          <span
                            key={i.instance_id}
                            title={i.qr_text}
                            className={cn(
                              "num rounded-md px-2.5 py-1 text-lg font-black",
                              i.done
                                ? "bg-green-600 text-white"
                                : "bg-muted text-muted-foreground",
                            )}
                          >
                            {g.instances.length > 1 && (
                              <span className="mr-1 text-xs font-bold opacity-70">
                                №{instanceNo(i.qr_text)}
                              </span>
                            )}
                            {i.done ? "✓" : "–"}
                          </span>
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
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {/* YETIB KELMAGAN nusxa chip bo'lmaydi: uni skanerlab bo'lmaydi (E004)
            va operator uni izlab vaqt yo'qotardi. Faqat nechta yo'lda ekani. */}
        {!!waitingTotal && (
          <div className="border-t px-4 py-2 text-sm text-muted-foreground">
            Yana <span className="num font-semibold">{waitingTotal}</span> detal
            tsexda — shu bosqichga yetib kelgach chip bo'lib chiqadi.
          </div>
        )}
      </div>
    </div>
  )
}
