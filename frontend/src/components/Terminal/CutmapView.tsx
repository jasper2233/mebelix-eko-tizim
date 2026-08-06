// ARRA kesish xaritasi (TZ 7.1.7) — GibSaw uslubidagi ekran: materiallar jadvali,
// list kartochkalari, to'liq list SVG (detallar, kesim chiziqlari, teshiklar overlay),
// detal kartochkasi (katta QR + YORLIQ CHOP ETISH). GibCut litsenziyasi o'rnini bosadi.

import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minus,
  Plus,
  Printer,
  RotateCw,
} from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useEffect, useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { renderToStaticMarkup } from "react-dom/server"
import { toast } from "sonner"

import {
  type CutmapInstanceState,
  OrdersService,
  TerminalService,
} from "@/client"
import {
  edgeBoreRect,
  edgeLocalXY,
  holeXY,
  SheetSvg,
} from "@/components/Terminal/SheetSvg"
import { usePrintLabel } from "@/components/Terminal/usePrintLabel"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { isCut } from "@/lib/mes"
import { handleError } from "@/utils"

// Kesish xaritasi modeli (order.cutmap JSON) server tomonda tiplashtirilmagan
// (CutmapState.model = {[k: string]: unknown} | null) — lokal any'lar shu sababli
type SheetPart = any
type Sheet = any
type Material = any

const getCutmapQueryOptions = (orderId: number, admin: boolean) =>
  queryOptions({
    queryKey: [admin ? "admin" : "terminal", "cutmap", orderId],
    queryFn: () =>
      admin
        ? OrdersService.readOrderCutmap({ orderId })
        : TerminalService.readTerminalCutmap({ orderId }),
    refetchInterval: 60_000,
  })

// Noto'g'ri chiqarilgan chekni bekor qilish (long press) — katak apelsinga qaytadi
function useCancelLabel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (instanceId: number) =>
      TerminalService.cancelInstanceLabel({ instanceId }),
    onSuccess: (r) => toast.success(r.message),
    onError: handleError,
    onSettled: () => {
      // Terminal (arrachi long press) ham, admin xarita (texnolog tugmasi) ham yangilansin
      queryClient.invalidateQueries({ queryKey: ["terminal", "cutmap"] })
      queryClient.invalidateQueries({ queryKey: ["admin", "cutmap"] })
    },
  })
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`)
}

/** Barcha kesish xaritalarini chop etish: har xarita tepasida
 * "Material nomi | №1 — 2750 × 1830 mm × 2 list" sarlavha, har list o'z sahifasida. */
function printAllMaps(
  orderNumber: string,
  materials: Material[],
  holes: Record<string, any>,
  instancesByCell: Map<string, CutmapInstanceState[]>,
) {
  const w = window.open("", "_blank", "width=1000,height=800")
  if (!w) return
  const blocks = materials
    .flatMap((m: Material) =>
      m.sheets.map(
        (s: Sheet) => `
        <section>
          <h2>${escapeHtml(m.name)} | №${s.disp ?? s.no} — ${s.L} × ${s.W} mm</h2>
          ${renderToStaticMarkup(
            <SheetSvg
              sheet={s}
              holes={holes}
              instancesByCell={instancesByCell}
              onSelect={() => {}}
              selectedCell={null}
            />,
          )}
        </section>`,
      ),
    )
    .join("")
  w.document.write(`<!doctype html><html lang="uz"><head><meta charset="utf-8">
    <title>${escapeHtml(orderNumber)} — kesish xaritalari</title>
    <style>
      @page{ size: A4 landscape; margin: 8mm }
      body{font-family:system-ui,sans-serif;color:#000;margin:0}
      section{page-break-after:always;page-break-inside:avoid;padding:4px 8px}
      section:last-child{page-break-after:auto}
      h2{font-size:15px;margin:0 0 4px;border-bottom:2px solid #000;padding-bottom:3px}
      svg{width:100%;height:auto;max-height:180mm;display:block}
    </style></head><body>${blocks}</body></html>`)
  w.document.close()
  w.focus()
  setTimeout(() => w.print(), 300)
}

export function CutmapView({
  orderId,
  onBack,
  admin = false,
  registerPrint,
  statsContainer,
  toolbarContainer,
  focusPartKey,
}: {
  orderId: number
  onBack: () => void
  admin?: boolean
  /** Sahifa tepasidagi "PDF / Chop etish" tugmasi shu funksiyani chaqiradi (barcha xaritalar). */
  registerPrint?: (fn: () => void) => void
  /** Material statistikasi shu elementga portal qilinadi (terminal header); yo'q bo'lsa xarita panelida qoladi */
  statsContainer?: HTMLElement | null
  /** Toolbar tugmalari shu elementga portal qilinadi (terminal chap ustuni); yo'q bo'lsa o'z ustunida */
  toolbarContainer?: HTMLElement | null
  /** Matritsadan sakrash: shu kalitli detalning listi ochilib, katakchasi belgilanadi */
  focusPartKey?: string
}) {
  const { data, isLoading } = useQuery(getCutmapQueryOptions(orderId, admin))
  // GibLab uslubi: bitta sahifa (material tablar + list grid), list -> xarita
  const [materialIdx, setMaterialIdx] = useState(0)
  const [sheetIdx, setSheetIdxRaw] = useState<number | null>(null)
  const setSheetIdx = (v: number | null) => {
    setSheetIdxRaw(v)
    setMarkedCell(null)
  }
  const [selected, setSelected] = useState<SheetPart | null>(null)
  // Bosilgan detal kartochka yopilgach ham moviy belgilangan qoladi
  const [markedCell, setMarkedCell] = useState<number | null>(null)
  // Long press: bekor qilishdan avval tasdiq — qo'lqopda tasodifiy bosib
  // turish ham bo'ladi, chekni indamay o'chirish xavfli
  const [cancelTarget, setCancelTarget] = useState<{
    num: number
    name: string
    qr_text: string
    instance_id: number
  } | null>(null)
  // GibLab toolbar zoom API (SheetSvg ro'yxatdan o'tkazadi)
  const zoomApi = useRef<{
    zin: () => void
    zout: () => void
    reset: () => void
  } | null>(null)

  // Chap qatordagi Chop etish: belgilangan detalning navbatdagi nusxasi
  // to'g'ridan-to'g'ri GoDEX navbatiga ketadi (dialog yo'q)
  const printMutation = usePrintLabel("cutmap")
  const cancelMutation = useCancelLabel()

  const instancesByCell = useMemo(() => {
    const map = new Map<string, CutmapInstanceState[]>()
    for (const inst of data?.instances ?? []) {
      if (inst.pattern_no == null) continue
      const key = `${inst.pattern_no}:${inst.cell_index}`
      const list = map.get(key)
      if (list) list.push(inst)
      else map.set(key, [inst])
    }
    return map
  }, [data])

  // HAR JISMONIY LIST ALOHIDA KARTA: mult>1 naqsh render paytida nusxalarga
  // yoyiladi — har karta faqat O'Z nusxalarini ko'radi (katak holati listga xos).
  // Bazadagi eski (yig'ilgan) xaritalar uchun ham ishlaydi — backend o'zgarmagan,
  // binding (pattern_no, cell_index) semantikasi buzilmaydi.
  const { expMaterials, cellInsts } = useMemo(() => {
    const view = new Map<string, CutmapInstanceState[]>()
    const mats = (((data?.model as any)?.materials ?? []) as any[]).map(
      (m: any) => {
        let disp = 0
        const sheets = ((m.sheets ?? []) as any[]).flatMap((s: any) => {
          const mult = s.mult || 1
          return Array.from({ length: mult }, (_, k) => {
            disp += 1
            const no = mult > 1 ? `${s.no}c${k + 1}` : s.no
            for (const p of s.parts ?? []) {
              if (p.waste) continue
              const all = instancesByCell.get(`${s.no}:${p.cell}`) ?? []
              // Barqaror taqsimot: k-karta har katakning k-nusxasini oladi
              const sorted = [...all].sort(
                (a, b) =>
                  (a.instance_no ?? 0) - (b.instance_no ?? 0) ||
                  a.instance_id - b.instance_id,
              )
              view.set(
                `${no}:${p.cell}`,
                mult > 1 ? sorted.slice(k, k + 1) : sorted,
              )
            }
            return { ...s, no, disp, mult: 1 }
          })
        })
        return { ...m, sheets }
      },
    )
    return { expMaterials: mats, cellInsts: view }
  }, [data, instancesByCell])

  // Matritsadan kelgan "xaritada ko'rsat" sakrashi: ma'lumot kelgach detalning
  // birinchi katakchasini topib, o'sha material + listni ochamiz va belgilaymiz.
  // BIR MARTA: aks holda har refetch (60s interval, fokus) foydalanuvchi qaysi
  // listga o'tgan bo'lsa ham uni qaytarib uloqtirardi.
  const focusApplied = useRef(false)
  useEffect(() => {
    if (!focusPartKey || !data?.model || focusApplied.current) return
    focusApplied.current = true
    for (let mi = 0; mi < expMaterials.length; mi++) {
      const shs = expMaterials[mi].sheets ?? []
      for (let si = 0; si < shs.length; si++) {
        const hit = (shs[si].parts ?? []).find(
          (p: any) => !p.waste && p.key === focusPartKey,
        )
        if (hit) {
          setMaterialIdx(mi)
          setSheetIdxRaw(si)
          setMarkedCell(hit.cell)
          return
        }
      }
    }
  }, [focusPartKey, data, expMaterials])

  if (isLoading) return <Skeleton className="h-full w-full" />
  if (!data?.model) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <p className="max-w-md text-muted-foreground">
          Kesish xaritasi mavjud emas — fayl GibLabda optimizatsiya qilinmagan
          (TEMPLATE). Oddiy vazifalar ro'yxatidan foydalaning.
        </p>
        <Button
          variant="outline"
          className="h-12 px-6 text-base"
          onClick={onBack}
        >
          <ArrowLeft /> Orqaga
        </Button>
      </div>
    )
  }

  const model = data.model as any
  const materials: Material[] = expMaterials
  const material = materials[materialIdx]
  const sheets: Sheet[] = material?.sheets ?? []
  const sheet = sheetIdx !== null ? sheets[sheetIdx] : undefined
  const holes = (model.holes ?? {}) as Record<string, any>

  const sheetDone = (s: Sheet) => {
    const cells = (s.parts as SheetPart[]).filter((p) => !p.waste)
    if (!cells.length) return false
    return cells.every((p) => {
      const insts = cellInsts.get(`${s.no}:${p.cell}`) ?? []
      return insts.length > 0 && insts.every(isCut)
    })
  }

  registerPrint?.(() =>
    printAllMaps(data.order_number, materials, holes, cellInsts),
  )

  // Material statistikasi — ixcham bir qator (terminalda SKAN ON qatoriga portal,
  // admin sahifada xarita tepasida). Xarita balandligidan joy olmaydi.
  const listTot = sheets.reduce((a: number, s: Sheet) => a + (s.mult || 1), 0)
  const listDn = sheets
    .filter(sheetDone)
    .reduce((a: number, s: Sheet) => a + (s.mult || 1), 0)
  const detTot = Number(material?.kd) || 0
  let detDn = 0
  for (const s of sheets) {
    for (const p of s.parts as SheetPart[]) {
      if (p.waste) continue
      detDn += (cellInsts.get(`${s.no}:${p.cell}`) ?? []).filter(isCut).length
    }
  }
  const markedPart =
    sheet && markedCell !== null
      ? (sheet.parts as SheetPart[]).find(
          (p) => p.cell === markedCell && !p.waste,
        )
      : undefined
  const markedInsts = markedPart
    ? (cellInsts.get(`${sheet.no}:${markedPart.cell}`) ?? [])
    : []
  // Fallback YO'Q: hammasi chiqarilgan bo'lsa qayta chop etilmaydi —
  // avval long press bilan bekor qilinadi (dublikat chek oqimni buzadi)
  const nextInstance = markedInsts.find((i) => !isCut(i))

  const statPairs: Array<[string, string | number]> = [
    ["Listlar", `${listTot}−${listDn}=${listTot - listDn}`],
    ["Detallar", `${detTot}−${detDn}=${detTot - detDn}`],
    ["Atxot", material?.ko ?? "—"],
    ["Rez, m", material?.dr?.toFixed?.(1) ?? material?.dr ?? "—"],
    ["Rezlar", material?.kr ?? "—"],
    [
      "To'ldirish",
      material?.fill ? `${(material.fill * 100).toFixed(1)}%` : "—",
    ],
    ["Arra", material?.kerf ?? "—"],
    ["Tirim uz.", material?.trimL ?? "—"],
    ["Tirim en", material?.trimW ?? "—"],
  ]
  // GibSaw uslubi: 3 qator × 3 ustun qat'iy blok (KK/KD/KO | DR/KR/PZ | TP/TD/TSh)
  // — hech qachon o'ramaydi, header balandligi o'smaydi, eni ~400px
  // Header info: list nomi (ochiq bo'lsa) + 3x3 statlar — bitta portalda
  const statsRow = material ? (
    <div
      className={`flex w-fit items-center gap-6 ${statsContainer ? "mx-auto" : ""}`}
    >
      {sheet && (
        <div className="min-w-0 max-w-[320px] text-base font-black">
          <div className="whitespace-nowrap">
            №{sheet.disp ?? sheet.no} —{" "}
            <span className="num">
              {sheet.L} × {sheet.W} mm
            </span>
          </div>
          <div className="truncate text-xs font-normal text-muted-foreground">
            {material.name}
          </div>
        </div>
      )}
      <div
        className="num grid w-fit grid-flow-col grid-rows-3 text-xs leading-[1.4]"
        style={{ columnGap: "18px" }}
      >
        {statPairs.map(([l, v]) => (
          <span key={l} className="whitespace-nowrap">
            <span className="text-muted-foreground">{l}:</span> <b>{v}</b>
          </span>
        ))}
      </div>
    </div>
  ) : null

  // Web (admin) boshqaruvi: sichqonchaga mo'ljallangan ixcham qator — chapdagi
  // 68px sensor ustuni 17" terminal uchun, webda u joy yeb qiyshiq ko'rinardi.
  const webToolbar =
    admin && sheetIdx !== null ? (
      <div className="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="icon-sm"
          disabled={sheetIdx === 0}
          onClick={() => setSheetIdx(sheetIdx - 1)}
          title="Oldingi list"
        >
          <ChevronUp />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          disabled={sheetIdx >= sheets.length - 1}
          onClick={() => setSheetIdx(sheetIdx + 1)}
          title="Keyingi list"
        >
          <ChevronDown />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => zoomApi.current?.zin()}
          title="Kattalashtirish"
        >
          <Plus />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => zoomApi.current?.zout()}
          title="Kichiklashtirish"
        >
          <Minus />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => zoomApi.current?.reset()}
          title="To'liq ko'rinish"
        >
          <Maximize2 />
        </Button>
      </div>
    ) : null

  const toolbarButtons = (
    <>
      <TBtn
        label="Orqaga"
        tone="primary"
        onClick={() => (sheetIdx !== null ? setSheetIdx(null) : onBack())}
      >
        <ArrowLeft />
      </TBtn>
      <TBtn
        label="Oldingi"
        disabled={sheetIdx === null || sheetIdx === 0}
        onClick={() => sheetIdx !== null && setSheetIdx(sheetIdx - 1)}
      >
        <ChevronUp />
      </TBtn>
      <TBtn
        label="Keyingi"
        disabled={sheetIdx === null || sheetIdx >= sheets.length - 1}
        onClick={() => sheetIdx !== null && setSheetIdx(sheetIdx + 1)}
      >
        <ChevronDown />
      </TBtn>
      <TBtn
        label="Katta"
        disabled={sheetIdx === null}
        onClick={() => zoomApi.current?.zin()}
      >
        <Plus />
      </TBtn>
      <TBtn
        label="Kichik"
        disabled={sheetIdx === null}
        onClick={() => zoomApi.current?.zout()}
      >
        <Minus />
      </TBtn>
      <TBtn
        label="To'liq"
        disabled={sheetIdx === null}
        onClick={() => zoomApi.current?.reset()}
      >
        <Maximize2 />
      </TBtn>
      <TBtn
        label="Chop etish"
        tone={nextInstance ? "success" : "default"}
        disabled={!markedInsts.length || printMutation.isPending}
        onClick={() =>
          nextInstance
            ? printMutation.mutate(nextInstance.instance_id)
            : toast.error(
                "Bu detal chiqarilgan. Qaytadan chiqarish uchun katakni bosib turib chekni bekor qiling.",
              )
        }
      >
        <Printer />
      </TBtn>
    </>
  )

  return (
    <div className="flex h-full gap-3">
      {statsContainer
        ? statsRow && createPortal(statsRow, statsContainer)
        : null}

      {/* Chap toolbar (GibLab joylashuvi): terminalda umumiy ustunga portal,
          admin sahifada o'z ustunida */}
      {toolbarContainer ? (
        createPortal(toolbarButtons, toolbarContainer)
      ) : admin ? null : (
        <div className="flex w-[68px] shrink-0 flex-col gap-2">
          {toolbarButtons}
        </div>
      )}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
        {!statsContainer && (statsRow || webToolbar) && (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              {/* Orqaga-navigatsiya CHAPDA: "Listlar" o'ngda turganda odam
                  odatiy chapdagi "← Buyurtma"ni bosib sahifadan chiqib ketardi */}
              {admin && sheetIdx !== null && (
                <Button size="sm" onClick={() => setSheetIdx(null)}>
                  <ArrowLeft /> Listlar ro'yxati
                </Button>
              )}
              {statsRow ?? <span />}
            </div>
            {webToolbar}
          </div>
        )}
        {sheetIdx === null ? (
          /* Jadval sahifasi: material tablar + list grid (GibLab #matlist + #grid) */
          <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border bg-white p-4">
            {/* Material tablar: bitta qator, ko'paysa gorizontal swipe (grid joyini yemaydi) */}
            <div className="mb-3 flex items-center gap-2 overflow-x-auto pb-1">
              {materials.map((m: Material, i: number) => {
                const mdone = m.sheets.filter(sheetDone).length
                const active = i === materialIdx
                return (
                  <Button
                    key={m.name}
                    variant={active ? "default" : "outline"}
                    className="h-12 max-w-xs shrink-0 px-4 text-base"
                    onClick={() => setMaterialIdx(i)}
                  >
                    <span className="truncate">{m.name}</span>
                    <span
                      className={`num ml-1 text-xs ${active ? "opacity-80" : "text-muted-foreground"}`}
                    >
                      {mdone}/{m.sheets.length}
                    </span>
                  </Button>
                )
              })}
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {sheets.map((s: Sheet, i: number) => {
                const done = sheetDone(s)
                return (
                  <button
                    type="button"
                    key={s.no}
                    onClick={() => setSheetIdx(i)}
                    className={`rounded-xl border-2 px-4 py-3 text-left outline-none transition-all hover:border-primary focus-visible:ring-[3px] focus-visible:ring-ring/50 active:scale-[0.98] active:border-primary ${
                      done
                        ? "border-green-500/60 bg-green-50 text-green-700"
                        : ""
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="num text-xl font-black">
                        №{s.disp ?? s.no}
                      </span>
                      <span className="num flex-1 text-base">
                        {s.L}×{s.W}
                      </span>
                    </div>
                    {/* Mini xarita — kichik preview, bosishga xalaqit bermaydi */}
                    <div className="pointer-events-none mt-2 h-32 overflow-hidden rounded-lg border bg-slate-100 p-1">
                      <SheetSvg
                        sheet={s}
                        holes={holes}
                        instancesByCell={cellInsts}
                        onSelect={() => {}}
                        selectedCell={null}
                        thumbnail
                      />
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        ) : (
          /* Xarita (GibLab #single) — to'liq maydon; sarlavha xarita ustida overlay
             (alohida qator xaritadan joy olmasin) */
          <div
            className={`relative min-h-0 flex-1 overflow-hidden bg-slate-200 ${
              toolbarContainer ? "" : "rounded-xl border p-1"
            }`}
          >
            <div className="h-full w-full">
              <SheetSvg
                sheet={sheet}
                holes={holes}
                instancesByCell={cellInsts}
                onSelect={(part) => {
                  // Terminalda tap faqat belgilaydi — chop etish chap qatordan;
                  // admin (texnolog) esa QR kartochkani ko'radi
                  if (admin) setSelected(part)
                  setMarkedCell(part.cell)
                }}
                onLongPress={
                  admin
                    ? undefined
                    : (part) => {
                        // Noto'g'ri detal cheki chiqib ketgan: oxirgi chiqarilgan
                        // (hali skan qilinmagan) nusxa tasdiqdan keyin bekor bo'ladi
                        const insts =
                          cellInsts.get(`${sheet.no}:${part.cell}`) ?? []
                        const last = insts
                          .filter((i) => i.label_printed_at && !i.done)
                          .sort((a, b) =>
                            String(a.label_printed_at).localeCompare(
                              String(b.label_printed_at),
                            ),
                          )
                          .pop()
                        if (last)
                          setCancelTarget({
                            num: part.num ?? part.id,
                            name: part.name,
                            qr_text: last.qr_text,
                            instance_id: last.instance_id,
                          })
                      }
                }
                selectedCell={markedCell}
                registerZoom={(a) => {
                  zoomApi.current = a
                }}
                onSwipe={(dir) =>
                  sheetIdx !== null &&
                  setSheetIdx(
                    dir === "next"
                      ? Math.min(sheetIdx + 1, sheets.length - 1)
                      : Math.max(sheetIdx - 1, 0),
                  )
                }
              />
            </div>
          </div>
        )}
      </div>

      <PartCard
        part={selected}
        sheetNo={sheet?.no}
        instancesByCell={cellInsts}
        onClose={() => setSelected(null)}
        admin={admin}
        holes={holes}
      />

      {/* Long press tasdiq dialogi — qo'lqopga mos katta tugmalar */}
      <Dialog
        open={cancelTarget !== null}
        onOpenChange={(v) => !v && setCancelTarget(null)}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Chekni bekor qilasizmi?</DialogTitle>
          </DialogHeader>
          {cancelTarget && (
            <p className="text-base">
              №{cancelTarget.num} — {cancelTarget.name}{" "}
              <span className="num text-muted-foreground">
                ({cancelTarget.qr_text})
              </span>
              <br />
              Katak chop etilmagan holatga qaytadi.
            </p>
          )}
          <div className="flex gap-3">
            <Button
              variant="outline"
              className="h-14 flex-1 text-base font-bold"
              onClick={() => setCancelTarget(null)}
            >
              Yo'q
            </Button>
            <LoadingButton
              variant="destructive"
              className="h-14 flex-1 text-base font-bold"
              loading={cancelMutation.isPending}
              onClick={() => {
                if (!cancelTarget) return
                cancelMutation.mutate(cancelTarget.instance_id, {
                  onSuccess: () => setCancelTarget(null),
                })
              }}
            >
              Ha, bekor qilinsin
            </LoadingButton>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

/** Chap toolbar tugmasi: ikonka + kichik yozuv (sanoat HMI uslubi).
 * tone — funksiya bo'yicha rang kodi: primary (asosiy nav), warn (qulf), danger (chiqish). */
const TBTN_TONES = {
  default: "border bg-white text-primary hover:border-primary",
  primary:
    "border-transparent bg-primary text-primary-foreground hover:bg-primary/90",
  // warn to'ldirilmaydi: amber fon xarita apelsini bilan qo'shilib ketardi — faqat ikonka rangi
  warn: "border bg-white text-amber-600 hover:border-amber-500",
  danger: "border-transparent bg-red-600 text-white hover:bg-red-700",
  success: "border-transparent bg-green-600 text-white hover:bg-green-700",
} as const

export function TBtn({
  label,
  disabled = false,
  tone = "default",
  onClick,
  children,
}: {
  label: string
  disabled?: boolean
  tone?: keyof typeof TBTN_TONES
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`flex h-16 w-full flex-col items-center justify-center gap-1 rounded-xl shadow-sm outline-none transition-all focus-visible:ring-[3px] focus-visible:ring-ring/50 active:scale-95 disabled:opacity-40 [&_svg]:size-6 ${TBTN_TONES[tone]}`}
    >
      {children}
      <span className="text-2xs font-bold leading-none">{label}</span>
    </button>
  )
}

/** Tanlangan detal mini-chizmasi: o'lcham strelkalari + teshiklar (GibSaw «Чертеж детали»). */
function PartPreview({
  part,
  holes,
}: {
  part: SheetPart
  holes: Record<string, any>
}) {
  const w = part.w
  const h = part.h
  const boxW = 276
  const boxH = 190
  const m = 34
  const scale = Math.min((boxW - 2 * m) / w, (boxH - 2 * m) / h)
  const rw = w * scale
  const rh = h * scale
  const ox = (boxW - rw) / 2
  const oy = (boxH - rh) / 2
  const H = holes[String(part.id)]
  const local = { ...part, x: ox, y: oy, w: rw, h: rh } as SheetPart
  const ty = oy - 13
  const lx = ox - 13
  return (
    <svg viewBox={`0 0 ${boxW} ${boxH}`} className="block h-auto w-full">
      <title>Detal chizmasi</title>
      <rect
        x={ox}
        y={oy}
        width={rw}
        height={rh}
        fill="#d2d2d2"
        stroke="#242424"
        strokeWidth="1.5"
      />
      {H?.bores?.map((b: any, i: number) => {
        const [cx, cy] = holeXY(local, H, b.x, b.y)
        return (
          <circle
            key={`b${i}`}
            cx={cx}
            cy={cy}
            r={Math.max((b.d / 2) * scale, 2.4)}
            fill="#fafafa"
            stroke="#202020"
            strokeWidth="1"
          />
        )
      })}
      {H?.edge?.map((b: any, i: number) => {
        const [px, py] = edgeLocalXY(H, b.side, b.pos)
        const [cx, cy] = holeXY(local, H, px, py)
        const r = edgeBoreRect(
          local,
          cx,
          cy,
          Math.max(b.d * scale, 2),
          Math.max((b.dp || 12) * scale, 4),
        )
        return (
          <rect
            key={`e${i}`}
            x={r.x}
            y={r.y}
            width={r.w}
            height={r.h}
            fill="#fafafa"
            stroke="#202020"
            strokeWidth="1"
          />
        )
      })}
      <line
        x1={ox}
        y1={ty}
        x2={ox + rw}
        y2={ty}
        stroke="#333"
        strokeWidth="1"
      />
      <path
        d={`M${ox} ${ty}l6 -3M${ox} ${ty}l6 3M${ox + rw} ${ty}l-6 -3M${ox + rw} ${ty}l-6 3`}
        stroke="#333"
        strokeWidth="1"
        fill="none"
      />
      <text
        x={ox + rw / 2}
        y={ty - 5}
        fontSize="14"
        fontWeight="bold"
        textAnchor="middle"
        fill="#111"
      >
        {w}
      </text>
      <line
        x1={lx}
        y1={oy}
        x2={lx}
        y2={oy + rh}
        stroke="#333"
        strokeWidth="1"
      />
      <path
        d={`M${lx} ${oy}l-3 6M${lx} ${oy}l3 6M${lx} ${oy + rh}l-3 -6M${lx} ${oy + rh}l3 -6`}
        stroke="#333"
        strokeWidth="1"
        fill="none"
      />
      <text
        x={lx - 5}
        y={oy + rh / 2}
        fontSize="14"
        fontWeight="bold"
        textAnchor="middle"
        fill="#111"
        transform={`rotate(-90 ${lx - 5} ${oy + rh / 2})`}
      >
        {h}
      </text>
      {part.rot && (
        <text
          x={ox + rw - 4}
          y={oy + 16}
          fontSize="15"
          textAnchor="end"
          fill="#a94b05"
        >
          ⟳
        </text>
      )}
    </svg>
  )
}

function PartCard({
  part,
  sheetNo,
  instancesByCell,
  onClose,
  admin = false,
  holes,
}: {
  part: SheetPart | null
  sheetNo?: number
  instancesByCell: Map<string, CutmapInstanceState[]>
  onClose: () => void
  admin?: boolean
  holes: Record<string, any>
}) {
  // PartCard faqat admin xaritada ochiladi (onSelect if(admin)) — terminal
  // chop etish chap toolbar orqali; shuning uchun bu yerda print mutatsiyasi yo'q
  const cancelMutation = useCancelLabel()

  if (!part || part.waste) return null
  const insts = instancesByCell.get(`${sheetNo}:${part.cell}`) ?? []
  const next = insts.find((i) => !i.done) ?? insts[0]

  return (
    <Dialog open={!!part} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            №{part.num} — {part.name}{" "}
            {part.rot && <RotateCw className="inline size-4" />}
          </DialogTitle>
        </DialogHeader>
        <div className="rounded-lg border bg-white p-2">
          <PartPreview part={part} holes={holes} />
        </div>
        <div className="flex items-start gap-4">
          {next && (
            <div className="shrink-0 rounded-lg border p-2">
              <QRCodeSVG value={next.qr_text} size={170} />
              <div className="num mt-1 text-center text-2xs text-muted-foreground">
                {next.qr_text}
              </div>
            </div>
          )}
          <div className="num space-y-1 text-sm">
            <div>
              O'lcham:{" "}
              <b>
                {part.w} × {part.h} mm
              </b>
            </div>
            <div>
              Kromka:{" "}
              {[part.eW?.[0], part.eW?.[1], part.eH?.[0], part.eH?.[1]]
                .filter(Boolean)
                .join(", ") || "yo'q"}
            </div>
            <div>
              Yorliq raqami: <b>№{part.num}</b>
            </div>
          </div>
        </div>
        <div className="space-y-1.5">
          {insts.map((inst) => (
            <div
              key={inst.instance_id}
              className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm"
            >
              <span className="num">
                {inst.qr_text}{" "}
                {inst.done ? (
                  <span className="font-bold text-green-700">✓ kesildi</span>
                ) : inst.label_printed_at ? (
                  <span className="font-bold text-green-600">
                    ✓ chek chiqarilgan
                  </span>
                ) : null}
              </span>
              {/* Texnolog xato chekni shu yerdan tuzatadi — proyekt ARRA
                  ro'yxatidan tushib bo'lgach arrachi xaritani ocholmaydi */}
              {admin && inst.label_printed_at && !inst.done && (
                <LoadingButton
                  variant="destructive"
                  size="sm"
                  loading={cancelMutation.isPending}
                  onClick={() => cancelMutation.mutate(inst.instance_id)}
                >
                  Chekni bekor qilish
                </LoadingButton>
              )}
            </div>
          ))}
        </div>
        {/* Radix X 16px — qo'lqopga kichik; katta yopish tugmasi */}
        <Button
          variant="outline"
          className="h-12 w-full text-base font-bold"
          onClick={onClose}
        >
          Yopish
        </Button>
      </DialogContent>
    </Dialog>
  )
}
