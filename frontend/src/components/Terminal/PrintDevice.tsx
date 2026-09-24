// Chek qurilmasi (monoblok) — terminal sarlavhasidagi belgi va ulash oynasi.
//
// Ish markazida ulangan monoblok bo'lsa chek FAQAT undan chiqadi (server E011
// bilan rad etadi). Bu yerda ishchiga oldindan aytiladi: telefonda qizil
// «chek chiqmaydi» belgisi, admin kod bergan monoblokda esa «Qurilmani ulash».
// Ikkalasi ham bo'lmasa HECH NARSA chizilmaydi — sarlavha faqat muammoni
// ko'rsatadi (agent chipi bilan bir falsafa).

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound, PrinterX } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { type TerminalContext, TerminalDevicesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { handleError } from "@/utils"

/** Chek chiqarish shu brauzerda to'silganmi (telefon / ulanmagan kompyuter). */
export const printBlocked = (ctx?: TerminalContext): boolean =>
  !!ctx?.print_lock && ctx.print_allowed === false

/** Admin kod bergan, shu brauzer esa hali ulanmagan — kod kiritish taklifi. */
const pairingOffered = (ctx?: TerminalContext): boolean =>
  !!ctx?.print_pairing && !ctx.print_device_name

export function PrintDeviceChip({
  ctx,
  onOpen,
}: {
  ctx?: TerminalContext
  onOpen: () => void
}) {
  if (printBlocked(ctx))
    return (
      <Button
        variant="destructive"
        className="h-12 shrink-0 gap-2 px-3"
        onClick={onOpen}
        title="Bu qurilmadan chek chiqmaydi"
      >
        <PrinterX className="size-6" />
        <span className="text-sm font-bold">Chek chiqmaydi</span>
      </Button>
    )
  if (pairingOffered(ctx))
    return (
      <Button
        variant="outline"
        className="h-12 shrink-0 gap-2 border-amber-500 px-3 text-amber-700 hover:text-amber-800"
        onClick={onOpen}
      >
        <KeyRound className="size-6" />
        <span className="text-sm font-bold">Qurilmani ulash</span>
      </Button>
    )
  return null
}

export function PrintDeviceDialog({
  ctx,
  open,
  onOpenChange,
}: {
  ctx?: TerminalContext
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const [code, setCode] = useState("")
  const pair = useMutation({
    mutationFn: async (c: string) =>
      (await TerminalDevicesService.pairTerminalDevice({ body: { code: c } }))
        .data,
    onSuccess: (r) => {
      toast.success(`Qurilma ulandi: ${r.name} — chek shu yerdan chiqadi`)
      setCode("")
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["terminal", "context"] })
    },
    onError: handleError,
  })
  const blocked = printBlocked(ctx)
  const machine = ctx?.machine_name ?? "shu ish markazi"
  // Kod 8 belgi; ko'rsatishda ikkiga bo'linadi (ABCD-EFGH) — server chiziqni o'zi olib tashlaydi
  const clean = code.replace(/[^A-Za-z0-9]/g, "").toUpperCase()

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) setCode("")
        onOpenChange(o)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {blocked ? "Bu qurilmadan chek chiqmaydi" : "Qurilmani ulash"}
          </DialogTitle>
          <DialogDescription>
            {blocked
              ? `Chek faqat ${machine} monoblokidan chiqadi. Skan va xarita bu yerda ham ishlaydi. Agar bu postning monobloki bo'lsa — admin bergan kodni kiriting.`
              : `Admin bergan 8 belgili kodni kiriting — shundan keyin ${machine} cheki faqat shu kompyuterdan chiqadi.`}
          </DialogDescription>
        </DialogHeader>
        <input
          autoFocus
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            // isPending: Enter ikki marta bosilsa kod ikki marta ketardi —
            // birinchisi kodni ishlatib yuboradi, ikkinchisi «noto'g'ri kod» deydi
            if (e.key === "Enter" && clean.length >= 4 && !pair.isPending)
              pair.mutate(clean)
          }}
          placeholder="ABCD-EFGH"
          maxLength={16}
          autoComplete="off"
          spellCheck={false}
          aria-label="Ulanish kodi"
          className="h-14 w-full select-text rounded-lg border-2 border-primary/40 bg-card px-4 text-center font-mono text-2xl uppercase tracking-widest outline-none focus:border-primary"
        />
        <DialogFooter className="mt-2 gap-3">
          <DialogClose asChild>
            <Button
              variant="outline"
              className="h-11 px-5"
              disabled={pair.isPending}
            >
              Yopish
            </Button>
          </DialogClose>
          <LoadingButton
            className="h-11 px-5"
            loading={pair.isPending}
            disabled={clean.length < 4}
            onClick={() => pair.mutate(clean)}
          >
            Ulash
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
