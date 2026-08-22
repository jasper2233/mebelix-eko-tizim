// PRISADKA post sahifasi (TZ 12.5): buyurtmaning prisadka detallari ro'yxati,
// har detalning SCX fayllari. "Hammasini yuklab olish" barcha SCX'ni BIR MARTA
// tanlangan papkaga yozadi (File System Access API) — papka IndexedDB'da
// saqlanadi, keyingi safar so'ralmaydi. SKAN esa hech qanday fayl yuklamaydi:
// yuklash faqat shu tugma orqali, operator xohlaganda.

import { useQuery } from "@tanstack/react-query"
import {
  ArrowLeft,
  FolderCog,
  HardDriveDownload,
  Map as MapIcon,
  Printer,
} from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { toast } from "sonner"

import { TerminalService } from "@/client"
import { PostProgress } from "@/components/Terminal/PostProgress"
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
  toolbarContainer?: HTMLElement | null
}) {
  const { data, isLoading } = useQuery({
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
  // ROVER rejimi: qator (nusxa) tanlanadi, chop etish chapdagi katta tugmada
  const [selectedId, setSelectedId] = useState<number | null>(null)

  // PrisadkaPartRow'da files sxemada ixtiyoriy — bir joyda normallashtiramiz
  const parts = useMemo(
    () => (data?.parts ?? []).map((p) => ({ ...p, files: p.files ?? [] })),
    [data],
  )

  // Oxirgi skan bo'lgan qator keyingi skangacha ajralib turadi + avto-scroll
  const flashId = useScanFlash(
    parts,
    (p) => p.part_id,
    (p) => p.done,
    "pv-row-",
  )

  // ROVER: har jismoniy nusxa alohida qator
  const instRows = parts.flatMap((p) =>
    (p.instances ?? []).map((i) => ({ p, i })),
  )
  const instFlash = useScanFlash(
    instRows,
    (r) => r.i.instance_id,
    (r) => Number(r.i.done),
    "pv-inst-",
  )

  if (isLoading) return <Skeleton className="h-full w-full" />
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
        let dir = await getSavedDir(true)
        if (!dir) dir = await pickDir()
        if (!dir) return // bekor qilindi
        // Har proyekt o'z papkasiga: "1007 Yangibozor" kabi — fayllar aralashmaydi
        const folder = projectFolder(
          data?.project_name || data?.order_number || "scx",
        )
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
        toast.success(`${allFiles.length} ta SCX yuklab olindi`)
      }
    } finally {
      setProgress(null)
    }
  }

  const changeDir = async () => {
    const dir = await pickDir()
    if (dir) toast.success(`SCX papkasi: ${dir.name}`)
  }

  // ROVER rejimi: har nusxa ALOHIDA qator; qator tanlanadi, chop etish
  // chapdagi katta tugmada (ARRA terminal bilan bir xil ishlash naqshi —
  // sensor uchun katta nishon, chip ichidagi mayda tugma emas)
  if (!showScx) {
    const sel = instRows.find((r) => r.i.instance_id === selectedId) ?? null
    const canPrint =
      !!sel && !sel.i.done && !sel.i.label_printed && !sel.p.arra_route
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
        {toolbarContainer ? (
          createPortal(printBtn, toolbarContainer)
        ) : (
          <div className="flex w-[68px] shrink-0 flex-col gap-2">
            {printBtn}
          </div>
        )}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col rounded-xl border bg-white">
          <div className="flex flex-wrap items-center gap-3 border-b px-4 py-2">
            <Button
              variant="outline"
              className="h-12 px-4 text-base font-bold"
              onClick={onBack}
            >
              <ArrowLeft /> Orqaga
            </Button>
            <div className="text-lg font-black">{data?.order_number}</div>
            {/* Imo-ishora ko'rinmas — ISHORASI bir marta, jadval tepasida.
                Har qatorga takrorlansa 15 marta bir xil yozuv bo'lardi va
                holat badge'i bilan zid o'qilardi. */}
            <div className="text-sm text-muted-foreground">
              Chekni bekor qilish: qatorni bosib turing
            </div>
            <PostProgress className="ml-auto" done={totDone} total={totReq} />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="w-full text-base">
              <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
                <tr>
                  <th className="px-4 py-2.5">Detal ID</th>
                  <th className="px-4 py-2.5">Nomi</th>
                  <th className="px-4 py-2.5">O'lchami</th>
                  <th className="px-4 py-2.5 text-right">Holat</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map(({ p, i }) => (
                  <tr
                    key={i.instance_id}
                    id={`pv-inst-${i.instance_id}`}
                    onClick={() => setSelectedId(i.instance_id)}
                    // Chek chiqarilgan nusxada uzoq bosish uni bekor qiladi —
                    // lekin FAQAT o'z postida chiqarilganida. Ro'yxatda arradan
                    // kelgan detallar ham turadi va ilgari ularda ham ishlardi:
                    // roverchi arrachining kesish skanini qaytara olardi.
                    // Shart ikonkanikiga teng — uning borligi "chek shu yerda
                    // chiqadi" degani (backend ham shuni tekshiradi).
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
                      selectedId === i.instance_id &&
                        "bg-primary/10 ring-2 ring-inset ring-primary",
                      // Xatcho'p tanlov bilan birga ko'rinadi — boshqa o'q
                      instFlash === i.instance_id &&
                        "border-l-4 border-l-primary",
                    )}
                  >
                    <td className="num px-4 py-3 font-semibold">
                      {i.qr_text}
                      {/* Marshruti roverdan boshlangan detal — uni ROVER o'z
                          listidan kesadi. Ikonka bosilsa xarita o'sha katak
                          belgilangan holda ochiladi: 20 detalli listda uni
                          qidirib topguncha ancha vaqt ketardi. Ikonkaning
                          BORLIGI ayni paytda "chek shu yerda chiqadi" degani —
                          arradan kelgan detalda u yo'q. */}
                      {!p.arra_route && onShowOnMap && (
                        <button
                          type="button"
                          title="Kesish xaritasida ko'rsatish"
                          aria-label={`${i.qr_text} — kesish xaritasida ko'rsatish`}
                          className="ml-2 inline-flex size-8 items-center justify-center rounded-md align-middle text-muted-foreground hover:bg-muted hover:text-primary"
                          onClick={(e) => {
                            e.stopPropagation()
                            onShowOnMap(p.code)
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
                      {/* Holat IKKILIK — boshqa hamma ekranda ham shunday
                          (kromka, post navbati, kesish xaritasi). `label_printed`
                          holat emas: u NUSXANING bayrog'i va arradan kelgan
                          detalda allaqachon rost bo'ladi, ya'ni "chek chiqarilgan"
                          deb yozish oddiy kutayotgan qatorlarga ham tegib,
                          hech qanday ma'no bermasdi. */}
                      <span
                        className={cn(
                          "rounded-md px-2.5 py-1 text-sm font-bold",
                          i.done
                            ? "bg-green-600 text-white"
                            : "bg-muted text-muted-foreground",
                        )}
                      >
                        {i.done ? "✓ Bajarildi" : "Bajarilmagan"}
                      </span>
                    </td>
                  </tr>
                ))}
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
      <div className="flex flex-wrap items-center gap-3 border-b px-4 py-2">
        <Button
          variant="outline"
          className="h-12 px-4 text-base font-bold"
          onClick={onBack}
        >
          <ArrowLeft /> Orqaga
        </Button>
        <div className="text-lg font-black">{data?.order_number}</div>
        <PostProgress className="ml-auto" done={totDone} total={totReq} />
        <div className="flex items-center gap-2">
          {/* Sensorli ekranda hover yo'q — ikonka yoniga yozuv shart */}
          {dirSupported() && (
            <Button
              variant="outline"
              className="h-12 px-3 font-bold"
              title="SCX papkasini almashtirish"
              onClick={changeDir}
            >
              <FolderCog /> Papka
            </Button>
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
                <HardDriveDownload /> Hammasini yuklab olish ({allFiles.length})
              </>
            )}
          </LoadingButton>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <table className="w-full text-base">
          <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
            <tr>
              <th className="px-4 py-2.5">Kod</th>
              <th className="px-4 py-2.5">Nomi</th>
              <th className="px-4 py-2.5">O'lchami</th>
              <th className="px-4 py-2.5">
                {showScx ? "Nusxalar (SCX)" : "Nusxalar"}
              </th>
              <th className="px-4 py-2.5 text-right">Bajarildi</th>
            </tr>
          </thead>
          <tbody>
            {/* Ish-navbat: qilinmaganlar tepada, tugaganlar (✓) pastga tushadi */}
            {[...parts]
              .sort(
                (a, b) => Number(a.done >= a.total) - Number(b.done >= b.total),
              )
              .map((p) => {
                const finished = p.done >= p.total
                return (
                  <tr
                    key={p.route_id}
                    id={`pv-row-${p.part_id}`}
                    className={cn(
                      "border-b last:border-0",
                      finished && "bg-green-50",
                      // Xatcho'p: holat rangini bosmaydi, chap chetda turadi
                      flashId === p.part_id && "border-l-4 border-l-primary",
                    )}
                  >
                    <td className="num px-4 py-3 font-semibold">{p.code}</td>
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
                                  : i.label_printed
                                    ? "bg-amber-100 text-amber-700"
                                    : "text-muted-foreground",
                              )}
                            >
                              {i.qr_text}
                              {i.done && " ✓"}
                              {!i.done && !i.label_printed && !p.arra_route && (
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
                        <div className="flex flex-wrap gap-1">
                          {p.files.map((f) => {
                            const ok = p.done_qrs?.includes(
                              f.filename.replace(/\.scx$/i, ""),
                            )
                            return (
                              <span
                                key={f.id}
                                className={cn(
                                  "num rounded-sm px-1.5 py-0.5",
                                  ok
                                    ? "bg-green-100 font-semibold text-green-700"
                                    : "text-muted-foreground",
                                )}
                              >
                                {f.filename}
                                {ok && " ✓"}
                              </span>
                            )
                          })}
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
