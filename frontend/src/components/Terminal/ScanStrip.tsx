// Oxirgi skan natijasi + BEKOR QILISH. Har post ekranining tepasida turadi:
// tsex shovqinida ovoz signaliga ishonib bo'lmaydi, natija ko'rinib turishi kerak.

import { Undo2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type LastScan =
  | { kind: "ok"; code: string; qoldiq: number; scanId: number; at: number }
  | { kind: "error"; code: string; message: string; at: number }
  // "info" — skan xato ham, muvaffaqiyat ham emas (mas. ATX: qoldiq QR
  // ma'lumot uchun skan qilindi). Ko'k rang: qizil "to'xta!" degani, bu emas.
  | { kind: "info"; code: string; message: string; at: number }
  | null

export function ScanStrip({
  scan,
  canUndo,
  onUndo,
}: {
  scan: LastScan
  /** Bekor qilish oynasi 60 s (TZ 8.6) — chaqiruvchi taymer bilan hisoblaydi */
  canUndo: boolean
  onUndo: () => void
}) {
  if (!scan) return null
  const ok = scan.kind === "ok"
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl border-2 px-4 py-2",
        ok
          ? "border-green-500 bg-green-50"
          : scan.kind === "info"
            ? "border-blue-500 bg-blue-50"
            : "border-red-500 bg-red-50",
      )}
    >
      {scan.kind === "ok" ? (
        <>
          <span className="num text-xl font-black text-green-700">
            {scan.code}
          </span>
          <span className="text-base text-green-800">
            Qoldiq: <b>{scan.qoldiq}</b>
          </span>
        </>
      ) : scan.kind === "info" ? (
        <>
          <span className="text-lg font-black text-blue-700">{scan.code}</span>
          <span className="text-base text-blue-900">{scan.message}</span>
        </>
      ) : (
        <>
          <span className="text-lg font-black text-red-700">{scan.code}</span>
          <span className="truncate text-base text-red-800">
            {scan.message}
          </span>
        </>
      )}
      <Button
        variant="destructive"
        className="ml-auto h-12 shrink-0 px-4 text-sm font-black"
        disabled={!canUndo}
        onClick={onUndo}
      >
        <Undo2 /> BEKOR QILISH
      </Button>
    </div>
  )
}
