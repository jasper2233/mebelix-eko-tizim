// PRISADKA post sahifasi: buyurtmaning prisadka detallari ro'yxati,
// har detalning SCX fayllari. "Hammasini yuklab olish" barcha SCX'ni BIR MARTA
// tanlangan papkaga yozadi (File System Access API) — papka IndexedDB'da
// saqlanadi, keyingi safar so'ralmaydi. SKAN esa hech qanday fayl yuklamaydi:
// yuklash faqat shu tugma orqali, operator xohlaganda.

import { useQuery } from "@tanstack/react-query"
import { HardDriveDownload, Map as MapIcon, Printer } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { toast } from "sonner"

import type { PrisadkaInstance, PrisadkaPartRow } from "@/client"
import { TerminalService } from "@/client"
import { QueryError } from "@/components/Common/QueryError"
import { PostHeader } from "@/components/Terminal/PostHeader"
import { PostProgress } from "@/components/Terminal/PostProgress"
import { Serial } from "@/components/Terminal/Serial"
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
import { useScanFlash } from "@/hooks/useScanFlash"
import { formatSize } from "@/lib/mes"
import {
  dirSupported,
  getSavedDir,
  pickDir,
  projectFolder,
  saveScxToDir,
  scxFileUrl,
} from "@/lib/scxDir"
import { cn } from "@/lib/utils"

/** Bu nusxaga chek chiqarish mumkinmi — ROVER tugmasi va PRISADKA chipida
 *  qoida bitta: hali bajarilmagan, cheki chiqmagan, marshruti arradan boshlanmagan */
const canPrintInstance = (p: PrisadkaPartRow, i: PrisadkaInstance) =>
  !i.done && !i.label_printed && !p.arra_route

/** Qator pog'onasi: 0 — yarim (boshlangan, tugamagan), 1 — boshlanmagan, 2 — tugagan */
const partTier = (p: { done: number; total: number }) =>
  p.done >= p.total ? 2 : p.done > 0 ? 0 : 1

/** ROVER qator kaliti — QADAM + NUSXA: nostandart marshrutda detal ROVER'ni ikki marta olishi
 *  mumkin ([7,6,7]); yolg'iz `instance_id` ikki qatorga bir xil key/DOM id berardi. */
const instKey = (r: { p: PrisadkaPartRow; i: PrisadkaInstance }) =>
  `${r.p.route_id}:${r.i.instance_id}`

export function PrisadkaView({
  orderId,
  onBack,
  showScx = true,
  toolbarContainer,
  onShowOnMap,
}: {
  orderId: number
  onBack: () => void
  /** ROVER: SCX fayllar kerak emas — yuklab olish/Papka va fayl nomlari yashirin */
  showScx?: boolean
  /** ROVER: detalni kesish xaritasida ochish (faqat o'z listidagi detallarda —
   *  arradan kelgani rover xaritasida umuman yo'q) */
  onShowOnMap?: (partCode: string) => void
  /** ROVER Chop etish tugmasi terminalning umumiy chap ustuniga (Qulflash
   * ustiga) portal qilinadi — alohida ikkinchi ustun ochilmasin */
  toolbarContainer: HTMLElement | null
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["terminal", "prisadka", orderId],
    queryFn: async () =>
      (
        await TerminalService.readTerminalPrisadka({
          path: { order_id: orderId },
        })
      ).data,
    refetchInterval: 30_000,
  })
  // ROVER'da jarayon shu postdan boshlanishi mumkin (marshrutda ARRA yo'q) —
  // QR chek shu yerdan chiqariladi; keyin skan bilan ish yakunlanadi
  const printLabel = usePrintLabel("prisadka")
  const cancelLabel = useCancelLabel()
  // Noto'g'ri chiqarilgan chek: uzoq bosish (~600ms) + tasdiq — ARRA xaritasidagi
  // bilan bir xil imo-ishora, operator bitta odatni o'rganadi. Tugma qilinmadi:
  // qatorlar tor va tasodifiy bosish chop etilgan chekni o'chirib yuborardi.
  const [cancelTarget, setCancelTarget] = useState<{
    instance_id: number
    qr_text: string
    name: string
  } | null>(null)
  const pressRef = useRef<number | null>(null)
  const holdStart = (t: {
    instance_id: number
    qr_text: string
    name: string
  }) => {
    pressRef.current = window.setTimeout(() => setCancelTarget(t), 600)
  }
  /** Chek SHU postda chiqarilganmi — bekor qilish huquqi shunga bog'liq */
  const ownLabel = (p: { arra_route?: boolean | null }) =>
    Boolean(onShowOnMap) && !p.arra_route
  const holdEnd = () => {
    if (pressRef.current !== null) window.clearTimeout(pressRef.current)
    pressRef.current = null
  }
  // null = yuklanmayapti; son = nechta fayl saqlandi (tugmada jonli 12/69)
  const [progress, setProgress] = useState<number | null>(null)
  // Saqlangan SCX papkasining NOMI tugmada ko'rinadi: operator fayllar
  // qayerga tushishini ko'rib tursin («Papka» yolg'iz o'zi nima ekanini aytmasdi)
  const [dirName, setDirName] = useState<string | null>(null)
  useEffect(() => {
    if (!dirSupported()) return
    getSavedDir()
      .then((d) => setDirName(d?.name ?? null))
      .catch(() => setDirName(null))
  }, [])
  // ROVER rejimi: qator (nusxa) tanlanadi, chop etish chapdagi katta tugmada
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // PrisadkaPartRow'da files sxemada ixtiyoriy — bir joyda normallashtiramiz
  const parts = (data?.parts ?? []).map((p) => ({ ...p, files: p.files ?? [] }))

  // Oxirgi skan bo'lgan qator keyingi skangacha ajralib turadi + avto-scroll
  // Kalit `route_id` — takroriy qadamda `part_id` ikki qatorni bitta kalitga
  // siqib, har refetchda yolg'on "skan bo'ldi" xatcho'pini berardi
  const flashId = useScanFlash(
    parts,
    (p) => p.route_id,
    (p) => p.done,
    "pv-row-",
  )

  // ROVER: har jismoniy nusxa alohida qator
  const instRows = parts.flatMap((p) =>
    (p.instances ?? []).map((i) => ({ p, i })),
  )
  const instFlash = useScanFlash(
    instRows,
    instKey,
    (r) => Number(r.i.done),
    "pv-inst-",
  )

  if (isLoading) return <Skeleton className="h-full w-full" />
  // Xatoni yutib bo'lmaydi: aks holda bo'sh `parts` "detal yo'q" degan
  // YOLG'ON xabarga aylanadi va operator qayta urinish yo'lini ko'rmaydi
  if (isError) return <QueryError onRetry={() => refetch()} />
  const allFiles = parts.flatMap((p) => p.files)
  const totDone = parts.reduce((s, p) => s + p.done, 0)
  const totReq = parts.reduce((s, p) => s + p.total, 0)

  const downloadAll = async () => {
    if (!allFiles.length) return
    setProgress(0)
    try {
      if (dirSupported()) {
        // BIR MARTA so'raladi: saqlangan papka bo'lsa ruxsatini yangilaymiz,
        // bo'lmasa tanlash dialogi ochiladi va tanlov eslab qolinadi
        let dir = await getSavedDir()
        if (!dir) dir = await pickDir()
        if (!dir) return // bekor qilindi
        // Har proyekt o'z papkasiga: "1007 Yangibozor" kabi — fayllar aralashmaydi
        // `projectFolder` faqat taqiqlangan belgilarni tozalaydi — natija
        // bo'sh qolishi mumkin (" " kabi nom), bo'sh nom bilan papka ochilmaydi
        const folder =
          projectFolder(data?.project_name || data?.order_number || "scx") ||
          "scx"
        const sub = await dir.getDirectoryHandle(folder, { create: true })
        let ok = 0
        for (const f of allFiles) {
          try {
            await saveScxToDir(sub, f.id, f.filename)
            ok++
            setProgress(ok)
          } catch {
            /* bittasi yiqilsa qolganlari davom etadi */
          }
        }
        if (ok === allFiles.length)
          toast.success(`${ok} ta SCX "${dir.name}/${folder}" ga saqlandi`)
        else
          toast.error(
            `${ok}/${allFiles.length} saqlandi — qolganlarini qayta urining.`,
          )
      } else {
        // Eski brauzer: oddiy Downloads
        let n = 0
        for (const f of allFiles) {
          const a = document.createElement("a")
          a.href = scxFileUrl(f.id)
          a.download = ""
          a.click()
          n++
          setProgress(n)
          await new Promise((r) => setTimeout(r, 300))
        }
        // `<a download>` natijani qaytarmaydi: server 404 bersa yoki brauzer
        // yuklashni bloklasa ham JS bilmaydi — shu sabab "yuklab olindi" deb
        // yolg'on va'da bermaymiz, operatorni yuklamalar ro'yxatiga yo'llaymiz
        toast.success(
          `${allFiles.length} ta SCX yuklash boshlandi — brauzer yuklamalarini tekshiring`,
        )
      }
    } catch (e) {
      // Saqlangan papka o'chirilgan/ko'chirilgan yoki flesh olib qo'yilgan —
      // tugma jimgina qaytmasin, operator papkani qayta tanlashi kerakligini bilsin
      if ((e as Error)?.name !== "AbortError")
        toast.error(
          "SCX papkasini ochib bo'lmadi — Papka tugmasi bilan qayta tanlang",
        )
    } finally {
      setProgress(null)
    }
  }

  // ROVER rejimi: har nusxa ALOHIDA qator; qator tanlanadi, chop etish
  // chapdagi katta tugmada (ARRA terminal bilan bir xil ishlash naqshi —
  // sensor uchun katta nishon, chip ichidagi mayda tugma emas)
  if (!showScx) {
    const sel = instRows.find((r) => instKey(r) === selectedId) ?? null
    const canPrint = !!sel && canPrintInstance(sel.p, sel.i)
    const sorted = [...instRows].sort(
      (a, b) =>
        Number(a.i.done) - Number(b.i.done) ||
        a.i.qr_text.localeCompare(b.i.qr_text),
    )
    const printBtn = (
      <TBtn
        label="Chop etish"
        tone={canPrint ? "success" : "default"}
        disabled={!canPrint || printLabel.isPending}
        onClick={() => sel && printLabel.mutate(sel.i.instance_id)}
      >
        <Printer />
      </TBtn>
    )
    return (
      <div className="flex h-full min-h-0 gap-3">
        {/* Tugma terminalning umumiy chap ustunida, Qulflash tepasida turadi */}
        {toolbarContainer && createPortal(printBtn, toolbarContainer)}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col rounded-xl border bg-white">
          <PostHeader
            className="flex-wrap"
            onBack={onBack}
            orderNumber={data?.order_number}
            projectName={data?.project_name}
          >
            <PostProgress className="ml-auto" done={totDone} total={totReq} />
          </PostHeader>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="w-full text-base">
              <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
                <tr>
                  <th className="px-4 py-2.5">Detal ID</th>
                  <th className="px-4 py-2.5">Nomi</th>
                  <th className="px-4 py-2.5">O'lchami</th>
                  <th className="px-4 py-2.5 text-right">
                    Holat
                    <span className="block whitespace-nowrap text-2xs font-medium normal-case tracking-normal">
                      ✓ bajarildi · rover kesadigani — chek chiqishi bilan ·
                      arradan kelgani — skan bilan
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => {
                  const { p, i } = r
                  const key = instKey(r)
                  return (
                    <tr
                      key={key}
                      id={`pv-inst-${key}`}
                      onClick={() => setSelectedId(key)}
                      // ARRA xaritasi bilan bir xil imo-ishora: ikki marta bosish
                      // yoki uzoq bosish → chekni bekor qilish dialogi. Alohida
                      // tugma yo'q — dialogning o'zida «Ha, bekor qilinsin» bor.
                      onDoubleClick={() =>
                        i.label_printed &&
                        ownLabel(p) &&
                        setCancelTarget({
                          instance_id: i.instance_id,
                          qr_text: i.qr_text,
                          name: p.name,
                        })
                      }
                      // Uzoq bosish chekni bekor qiladi — FAQAT o'z postida chiqarilganida;
                      // ilgari roverchi arrachining kesish skanini ham qaytara olardi.
                      onPointerDown={() =>
                        i.label_printed &&
                        ownLabel(p) &&
                        holdStart({
                          instance_id: i.instance_id,
                          qr_text: i.qr_text,
                          name: p.name,
                        })
                      }
                      onPointerUp={holdEnd}
                      onPointerLeave={holdEnd}
                      onPointerCancel={holdEnd}
                      className={cn(
                        "cursor-pointer border-b last:border-0",
                        i.done && "bg-green-50",
                        selectedId === key &&
                          "bg-primary/10 ring-2 ring-inset ring-primary",
                        // Xatcho'p tanlov bilan birga ko'rinadi — boshqa o'q
                        instFlash === key && "border-l-4 border-l-primary",
                      )}
                    >
                      <td className="px-4 py-3 text-lg font-semibold">
                        <Serial code={i.qr_text} />
                        {/* Marshruti roverdan boshlangan detal — uni ROVER o'z
                          listidan kesadi. Ikonka bosilsa xarita o'sha katak
                          belgilangan holda ochiladi: 20 detalli listda uni
                          qidirib topguncha ancha vaqt ketardi. Ikonkaning
                          BORLIGI ayni paytda "chek shu yerda chiqadi" degani —
                          arradan kelgan detalda u yo'q (`ownLabel` bilan bir
                          xil shart: uzoq bosib bekor qilish ham shunga bog'liq). */}
                        {ownLabel(p) && (
                          <button
                            type="button"
                            title="Kesish xaritasida ko'rsatish"
                            aria-label={`${i.qr_text} — kesish xaritasida ko'rsatish`}
                            className="ml-2 inline-flex size-10 items-center justify-center rounded-md align-middle text-muted-foreground hover:bg-muted hover:text-primary"
                            onClick={(e) => {
                              e.stopPropagation()
                              onShowOnMap?.(p.code)
                            }}
                          >
                            <MapIcon className="size-5" />
                          </button>
                        )}
                      </td>
                      <td className="max-w-[240px] truncate px-4 py-3">
                        {p.name}
                      </td>
                      <td className="num whitespace-nowrap px-4 py-3 text-sm">
                        {formatSize(p.length, p.width, p.thickness)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {/* Holat: arradan kelgan detalda IKKILIK (chek arrada
                          chiqqan, bu yerda faqat skan). ROVER O'ZI KESADIGAN
                          detalda uch bosqich — chek yo'q → chek chiqarilgan →
                          ✓: chek shu tugma bilan chiqadi, chiqqanini ko'rmasa
                          operator qatorni bosib o'chiq «Chop etish»ga qarab
                          qolardi (sababi ko'rinmasdi) yoki ikkinchi chek so'rardi. */}
                        <span
                          className={cn(
                            "rounded-md px-2.5 py-1 text-sm font-bold",
                            i.done
                              ? "bg-green-600 text-white"
                              : ownLabel(p) && i.label_printed
                                ? "bg-amber-100 text-amber-800"
                                : "bg-muted text-muted-foreground",
                          )}
                        >
                          {i.done
                            ? "✓ Bajarildi"
                            : ownLabel(p)
                              ? i.label_printed
                                ? "Chek chiqarilgan"
                                : "Chek yo'q"
                              : "Bajarilmagan"}
                        </span>
                      </td>
                    </tr>
                  )
                })}
                {!sorted.length && (
                  <tr>
                    <td
                      colSpan={4}
                      className="h-32 text-center text-muted-foreground"
                    >
                      Bu buyurtmada bu postga detal yo'q
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        {/* Long press tasdiq dialogi — ARRA xaritasidagi bilan bir xil matn */}
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
                {cancelTarget.name}{" "}
                <span className="num text-muted-foreground">
                  ({cancelTarget.qr_text})
                </span>
                <br />
                Detal chop etilmagan holatga qaytadi, bosqich hisobi tiklanadi.
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
                loading={cancelLabel.isPending}
                onClick={() => {
                  if (!cancelTarget) return
                  cancelLabel.mutate(cancelTarget.instance_id, {
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

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border bg-white">
      <PostHeader
        className="flex-wrap"
        onBack={onBack}
        orderNumber={data?.order_number}
        projectName={data?.project_name}
      >
        <PostProgress className="ml-auto" done={totDone} total={totReq} />
        <div className="flex items-center gap-2">
          {/* Papka tugmasi YO'Q: papka birinchi yuklashda bir marta so'raladi
              va eslab qolinadi — operator faqat yuklab oladi. Tanlangan papka
              nomi xira izoh (qayerga tushishini bilsin). Almashtirish —
              brauzer sayt ma'lumotini tozalash (admin). */}
          {dirName && (
            <span
              className="max-w-56 truncate text-sm text-muted-foreground"
              title="SCX fayllar shu papkaga tushadi"
            >
              Papka: {dirName}
            </span>
          )}
          <LoadingButton
            className="h-12 px-5 text-base font-bold"
            loading={progress !== null}
            disabled={!allFiles.length}
            onClick={downloadAll}
          >
            {progress !== null ? (
              <span className="num">
                Yuklanmoqda… {progress}/{allFiles.length}
              </span>
            ) : (
              <>
                {/* «Hammasini yuklab olish» NIMANI va QAYERGA aytmasdi: SCX
                    fayllar stanok o'qiydigan papkaga tushadi */}
                <HardDriveDownload /> SCX → papkaga ({allFiles.length})
              </>
            )}
          </LoadingButton>
        </div>
      </PostHeader>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <table className="w-full text-base">
          <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
            <tr>
              <th className="px-4 py-2.5">Kod</th>
              <th className="px-4 py-2.5">Nomi</th>
              <th className="px-4 py-2.5">O'lchami</th>
              <th className="px-4 py-2.5">
                Detal ID · SCX
                <span className="block text-2xs font-medium normal-case tracking-normal">
                  ✓ tugadi · sariq — chek chiqqan / yarim · 1/2 = skan
                </span>
              </th>
              <th className="px-4 py-2.5 text-right">
                Skanlar
                <span className="block whitespace-nowrap text-2xs font-medium normal-case tracking-normal">
                  qilingan / jami
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {/* Ish-navbat (Kromka bilan bir qoida): YARIM qolganlar tepada
                sariq, keyin boshlanmaganlar, tugaganlar (✓) pastda yashil */}
            {[...parts]
              .sort((a, b) => partTier(a) - partTier(b))
              .map((p) => {
                const finished = p.done >= p.total
                const started = !finished && p.done > 0
                return (
                  <tr
                    key={p.route_id}
                    id={`pv-row-${p.route_id}`}
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
                    <td className="max-w-[240px] truncate px-4 py-3">
                      {p.name}
                    </td>
                    <td className="num whitespace-nowrap px-4 py-3 text-sm">
                      {formatSize(p.length, p.width, p.thickness)}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {/* Har chip = bitta nusxa (nom = QR = SCX fayl nomi):
                          yashil ✓ — skan tugagan, amber — chek chiqqan (skan
                          kutilmoqda), kulrang — boshlanmagan. Marshrutida ARRA
                          bo'lmagan detalga (jarayon shu postdan boshlanadi)
                          printer tugmasi bilan QR chek shu yerdan chiqariladi */}
                      {(p.instances?.length ?? 0) > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {(p.instances ?? []).map((i) => (
                            <span
                              key={i.instance_id}
                              className={cn(
                                "num inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5",
                                i.done
                                  ? "bg-green-100 font-semibold text-green-700"
                                  : (i.scans ?? 0) > 0 || i.label_printed
                                    ? "bg-amber-100 text-amber-700"
                                    : "text-muted-foreground",
                              )}
                            >
                              <Serial code={i.qr_text} />
                              {/* Bir nusxa 2+ skan talab qilsa (per_instance) yarim
                                  yo'l ko'rinsin: «1/2» — ilgari chip faqat tugadi/
                                  tugamadi edi va «Bajarildi 1/2» ustuni «2 nusxadan
                                  1» deb o'qilardi */}
                              {i.done
                                ? " ✓"
                                : (i.need ?? 1) > 1 && (i.scans ?? 0) > 0
                                  ? ` ${i.scans}/${i.need}`
                                  : ""}
                              {canPrintInstance(p, i) && (
                                <button
                                  type="button"
                                  title="QR chek chiqarish"
                                  disabled={printLabel.isPending}
                                  onClick={() =>
                                    printLabel.mutate(i.instance_id)
                                  }
                                  className="inline-flex h-9 items-center rounded border px-2.5 text-foreground hover:bg-secondary"
                                >
                                  <Printer className="size-4" />
                                </button>
                              )}
                            </span>
                          ))}
                        </div>
                      ) : p.files.length ? (
                        // Nusxasiz fayl ro'yxati — HOLATSIZ: nusxa yo'q bo'lsa holat ham yo'q, faqat nomlar
                        <div className="flex flex-wrap gap-1 text-muted-foreground">
                          {p.files.map((f) => (
                            <span
                              key={f.id}
                              className="num rounded-sm px-1.5 py-0.5"
                            >
                              {f.filename}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={cn(
                          "num rounded-md px-2.5 py-1 text-lg font-black",
                          finished
                            ? "bg-green-600 text-white"
                            : p.done > 0
                              ? "bg-amber-100 text-amber-700"
                              : "bg-muted text-muted-foreground",
                        )}
                      >
                        {finished ? "✓" : `${p.done}/${p.total}`}
                      </span>
                    </td>
                  </tr>
                )
              })}
            {!parts.length && (
              <tr>
                <td
                  colSpan={5}
                  className="h-32 text-center text-muted-foreground"
                >
                  Bu buyurtmada prisadka detallari yo'q
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
