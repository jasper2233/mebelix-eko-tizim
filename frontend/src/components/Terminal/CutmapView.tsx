// ARRA kesish xaritasi — GibSaw uslubidagi ekran: materiallar jadvali,
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
} from "lucide-react"
import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { createPortal } from "react-dom"
import { renderToStaticMarkup } from "react-dom/server"
import { toast } from "sonner"
import {
  type CutmapHole,
  type CutmapInstanceState,
  type CutmapMaterial,
  OrdersService,
  TerminalService,
} from "@/client"
import { QueryError } from "@/components/Common/QueryError"
import { PartCard } from "@/components/Terminal/PartCard"
import {
  type Sheet,
  type SheetPart,
  SheetSvg,
} from "@/components/Terminal/SheetSvg"
import { TBtn } from "@/components/Terminal/TBtn"
import {
  useCancelLabel,
  usePrintLabel,
} from "@/components/Terminal/usePrintLabel"
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

// `SheetPart`/`Sheet` — SheetSvg dan (ikkalasi bir xil yoyilgan listni ko'radi).
// `rover` materialda ham bor: hamma listi roverniki bo'lgan material.
type Material = Omit<CutmapMaterial, "sheets"> & {
  sheets: Sheet[]
  rover?: boolean
}

const getCutmapQueryOptions = (orderId: number, admin: boolean) =>
  queryOptions({
    queryKey: [admin ? "admin" : "terminal", "cutmap", orderId],
    queryFn: async () =>
      (
        await (admin
          ? OrdersService.readOrderCutmap({ path: { order_id: orderId } })
          : TerminalService.readTerminalCutmap({ path: { order_id: orderId } }))
      ).data,
    refetchInterval: 60_000,
  })

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`)
}

/** Barcha kesish xaritalarini chop etish: har xarita tepasida
 * "Material nomi | №1 — 2750 × 1830 mm × 2 list" sarlavha, har list o'z sahifasida. */
function printAllMaps(
  orderNumber: string,
  materials: Material[],
  holes: Record<string, CutmapHole>,
  instancesByCell: Map<string, CutmapInstanceState[]>,
) {
  const w = window.open("", "_blank", "width=1000,height=800")
  if (!w) {
    toast.error("Brauzer yangi oynani blokladi — popup'ga ruxsat bering")
    return
  }
  const blocks = materials
    .flatMap((m: Material) =>
      m.sheets.map(
        (s) => `
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

/** Barmoq bilan SURIB gorizontal aylantirish.
 *
 * Tsex monoblokida sichqoncha yo'q — ingichka scrollbar'ni tortish qo'lqopda
 * deyarli imkonsiz, shuning uchun kartochkalar ustidan surish yagona tabiiy
 * harakat. Qatorga `touch-pan-y` qo'yilgan: vertikal aylantirishni brauzer
 * o'zi bajaradi, gorizontalini esa shu hook — ikkalasi bir-biriga xalaqit
 * bermaydi va qo'sh aylantirish bo'lmaydi.
 *
 * Bosish bilan aralashmaydi: 8px dan ko'p surilsa bu SURISH deb hisoblanadi
 * va keyingi `click` yutiladi, aks holda material tasodifan almashardi.
 */
function useDragScroll() {
  const ref = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; left: number; id: number } | null>(null)
  const surildi = useRef(false)

  return {
    ref,
    props: {
      onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => {
        const el = ref.current
        if (!el) return
        surildi.current = false
        drag.current = { x: e.clientX, left: el.scrollLeft, id: e.pointerId }
      },
      onPointerMove: (e: React.PointerEvent<HTMLDivElement>) => {
        const el = ref.current
        const d = drag.current
        if (!el || !d || e.pointerId !== d.id) return
        const dx = e.clientX - d.x
        if (!surildi.current && Math.abs(dx) < 8) return
        surildi.current = true
        el.scrollLeft = d.left - dx
      },
      onPointerUp: () => {
        drag.current = null
      },
      onPointerCancel: () => {
        drag.current = null
      },
      onPointerLeave: () => {
        drag.current = null
      },
      // Surishdan keyingi bosishni yutamiz — barmoq material tugmasi ustida
      // uzilsa, surish tasodifan tanlovga aylanardi.
      onClickCapture: (e: React.MouseEvent) => {
        if (!surildi.current) return
        e.preventDefault()
        e.stopPropagation()
        surildi.current = false
      },
    },
  }
}

export function CutmapView({
  orderId,
  onBack,
  admin = false,
  registerPrint,
  statsContainer,
  toolbarContainer,
  focusPartKey,
  postCode = "ARRA",
}: {
  orderId: number
  onBack: () => void
  admin?: boolean
  /** Qaysi post ochgan. Listning EGASI marshrutdan aniqlanadi (giyotina kesimi
   *  listni chetdan chetgacha kesadi — bitta katakni chetlab o'tib bo'lmaydi,
   *  ya'ni list yo butunlay arraniki, yo butunlay roverniki):
   *  ARRA — roverning listlari xira va yozuv bilan; ROVER — faqat o'ziniki. */
  postCode?: string
  /** Sahifa tepasidagi "PDF / Chop etish" tugmasi shu funksiyani chaqiradi (barcha xaritalar). */
  registerPrint?: (fn: () => void) => void
  /** Material statistikasi shu elementga portal qilinadi (terminal header); yo'q bo'lsa xarita panelida qoladi */
  statsContainer?: HTMLElement | null
  /** Toolbar tugmalari shu elementga portal qilinadi (terminal chap ustuni); yo'q bo'lsa o'z ustunida */
  toolbarContainer?: HTMLElement | null
  /** Matritsadan sakrash: shu kalitli detalning listi ochilib, katakchasi belgilanadi */
  focusPartKey?: string
}) {
  const { data, isLoading, isError, refetch } = useQuery(
    getCutmapQueryOptions(orderId, admin),
  )
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
  // Material qatorini barmoq bilan surib aylantirish
  const matDrag = useDragScroll()
  // GibLab toolbar zoom API (SheetSvg ro'yxatdan o'tkazadi)
  const zoomApi = useRef<{
    zin: () => void
    zout: () => void
    reset: () => void
  } | null>(null)
  // Barqaror identifikatsiya: SheetSvg'dagi ro'yxatga olish effekti
  // `[registerZoom]` ga bog'langan — inline arrow bo'lsa har renderda qayta
  // ishlardi.
  const registerZoom = useCallback(
    (api: NonNullable<typeof zoomApi.current>) => {
      zoomApi.current = api
    },
    [],
  )

  // Chap qatordagi Chop etish: belgilangan detalning navbatdagi nusxasi
  // to'g'ridan-to'g'ri GoDEX navbatiga ketadi (dialog yo'q)
  const printMutation = usePrintLabel("cutmap")
  const cancelMutation = useCancelLabel()
  // Atxot cheki: WasteItem id `waste_items` dan atx raqami orqali topiladi
  const queryClient = useQueryClient()
  const wastePrint = useMutation({
    mutationFn: async (wasteId: number) =>
      (
        await TerminalService.printWasteItemLabel({
          path: { waste_id: wasteId },
        })
      ).data,
    onSuccess: (r) => {
      toast.success(r.message)
      setSelected(null)
    },
    onError: handleError,
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["terminal", "cutmap"] }),
  })
  // Cheki chiqarilgan qoldiqlar (atx raqamlari) — SVG katakni yashil qiladi
  const wastePrinted = useMemo(() => {
    const out = new Set<number>()
    for (const w of data?.waste_items ?? []) {
      if (!w.label_printed_at) continue
      const m = w.qr_text.match(/-(\d+)$/)
      if (m) out.add(Number(m[1]))
    }
    return out
  }, [data?.waste_items])
  const wasteCancel = useMutation({
    mutationFn: async (wasteId: number) =>
      (
        await TerminalService.cancelWasteItemLabel({
          path: { waste_id: wasteId },
        })
      ).data,
    onSuccess: (r) => {
      toast.success(r.message)
      setSelected(null)
    },
    onError: handleError,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["terminal", "cutmap"] })
      // Admin ko'rinishi boshqa kalitda — texnolog bekor qilganda u ham
      // yangilanishi kerak (chek chiqarish adminda yo'q, bekor qilish bor).
      queryClient.invalidateQueries({ queryKey: ["admin", "cutmap"] })
    },
  })
  const wasteItemFor = (part: SheetPart | null) =>
    part?.atx
      ? ((data?.waste_items ?? []).find(
          (w) => w.qr_text.endsWith(`-${part.atx}`) && w.sheet_no === sheet?.no,
        ) ??
        (data?.waste_items ?? []).find((w) =>
          w.qr_text.endsWith(`-${part.atx}`),
        ) ??
        null)
      : null

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
    const mats: Material[] = (data?.model?.materials ?? []).map((m) => {
      let disp = 0
      const sheets: Sheet[] = (m.sheets ?? []).flatMap((s) => {
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
    })
    return { expMaterials: mats, cellInsts: view }
  }, [data, instancesByCell])

  // Listning egasi: hamma katagi marshrutida ARRA qadami YO'Q detallardan iborat
  // bo'lsa — list roverniki (frezer butun listni o'zi kesadi).
  const materials: Material[] = useMemo(() => {
    const isRover = (s: Sheet) => {
      const cells = s.parts.filter((p) => !p.waste)
      if (!cells.length) return false
      const insts = cells.flatMap(
        (p) => cellInsts.get(`${s.no}:${p.cell}`) ?? [],
      )
      return insts.length > 0 && insts.every((i) => i.arra_route === false)
    }
    const mats: Material[] = expMaterials.map((m) => {
      const sheets = m.sheets.map((s) => ({ ...s, rover: isRover(s) }))
      return {
        ...m,
        sheets,
        rover: sheets.length > 0 && sheets.every((s) => s.rover),
      }
    })
    // Admin (texnolog) rejasini fayl tartibida ko'radi: uning "o'z listi" degan
    // tushunchasi yo'q, marshrutni matritsa va nostandart tabidan tekshiradi.
    if (admin) return mats
    // Roverchi FAQAT o'z listlarini ko'radi
    if (postCode === "ROVER") {
      return mats
        .map((m) => ({ ...m, sheets: m.sheets.filter((s) => s.rover) }))
        .filter((m) => m.sheets.length > 0)
    }
    // Arrachida: O'ZINIKI OLDINDA. Materiallar fayl tartibida keladi va rover
    // materiali birinchi bo'lishi mumkin (prodda aynan shunday) — u holda xarita
    // ochilishi bilan birinchi ko'rinadigan narsa begona listlar bo'lardi.
    // Har material ichida ham o'z listlari tepada.
    return mats
      .map((m) => ({
        ...m,
        sheets: [...m.sheets].sort((a, b) => Number(a.rover) - Number(b.rover)),
      }))
      .sort((a, b) => Number(a.rover) - Number(b.rover))
  }, [expMaterials, cellInsts, postCode, admin])

  // Matritsadan kelgan "xaritada ko'rsat" sakrashi: ma'lumot kelgach detalning
  // birinchi katakchasini topib, o'sha material + listni ochamiz va belgilaymiz.
  // BIR MARTA: aks holda har refetch (60s interval, fokus) foydalanuvchi qaysi
  // listga o'tgan bo'lsa ham uni qaytarib uloqtirardi.
  // Kalit BO'YICHA: har refetch (60s, fokus) sakrashni qaytarmasin, lekin
  // operator boshqa detalga sakrasa qayta ishlasin — roverchi ro'yxatdan
  // ketma-ket bir nechta detalni xaritada ochib ko'radi.
  const focusApplied = useRef<string | undefined>(undefined)
  useEffect(() => {
    if (!focusPartKey || !data?.model || focusApplied.current === focusPartKey)
      return
    for (let mi = 0; mi < materials.length; mi++) {
      const shs = materials[mi].sheets ?? []
      for (let si = 0; si < shs.length; si++) {
        const hit = (shs[si].parts ?? []).find(
          (p) => !p.waste && p.key === focusPartKey,
        )
        if (hit) {
          focusApplied.current = focusPartKey
          setMaterialIdx(mi)
          setSheetIdxRaw(si)
          setMarkedCell(hit.cell)
          return
        }
      }
    }
    // Topilmadi: sababini aytamiz, lekin bayroqni baribir yozamiz —
    // aks holda har refetch (60s) shu toastni qayta chiqarardi.
    focusApplied.current = focusPartKey
    toast.error("Bu detal kesish xaritasida joylashtirilmagan")
  }, [focusPartKey, data, materials])

  if (isLoading) return <Skeleton className="h-full w-full" />
  // So'rov yiqilsa `data` undefined qoladi — quyidagi TEMPLATE xabari operatorga
  // "fayl optimizatsiya qilinmagan" deb YOLG'ON sabab ko'rsatardi. Xato alohida.
  if (isError)
    return (
      <div className="flex h-full items-center justify-center p-4">
        <QueryError onRetry={() => refetch()} />
      </div>
    )
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

  const model = data.model
  const material = materials[materialIdx]
  const sheets: Sheet[] = material?.sheets ?? []
  const sheet = sheetIdx !== null ? sheets[sheetIdx] : undefined
  const holes = model.holes ?? {}

  const sheetDone = (s: Sheet) => {
    const cells = s.parts.filter((p) => !p.waste)
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
  // Belgilangan katak — DETAL yoki QOLDIQ. Ikkalasi bir xil oqimdan o'tadi:
  // bir marta bosish belgilaydi, chap qatordagi "Chop etish" chiqaradi, ikki
  // marta bosish kartochkani ochadi (bekor qilish o'sha yerda).
  const markedPart =
    sheet && markedCell !== null
      ? sheet.parts.find((p) => p.cell === markedCell)
      : undefined
  const markedWaste = markedPart?.waste ? markedPart : undefined
  const markedWasteItem = wasteItemFor(markedWaste ?? null)
  const markedInsts =
    sheet && markedPart && !markedPart.waste
      ? (cellInsts.get(`${sheet.no}:${markedPart.cell}`) ?? [])
      : []
  // Fallback YO'Q: hammasi chiqarilgan bo'lsa qayta chop etilmaydi —
  // avval chek bekor qilinadi (dublikat chek oqimni buzadi)
  const nextInstance = markedInsts.find((i) => !isCut(i))

  // Reja ko'rsatkichlari (atxot, rez, to'ldirish, arra, tirim) hech qayerda
  // chizilmaydi (2026-09-03 qarori) — operator ham, texnolog ham ular bilan ish qilmaydi.
  // Header info: list nomi (ochiq bo'lsa) — bitta portalda
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
        tone={
          nextInstance || (markedWasteItem && !markedWasteItem.label_printed_at)
            ? "success"
            : "default"
        }
        // Katak belgilangan bo'lsa tugma ISHLAYDI. Ilgari nusxasi bog'lanmagan
        // katakda u jimgina o'chib qolardi: arrachi bosadi, hech narsa
        // bo'lmaydi, sabab ham aytilmaydi — 17" kioskda bu "chek chiqmayapti"
        // bo'lib ko'rinardi va operator sababini topa olmasdi.
        disabled={
          markedCell === null || printMutation.isPending || wastePrint.isPending
        }
        onClick={() => {
          // QOLDIQ — detal bilan bir xil qoida: chiqarilmagan bo'lsa chiqadi,
          // chiqarilgan bo'lsa avval kartochkadan bekor qilinadi.
          if (markedWaste) {
            if (!markedWasteItem)
              return toast.error(
                "Bu qoldiq ro'yxatga olinmagan (eski yuklama) — project faylni qayta yuklang.",
              )
            if (markedWasteItem.label_printed_at)
              return toast.error(
                "Bu qoldiq chiqarilgan. Qaytadan chiqarish uchun uni ikki marta bosib chekni bekor qiling.",
              )
            return wastePrint.mutate(markedWasteItem.id)
          }
          return nextInstance
            ? printMutation.mutate(nextInstance.instance_id)
            : toast.error(
                markedInsts.length
                  ? "Bu detal chiqarilgan. Qaytadan chiqarish uchun detalni ikki marta bosib chekni bekor qiling."
                  : "Bu detalning QR'i yo'q — chek chiqmaydi. Texnologga ayting.",
              )
        }}
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
        {/* Shart `sheet` bo'yicha, `sheetIdx` bo'yicha EMAS: material almashsa
            yoki refetch listlar sonini kamaytirsa indeks eskirib qolishi mumkin —
            o'shanda ro'yxatga qaytamiz, oq ekran bilan yiqilmaymiz. */}
        {!sheet ? (
          /* Jadval sahifasi: material tablar + list grid (GibLab #matlist + #grid) */
          <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border bg-white p-4">
            {/* Material tablar: bitta qator, ko'paysa gorizontal swipe (grid joyini yemaydi) */}
            <div
              ref={matDrag.ref}
              {...matDrag.props}
              // `select-none`: surganda material nomi ko'karib belgilanib qolardi
              // (kioskda matn tanlashning umuman ma'nosi yo'q).
              // `touch-pan-y`: vertikal aylantirish brauzerda qoladi, gorizontalini
              // `useDragScroll` bajaradi.
              className="mb-3 flex touch-pan-y cursor-grab select-none items-center gap-2 overflow-x-auto pb-1 active:cursor-grabbing"
            >
              {materials.map((m: Material, i: number) => {
                const mdone = m.sheets.filter(sheetDone).length
                const active = i === materialIdx
                // Begona material — o'ziniki emas. Xiralashtirmaymiz (17" kioskda
                // kontrast birinchi bo'lib yo'qoladi) va yangi rang qo'shmaymiz
                // (ekranda yashil/binafsha/ko'k allaqachon band): tartib va MATN
                // ishlaydi — o'ziniki oldinda, begonasida hisoblagich o'rniga so'z.
                const foreign = !admin && m.rover && postCode !== "ROVER"
                const firstForeign =
                  foreign && i > 0 && !materials[i - 1]?.rover
                return (
                  <div
                    key={m.name}
                    className={`flex shrink-0 items-center ${firstForeign ? "ml-4 border-l pl-4" : ""}`}
                  >
                    <Button
                      variant={active ? "default" : "outline"}
                      className="h-12 max-w-xs px-4 text-base"
                      onClick={() => setMaterialIdx(i)}
                    >
                      <span className="truncate">{m.name}</span>
                      <span
                        className={`ml-1 shrink-0 ${active ? "opacity-80" : "text-muted-foreground"} ${foreign ? "text-sm" : "num text-xs"}`}
                      >
                        {foreign ? "roverda" : `${mdone}/${m.sheets.length}`}
                      </span>
                    </Button>
                  </div>
                )
              })}
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {sheets.map((s: Sheet, i: number) => {
                // Aralash material — texnolog xatosi bo'lishi mumkin (bir listda
                // ikki xil egalik bo'lmaydi, lekin bir MATERIALDA bo'lishi mumkin)
                const mixedOwners =
                  !admin &&
                  postCode !== "ROVER" &&
                  sheets.some((x) => x.rover) &&
                  sheets.some((x) => !x.rover)
                const done = sheetDone(s)
                const foreign = !admin && s.rover && postCode !== "ROVER"
                // Ajratuvchi FAQAT aralash materialda va FAQAT begona guruh
                // tepasida: o'ziniki oldinda turgani uchun "sizning listlaringiz"
                // deb takrorlash ortiqcha — chiziqdan tepasi baribir uniki.
                const divider = mixedOwners && foreign && !sheets[i - 1]?.rover
                return (
                  <Fragment key={s.no}>
                    {divider && (
                      <div className="col-span-full mt-2 flex items-baseline gap-2 border-t pt-3 text-base text-muted-foreground">
                        Roverda kesiladi
                        <span className="num text-sm">
                          {sheets.filter((x) => x.rover).length}
                        </span>
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => setSheetIdx(i)}
                      className={`rounded-xl border-2 px-4 py-3 text-left outline-none transition-all hover:border-primary focus-visible:ring-[3px] focus-visible:ring-ring/50 active:scale-[0.98] active:border-primary ${
                        done && !foreign
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
                  </Fragment>
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
            {/* Ataylab ochgan — qichqirish shart emas, bitta jumla yetadi.
                Chek baribir bloklangan (backend aniq xato qaytaradi). */}
            {!admin && sheet?.rover && postCode !== "ROVER" && (
              <div className="absolute inset-x-0 top-0 z-10 bg-white/90 px-4 py-1.5 text-center text-base text-muted-foreground">
                Bu listni rover kesadi
              </div>
            )}
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
                // Terminalda ikki marta bosish (yoki uzoq bosish) detal
                // kartochkasini ochadi — adminda u bir marta bosishda ochiladi.
                // Chekni bekor qilish tugmasi kartochka ICHIDA: jest
                // buzg'unchi amalni o'zi bajarmaydi.
                onOpenPart={admin ? undefined : setSelected}
                wastePrinted={wastePrinted}
                selectedCell={markedCell}
                registerZoom={registerZoom}
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
        holes={holes}
        wasteItem={wasteItemFor(selected)}
        onCancelWaste={(id) => wasteCancel.mutate(id)}
        wasteCancelling={wasteCancel.isPending}
        // Terminalda bekor qilish TASDIQ orqali o'tadi: tsexda qo'lqopdagi
        // barmoq bilan xato bosish adminning stoliga qaraganda ancha ehtimolli.
        // Admin uchun `undefined` — u avvalgidek to'g'ridan-to'g'ri bekor qiladi.
        onCancelRequest={
          admin
            ? undefined
            : (inst) => {
                if (!selected) return
                setSelected(null)
                setCancelTarget({
                  num: selected.num ?? selected.id,
                  name: selected.name,
                  qr_text: inst.qr_text,
                  instance_id: inst.instance_id,
                })
              }
        }
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
