// PRISADKA post sahifasi (TZ 12.5): buyurtmaning prisadka detallari ro'yxati,
// har detalning SCX fayllari. "Hammasini yuklab olish" barcha SCX'ni BIR MARTA
// tanlangan papkaga yozadi (File System Access API) — papka IndexedDB'da
// saqlanadi, keyingi safar so'ralmaydi. Skan oqimi odatdagidek (har skanda
// o'sha detal SCX'i ham avtomatik tushadi).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, FolderCog, HardDriveDownload, Printer } from "lucide-react"
import { useState } from "react"

import { OpenAPI, TerminalService } from "@/client"
import { TBtn } from "@/components/Terminal/CutmapView"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { useScanFlash } from "@/hooks/useScanFlash"
import { formatSize } from "@/lib/mes"
import {
  dirSupported,
  getSavedDir,
  pickDir,
  projectFolder,
  saveScxToDir,
} from "@/lib/scxDir"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

type PFile = { id: number; filename: string }
type PInstance = {
  instance_id: number
  qr_text: string
  label_printed: boolean
  done: boolean
}
type PPart = {
  part_id: number
  code: string
  name: string
  length: number | null
  width: number | null
  thickness: number | null
  done: number
  total: number
  files: PFile[]
  // Marshrutida ARRA bormi: bo'lsa QR chekni arrachi chiqaradi, bu yerdan taqiq
  arra_route?: boolean
  // Skan tugagan nusxalar QR'lari (fayl nomi = QR + .scx) — qaysi nusxa qolganini ko'rsatish
  done_qrs?: string[]
  instances?: PInstance[]
}

export function PrisadkaView({
  orderId,
  onBack,
  showScx = true,
}: {
  orderId: number
  onBack: () => void
  /** ROVER: SCX fayllar kerak emas — yuklab olish/Papka va fayl nomlari yashirin */
  showScx?: boolean
}) {
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ["terminal", "prisadka", orderId],
    queryFn: () => TerminalService.readTerminalPrisadka({ orderId }),
    refetchInterval: 30_000,
  })
  // ROVER'da jarayon shu postdan boshlanishi mumkin (marshrutda ARRA yo'q) —
  // QR chek shu yerdan chiqariladi; keyin skan bilan ish yakunlanadi
  const printLabel = useMutation({
    mutationFn: (instanceId: number) =>
      TerminalService.printInstanceLabel({ instanceId }),
    onSuccess: (r) => showSuccessToast(r.message),
    onError: handleError(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["terminal", "prisadka"] }),
  })
  // null = yuklanmayapti; son = nechta fayl saqlandi (tugmada jonli 12/69)
  const [progress, setProgress] = useState<number | null>(null)
  // ROVER rejimi: qator (nusxa) tanlanadi, chop etish chapdagi katta tugmada
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const parts = ((data as { parts?: PPart[] } | undefined)?.parts ??
    []) as PPart[]

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
        const info = data as
          | { project_name?: string | null; order_number?: string }
          | undefined
        const folder = projectFolder(
          info?.project_name || info?.order_number || "scx",
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
          showSuccessToast(`${ok} ta SCX "${dir.name}/${folder}" ga saqlandi`)
        else
          showErrorToast(
            `${ok}/${allFiles.length} saqlandi — qolganlarini qayta urining.`,
          )
      } else {
        // Eski brauzer: oddiy Downloads
        let n = 0
        for (const f of allFiles) {
          const a = document.createElement("a")
          a.href = `${OpenAPI.BASE}/api/v1/terminal/files/${f.id}`
          a.download = ""
          a.click()
          n++
          setProgress(n)
          await new Promise((r) => setTimeout(r, 300))
        }
        showSuccessToast(`${allFiles.length} ta SCX yuklab olindi`)
      }
    } finally {
      setProgress(null)
    }
  }

  const changeDir = async () => {
    const dir = await pickDir()
    if (dir) showSuccessToast(`SCX papkasi: ${dir.name}`)
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
    return (
      <div className="flex h-full min-h-0 gap-3">
        <div className="flex w-[76px] shrink-0 flex-col gap-2">
          <TBtn
            label="Chop etish"
            tone={canPrint ? "success" : "default"}
            disabled={!canPrint || printLabel.isPending}
            onClick={() => sel && printLabel.mutate(sel.i.instance_id)}
          >
            <Printer />
          </TBtn>
        </div>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col rounded-xl border bg-white">
          <div className="flex flex-wrap items-center gap-3 border-b px-4 py-2">
            <Button
              variant="outline"
              className="h-12 px-4 text-base font-bold"
              onClick={onBack}
            >
              <ArrowLeft /> Orqaga
            </Button>
            <div className="text-lg font-black">
              {(data as { order_number?: string } | undefined)?.order_number}
            </div>
            <div className="num text-base text-muted-foreground">
              Bajarildi: <b className="text-foreground">{totDone}</b>/{totReq}
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="w-full text-base">
              <thead className="sticky top-0 z-10 bg-muted/80 text-left text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
                <tr>
                  <th className="px-4 py-2.5">Nusxa ID</th>
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
                    className={cn(
                      "cursor-pointer border-b last:border-0",
                      selectedId === i.instance_id
                        ? "bg-primary/10 ring-2 ring-inset ring-primary"
                        : instFlash === i.instance_id
                          ? "bg-amber-100 ring-2 ring-inset ring-amber-400"
                          : i.done && "bg-green-50",
                    )}
                  >
                    <td className="num px-4 py-3 font-semibold">{i.qr_text}</td>
                    <td className="max-w-[240px] truncate px-4 py-3">
                      {p.name}
                    </td>
                    <td className="num whitespace-nowrap px-4 py-3 text-sm">
                      {formatSize(p.length, p.width, p.thickness)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={cn(
                          "rounded-md px-2.5 py-1 text-sm font-bold",
                          i.done
                            ? "bg-green-600 text-white"
                            : i.label_printed
                              ? "bg-amber-100 text-amber-700"
                              : "bg-muted text-muted-foreground",
                        )}
                      >
                        {i.done
                          ? "✓ Bajarildi"
                          : i.label_printed
                            ? "Skan kutilmoqda"
                            : p.arra_route
                              ? "Chek arrada chiqadi"
                              : "Chek chiqarilmagan"}
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
        <div className="text-lg font-black">
          {(data as { order_number?: string } | undefined)?.order_number}
        </div>
        <div className="num text-base text-muted-foreground">
          Bajarildi: <b className="text-foreground">{totDone}</b>/{totReq}
        </div>
        {showScx && (
          <div className="ml-auto flex items-center gap-2">
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
                  <HardDriveDownload /> Hammasini yuklab olish (
                  {allFiles.length})
                </>
              )}
            </LoadingButton>
          </div>
        )}
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
                    key={p.part_id}
                    id={`pv-row-${p.part_id}`}
                    className={cn(
                      "border-b last:border-0",
                      flashId === p.part_id
                        ? "bg-amber-100 ring-2 ring-inset ring-amber-400"
                        : finished && "bg-green-50",
                    )}
                  >
                    <td className="num px-4 py-3 font-semibold">{p.code}</td>
                    <td className="max-w-[200px] truncate px-4 py-3">
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
                                "num inline-flex items-center gap-1 rounded px-1.5 py-0.5",
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
                                  className="rounded border px-1.5 py-0.5 text-foreground hover:bg-secondary"
                                >
                                  <Printer className="size-3.5" />
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
                                  "num rounded px-1.5 py-0.5",
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
