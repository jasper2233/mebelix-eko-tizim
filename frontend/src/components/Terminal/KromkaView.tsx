// KROMKA post sahifasi — bitta to'liq kenglikdagi jadval: arradan chiqqan
// kromkali detallar, har skan darhol yoziladi. Jarayondagi (2+ tomonli, bir
// tomoni skan qilingan, tugamagan) qatorlar TEPADA sariq fonda, tugaganlari
// pastda yashil; sarlavhada «Jarayonda N». Xato skan BEKOR QILISH (60s) bilan
// qaytariladi.

import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef } from "react"

import { TerminalService } from "@/client"
import { OperationChips } from "@/components/Common/OperationChips"
import { QueryError } from "@/components/Common/QueryError"
import { PostHeader } from "@/components/Terminal/PostHeader"
import { PostProgress } from "@/components/Terminal/PostProgress"
import { Skeleton } from "@/components/ui/skeleton"
import { useScanFlash } from "@/hooks/useScanFlash"
import { formatSize } from "@/lib/mes"
import { cn } from "@/lib/utils"

/** Qaysi tomonlarga kromka — CHEKDAGI eskiz bilan bir xil konvensiya
 *  (labels.py `burilgan`): uzun tomon `length` bo'lsa eskiz 90° burilgan,
 *  ya'ni t→chap, b→o'ng, l→past, r→tepa; aks holda tabiiy (l→chap, r→o'ng,
 *  t→tepa, b→past). Kromkachi chekdagi rasm bilan solishtiradi — bu yerda
 *  boshqa yo'nalish chalg'itardi. */
function EdgeGlyph({
  edges,
  length,
  width,
  paz = [],
}: {
  edges: Record<string, unknown>
  length: number | null | undefined
  width: number | null | undefined
  /** Paz/freza ketadigan qirralar — chekdagi uzuq chiziq bilan bir xil manba */
  paz?: string[]
}) {
  const burilgan = (length ?? 0) > (width ?? 0)
  const has = (k: string) => !!edges[k]
  const joy = (k: string) =>
    burilgan
      ? { t: "chap", b: "ong", l: "past", r: "tepa" }[k]
      : { l: "chap", r: "ong", t: "tepa", b: "past" }[k]
  const side = burilgan
    ? { chap: has("t"), ong: has("b"), past: has("l"), tepa: has("r") }
    : { chap: has("l"), ong: has("r"), tepa: has("t"), past: has("b") }
  const pazJoy = new Set(paz.map(joy))
  // Chekdagi kabi eskiz DOIM tik: uzun tomon vertikal, eni nisbatga qarab
  // (labels.py: `bh = area_h; bw = bh * short/long`). `burilgan` faqat qaysi
  // qirra qaysi tomonga tushishini hal qiladi, shaklni emas.
  const long = Math.max(length ?? 0, width ?? 0)
  const short = Math.min(length ?? 0, width ?? 0)
  const h = 26
  const w = long > 0 ? Math.max(8, Math.round((h * short) / long)) : 18
  const x = (30 - w) / 2
  const y = (30 - h) / 2
  const line = "stroke-amber-600"
  const pazLine = "stroke-sky-700 [stroke-dasharray:3_2]"
  return (
    <svg viewBox="0 0 30 30" className="size-7 shrink-0" aria-hidden="true">
      <title>Kromka tomonlari</title>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        className="fill-muted stroke-muted-foreground/50"
        strokeWidth="1"
      />
      {side.tepa && (
        <line
          x1={x}
          y1={y}
          x2={x + w}
          y2={y}
          className={line}
          strokeWidth="3"
        />
      )}
      {side.past && (
        <line
          x1={x}
          y1={y + h}
          x2={x + w}
          y2={y + h}
          className={line}
          strokeWidth="3"
        />
      )}
      {side.chap && (
        <line
          x1={x}
          y1={y}
          x2={x}
          y2={y + h}
          className={line}
          strokeWidth="3"
        />
      )}
      {side.ong && (
        <line
          x1={x + w}
          y1={y}
          x2={x + w}
          y2={y + h}
          className={line}
          strokeWidth="3"
        />
      )}
      {/* Paz/freza — chekdagidek kontur ICHIDA uzuq chiziq (kromka esa chekkada,
          tutash). Tomon nomi yozilmaydi: eskiz o'lchamga qarab buriladi. */}
      {pazJoy.has("tepa") && (
        <line
          x1={x + 2}
          y1={y + 3}
          x2={x + w - 2}
          y2={y + 3}
          className={pazLine}
        />
      )}
      {pazJoy.has("past") && (
        <line
          x1={x + 2}
          y1={y + h - 3}
          x2={x + w - 2}
          y2={y + h - 3}
          className={pazLine}
        />
      )}
      {pazJoy.has("chap") && (
        <line
          x1={x + 3}
          y1={y + 2}
          x2={x + 3}
          y2={y + h - 2}
          className={pazLine}
        />
      )}
      {pazJoy.has("ong") && (
        <line
          x1={x + w - 3}
          y1={y + 2}
          x2={x + w - 3}
          y2={y + h - 2}
          className={pazLine}
        />
      )}
    </svg>
  )
}

// Kromka lentalari — yorliqdagi GibLab EL harfi VA lenta nomi: "A — 1-19 kashmir".
// Yolg'iz harf tsexda tushunarsiz edi (operator uni tomonlar TARTIBI deb o'ylagan,
// 2026-09-12) — harf lenta TURINI bildiradi, tartibni emas: tomonlar istalgan
// ketma-ketlikda skanlanadi. Tomon NOMI ("Chap") ataylab yo'q: eskiz uzun tomonni
// vertikal chizadi, l/r/t/b joyi o'lchamga qarab almashadi (labels.py `burilgan`).
const edgeBands = (edges: Record<string, unknown>): string => {
  const juft = new Map<string, string>()
  for (const e of Object.values(edges)) {
    const q = e as { symbol?: string | null; mat?: string | null } | null
    if (!q) continue
    const sym = q.symbol || "\u2022"
    if (!juft.has(sym)) juft.set(sym, (q.mat || "").trim())
  }
  return [...juft]
    .map(([sym, mat]) => (mat ? `${sym} — ${mat}` : sym))
    .join(" · ")
}

export function KromkaView({
  orderId,
  onBack,
  registerScan,
  oval = false,
}: {
  orderId: number
  onBack: () => void
  /** Skan oldidan tekshiruv: null = yozish mumkin, "NOTFOUND" = bu proyektda
   * yo'q, boshqa string = foydalanuvchiga ko'rsatiladigan xato. */
  registerScan?: (fn: ((qr: string) => string | null) | null) => void
  /** OVAL post: har detal 1 skan — Jarayonda paneli va tomonlar ustuni ortiqcha */
  oval?: boolean
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["terminal", "kromka", orderId],
    queryFn: async () =>
      (
        await TerminalService.readTerminalKromka({
          path: { order_id: orderId },
        })
      ).data,
    refetchInterval: 30_000,
  })

  // KromkaPartRow'da edges/instances sxemada ixtiyoriy — bir joyda normallashtiramiz,
  // quyida hamma joyda oddiy massiv/obyekt sifatida ishlatiladi
  const parts = (data?.parts ?? []).map((p) => ({
    ...p,
    edges: p.edges ?? {},
    instances: p.instances ?? [],
  }))

  // Tekshiruv har renderda yangi data ko'radi, terminal esa bir marta ro'yxatga oladi
  const checkRef = useRef<(qr: string) => string | null>(() => "NOTFOUND")
  checkRef.current = (qr: string): string | null => {
    // Aynan moslik — eski `_1` fallback olib tashlandi (backend bilan bir).
    // Detal KROMKA'dan ikki marta o'tishi mumkin ([3,6,3]) — har qadamga alohida qator. Qadamlardan
    // bittasi ochiq bo'lsa skan haqli; birinchi topilgan qatorga qarab hukm chiqarib bo'lmaydi.
    const rows = parts.flatMap((p) => {
      const inst = p.instances.find((i) => i.qr_text === qr)
      return inst ? [{ p, inst }] : []
    })
    if (!rows.length) return "NOTFOUND"
    if (!rows.some(({ inst }) => inst.arra_passed))
      return "Bu detal hali arradan chiqmagan."
    if (rows.some(({ p, inst }) => inst.done < p.sides)) return null
    return oval
      ? "Bu detalning oval kromkasi allaqachon tugagan."
      : "Bu detalning kromkasi allaqachon tugagan."
  }
  useEffect(() => {
    registerScan?.((qr) => checkRef.current(qr))
    return () => registerScan?.(null)
  }, [registerScan])

  // Oxirgi skan bo'lgan detal qatori keyingi skangacha ajralib turadi + avto-scroll
  const flashId = useScanFlash(
    parts,
    (p) => p.route_id,
    (p) => p.instances.reduce((s, i) => s + i.done, 0),
    "kv-row-",
  )

  if (isLoading) return <Skeleton className="h-full w-full" />
  // Xato JIM yutilmasin: busiz `data` undefined qolib, ro'yxat "Arradan kelgan
  // detal yo'q" bo'lib ko'rinardi va kromkachi yo'q detallarni kutib turardi.
  if (isError) return <QueryError onRetry={() => refetch()} />

  // Arradan chiqqan nusxalar, uch pog'ona: JARAYONDA (bir tomoni skan
  // qilingan, tugamagan — kromkachi shuni davom ettiradi) tepada, keyin
  // boshlanmaganlar, tugaganlari yashil bo'lib PASTDA. Ilgari o'ng tomonda
  // alohida «Jarayonda» paneli bor edi — u jadvalning «Holat» ustunini
  // takrorlar va jadvalni yarim kenglikka siqib, nusxa chiplarini ustma-ust
  // (qatorni 4 barobar baland) qilib yuborardi. Endi jadval to'liq kenglikda,
  // jarayondagi qator tepada va sariq fonda.
  const tier = (p: { sides: number; instances: { done: number }[] }) => {
    const started = p.instances.some((i) => i.done > 0 && i.done < p.sides)
    if (started) return 0
    return p.instances.every((i) => i.done >= p.sides) ? 2 : 1
  }
  const leftParts = parts
    .map((p) => ({
      ...p,
      instances: p.instances.filter((i) => i.arra_passed),
    }))
    .filter((p) => p.instances.length > 0)
    .sort((a, b) => tier(a) - tier(b) || a.code.localeCompare(b.code))
  // Sarlavhadagi hisob: nechta nusxa yarim yo'lda (2+ tomonli, boshlangan)
  const inProgressCount = parts.reduce(
    (n, p) =>
      n +
      p.instances.filter((i) => p.sides >= 2 && i.done > 0 && i.done < p.sides)
        .length,
    0,
  )
  const totDone = parts.reduce((s, p) => s + p.total_done, 0)
  const totReq = parts.reduce((s, p) => s + p.total_required, 0)

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* CHAP: arradan kelgan detallar, progress joyida ko'rinadi */}
      <div className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
        <PostHeader
          onBack={onBack}
          orderNumber={data?.order_number}
          projectName={data?.project_name}
        >
          {/* Yarim yo'ldagi nusxalar soni — ular jadval tepasida sariq */}
          {!oval && inProgressCount > 0 && (
            <span className="num ml-auto rounded-md bg-amber-100 px-2.5 py-1 text-sm font-bold text-amber-800">
              Jarayonda {inProgressCount}
            </span>
          )}
          <PostProgress
            className={oval || !inProgressCount ? "ml-auto" : "ml-3"}
            done={totDone}
            total={totReq}
          />
        </PostHeader>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <table className="w-full text-base">
            <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <th className="px-4 py-2.5">Kod</th>
                <th className="px-4 py-2.5">Nomi</th>
                <th className="px-4 py-2.5">O'lchami</th>
                <th className="px-4 py-2.5">
                  {oval ? "Qirralar" : "Kromka"}
                  <span className="block whitespace-nowrap text-2xs font-medium normal-case tracking-normal">
                    qalin = lenta · uzuq = paz/oval · harf = lenta turi (tartib
                    emas)
                  </span>
                </th>
                <th className="px-4 py-2.5 text-right">
                  {/* Terminalda hover yo'q — izoh sarlavhaning o'zida: chip
                      nusxa, raqam qilingan/jami tomon */}
                  Nusxalar
                  <span className="block whitespace-nowrap text-2xs font-medium normal-case tracking-normal">
                    qilingan / tomon · ✓ bajarildi
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {leftParts.map((p) => {
                const finished = p.instances.every((i) => i.done >= p.sides)
                const started = !finished && tier(p) === 0
                return (
                  <tr
                    key={p.route_id}
                    id={`kv-row-${p.route_id}`}
                    className={cn(
                      "border-b last:border-0",
                      finished && "bg-green-50",
                      started && "bg-amber-50/70",
                      // Xatcho'p: holat rangini bosmaydi, chap chetda turadi
                      flashId === p.route_id && "border-l-4 border-l-primary",
                    )}
                  >
                    <td className="num whitespace-nowrap px-4 py-3 font-semibold">
                      {p.code}
                    </td>
                    <td className="max-w-[240px] px-4 py-3">
                      <div className="truncate">{p.name}</div>
                      <OperationChips
                        processCode={p.process_code}
                        postCode={oval ? "OVAL" : "KROMKA"}
                        defaultCode={oval ? 5 : 3}
                      />
                    </td>
                    <td className="num whitespace-nowrap px-4 py-3 text-sm">
                      {formatSize(p.length, p.width, p.thickness)}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className="inline-flex items-center gap-2">
                        <EdgeGlyph
                          edges={p.edges}
                          length={p.length}
                          width={p.width}
                          paz={p.paz_sides ?? []}
                        />
                        <span className="min-w-0">
                          {!oval && <b>{p.sides} tomon</b>}
                          <span
                            className={cn(
                              "block max-w-[220px] truncate text-xs text-muted-foreground",
                              oval && "text-sm",
                            )}
                          >
                            {edgeBands(p.edges)}
                          </span>
                          {(p.paz_sides ?? []).length > 0 && (
                            <span className="block text-xs font-semibold text-sky-700">
                              paz/oval — eskizdagi uzuq chiziq
                            </span>
                          )}
                        </span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {/* Ish TUGAGANDA bitta aniq belgi — prisadkadagi bilan
                          bir xil. Ilgari bu yerda faqat nusxa chiplari turardi
                          va tugagan qatorda ular hammasi "✓" bo'lib, "tayyor"
                          degan yagona ishorani berolmasdi: kromkachi 2 metrdan
                          qarab qaysi qator tugaganini darrov ajrata olmasdi.
                          Tugamagan qatorda chiplar qoladi — u yerda qaysi nusxa
                          nechta tomondan o'tgani muhim. */}
                      {finished ? (
                        <span className="rounded-md bg-green-600 px-2.5 py-1 text-sm font-bold text-white">
                          ✓ Bajarildi
                        </span>
                      ) : (
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
                                    : "bg-muted text-muted-foreground",
                              )}
                            >
                              {p.instances.length > 1 && (
                                <span className="mr-1 text-xs font-bold opacity-70">
                                  №{i.instance_no}
                                </span>
                              )}
                              {i.done >= p.sides
                                ? "✓"
                                : oval
                                  ? "–"
                                  : `${i.done}/${p.sides}`}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
              {!leftParts.length && (
                <tr>
                  <td
                    colSpan={oval ? 4 : 5}
                    className="h-32 text-center text-muted-foreground"
                  >
                    Arradan kelgan detal yo'q
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
