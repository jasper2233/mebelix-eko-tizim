// KROMKA post sahifasi — ikki panel (TZ 7.2):
// chapda arradan chiqqan kromkali detallar: har skan darhol yoziladi, 1 tomonli
// detal bitta skanda yashil bo'ladi, tugaganlari yashil bo'lib ro'yxatda qoladi.
// O'ngda "Jarayonda" — faqat 2+ tomonli, kamida 1 tomoni skan qilingan, hali
// tugamagan detallar. Xato skan BEKOR QILISH (60s) bilan qaytariladi.

import { useQuery } from "@tanstack/react-query"
import { ArrowLeft } from "lucide-react"
import { useEffect, useMemo, useRef } from "react"

import { TerminalService } from "@/client"
import { OperationChips } from "@/components/Common/OperationChips"
import { PostProgress } from "@/components/Terminal/PostProgress"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useScanFlash } from "@/hooks/useScanFlash"
import { formatSize } from "@/lib/mes"
import { cn } from "@/lib/utils"

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
  const { data, isLoading } = useQuery({
    queryKey: ["terminal", "kromka", orderId],
    queryFn: () => TerminalService.readTerminalKromka({ orderId }),
    refetchInterval: 30_000,
  })

  // KromkaPartRow'da edges/instances sxemada ixtiyoriy — bir joyda normallashtiramiz,
  // quyida hamma joyda oddiy massiv/obyekt sifatida ishlatiladi
  const parts = useMemo(
    () =>
      (data?.parts ?? []).map((p) => ({
        ...p,
        edges: p.edges ?? {},
        instances: p.instances ?? [],
      })),
    [data],
  )

  // Tekshiruv har renderda yangi data ko'radi, terminal esa bir marta ro'yxatga oladi
  const checkRef = useRef<(qr: string) => string | null>(() => "NOTFOUND")
  checkRef.current = (raw: string): string | null => {
    // Eski yorliqlar: migratsiyadan oldin yagona nusxa ham `_1` bilan chop etilgan
    const candidates = raw.endsWith("_1") ? [raw, raw.slice(0, -2)] : [raw]
    for (const qr of candidates) {
      for (const p of parts) {
        const inst = p.instances.find((i) => i.qr_text === qr)
        if (!inst) continue
        if (!inst.arra_passed) return "Bu detal hali arradan chiqmagan."
        if (inst.done >= p.sides)
          return oval
            ? "Bu detalning oval kromkasi allaqachon tugagan."
            : "Bu detalning kromkasi allaqachon tugagan."
        return null
      }
    }
    return "NOTFOUND"
  }
  useEffect(() => {
    registerScan?.((qr) => checkRef.current(qr))
    return () => registerScan?.(null)
  }, [registerScan])

  // Oxirgi skan bo'lgan detal qatori keyingi skangacha ajralib turadi + avto-scroll
  const flashId = useScanFlash(
    parts,
    (p) => p.part_id,
    (p) => p.instances.reduce((s, i) => s + i.done, 0),
    "kv-row-",
  )

  if (isLoading) return <Skeleton className="h-full w-full" />

  // Chap: arradan chiqqan nusxalar — tugaganlari yashil bo'lib PASTGA tushadi,
  // qilinmaganlari tepada (kromkachi navbatdagi ishni tepadan oladi)
  const leftParts = parts
    .map((p) => ({
      ...p,
      instances: p.instances.filter((i) => i.arra_passed),
    }))
    .filter((p) => p.instances.length > 0)
    .sort((a, b) => {
      const fin = (p: typeof a) =>
        p.instances.every((i) => i.done >= p.sides) ? 1 : 0
      return fin(a) - fin(b) || a.code.localeCompare(b.code)
    })

  // O'ng "Jarayonda": faqat 2+ tomonli, boshlangan-u tugamagan nusxalar
  const inProgress = parts
    .flatMap((p) =>
      p.instances
        .filter((i) => p.sides >= 2 && i.done > 0 && i.done < p.sides)
        .map((i) => ({ part: p, inst: i })),
    )
    .sort((a, b) => a.part.code.localeCompare(b.part.code))

  const totDone = parts.reduce((s, p) => s + p.total_done, 0)
  const totReq = parts.reduce((s, p) => s + p.total_required, 0)

  return (
    <div className="flex h-full min-h-0 gap-3">
      {/* CHAP: arradan kelgan detallar, progress joyida ko'rinadi */}
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
          <PostProgress className="ml-auto" done={totDone} total={totReq} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <table className="w-full text-base">
            <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
              <tr>
                <th className="px-4 py-2.5">Kod</th>
                <th className="px-4 py-2.5">Nomi</th>
                <th className="px-4 py-2.5">O'lchami</th>
                {!oval && <th className="px-4 py-2.5">Kromka</th>}
                <th className="px-4 py-2.5 text-right">Holat</th>
              </tr>
            </thead>
            <tbody>
              {leftParts.map((p) => {
                const finished = p.instances.every((i) => i.done >= p.sides)
                return (
                  <tr
                    key={p.route_id}
                    id={`kv-row-${p.part_id}`}
                    className={cn(
                      "border-b last:border-0",
                      finished && "bg-green-50",
                      // Xatcho'p: holat rangini bosmaydi, chap chetda turadi
                      flashId === p.part_id && "border-l-4 border-l-primary",
                    )}
                  >
                    <td className="num px-4 py-3 font-semibold">{p.code}</td>
                    <td className="max-w-[240px] px-4 py-3">
                      <div className="truncate">{p.name}</div>
                      <OperationChips
                        processCode={p.process_code}
                        postCode={oval ? "OVAL" : "KROMKA"}
                      />
                    </td>
                    <td className="num whitespace-nowrap px-4 py-3 text-sm">
                      {formatSize(p.length, p.width, p.thickness)}
                    </td>
                    {!oval && (
                      <td className="px-4 py-3 text-sm">
                        <b>{p.sides} tomon</b>
                        <span className="ml-1.5 text-muted-foreground">
                          {Object.keys(p.edges)
                            .map((k) => SIDE_LABELS[k] ?? k)
                            .join(", ")}
                        </span>
                      </td>
                    )}
                    <td className="px-4 py-3 text-right">
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

      {/* O'NG: Jarayonda — 2+ tomonli, boshlangan, tugamagan. OVAL'da panel
          yo'q: har detal bitta skanda tugaydi, jarayon bo'lmaydi */}
      {oval ? null : (
        <div className="flex min-w-0 flex-1 flex-col rounded-xl border bg-white">
          <div className="border-b px-4 py-3 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Jarayonda{" "}
            {inProgress.length > 0 && (
              <span className="num ml-1 rounded-sm bg-amber-100 px-1.5 py-0.5 text-amber-700">
                {inProgress.length}
              </span>
            )}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {inProgress.map(({ part, inst }) => (
              <div
                key={inst.instance_id}
                className="flex items-center gap-3 border-b px-4 py-3 last:border-0"
              >
                <div className="min-w-0 flex-1">
                  {/* To'liq nusxa ID — chekdagi satr bilan aynan bir xil */}
                  <div className="num truncate text-base font-semibold">
                    {inst.qr_text}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {part.name} ·{" "}
                    {formatSize(part.length, part.width, part.thickness)}
                  </div>
                </div>
                <span className="num shrink-0 rounded-md bg-amber-100 px-3 py-1.5 text-xl font-black text-amber-700">
                  {inst.done}/{part.sides}
                </span>
              </div>
            ))}
            {!inProgress.length && (
              <p className="p-4 text-sm text-muted-foreground">
                Jarayonda detal yo'q. QR skan qilinsa hisob darhol yoziladi: 1
                tomonlisi shu zahoti yashil bo'ladi, ko'p tomonlisi tugaguncha
                shu yerda turadi.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
