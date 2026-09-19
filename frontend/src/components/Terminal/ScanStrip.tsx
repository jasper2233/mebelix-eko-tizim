// Oxirgi skan natijasi + BEKOR QILISH. Har post ekranining tepasida turadi:
// tsex shovqinida ovoz signaliga ishonib bo'lmaydi, natija ko'rinib turishi kerak.

import { TriangleAlert, Undo2 } from "lucide-react"

import { Serial } from "@/components/Terminal/Serial"
import { Button } from "@/components/ui/button"
import { scanWord } from "@/lib/mes"
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
  onDefect,
  birlik,
}: {
  scan: LastScan
  /** Bekor qilish oynasi 60 s — chaqiruvchi taymer bilan hisoblaydi */
  canUndo: boolean
  onUndo: () => void
  /** BRAK — detal yaroqsiz chiqdi (OEE Quality). Berilmasa tugma chizilmaydi:
   *  brak sabablari ro'yxati hali kiritilmagan bo'lsa bosadigan narsa yo'q. */
  onDefect?: () => void
  /** Qoldiq birligi — KROMKA'da "qirra" (har qirra alohida skan).
   *  Yalang'och "Qoldiq: 3" kromkachini adashtirardi: 3 nima — detalmi, skanmi?
   *  U 4 qirralik detalni 2 skan bilan "tugadi" deb ketar, prisadka esa E004
   *  bilan to'xtatardi. */
  birlik?: string
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
          <Serial
            code={scan.code}
            className="text-xl font-black text-green-700"
          />
          <span className="text-base text-green-800">
            Qoldiq: <b>{scan.qoldiq}</b>
            {birlik ? ` ${birlik}` : ""}
          </span>
        </>
      ) : scan.kind === "info" ? (
        <>
          <span className="text-lg font-black text-blue-700">
            {scanWord(scan.code)}
          </span>
          <span className="text-base text-blue-900">{scan.message}</span>
          <span className="num text-xs text-blue-700/60">{scan.code}</span>
        </>
      ) : (
        <>
          {/* Sarlavha — so'z («NAVBAT», «TAKROR»), kod kichik: «E004» ishchiga
              hech narsa demasdi */}
          <span className="whitespace-nowrap text-lg font-black text-red-700">
            {scanWord(scan.code)}
          </span>
          <span className="truncate text-base text-red-800">
            {scan.message}
          </span>
          <span className="num text-xs text-red-700/60">{scan.code}</span>
        </>
      )}
      {/* BRAK faqat MUVAFFAQIYATLI skanda: belgilanadigan narsa — o'sha skan.
          Bekor qilish bilan yonma-yon, lekin ajralib tursin deb outline. */}
      {ok && onDefect && (
        <Button
          variant="outline"
          className="ml-auto h-12 shrink-0 border-2 border-red-500 px-4 text-sm font-black text-red-700 hover:bg-red-100 hover:text-red-800"
          onClick={onDefect}
        >
          <TriangleAlert /> BRAK
        </Button>
      )}
      <Button
        variant="destructive"
        className={cn(
          "h-12 shrink-0 px-4 text-sm font-black",
          !(ok && onDefect) && "ml-auto",
        )}
        disabled={!canUndo}
        onClick={onUndo}
      >
        <Undo2 /> BEKOR QILISH
      </Button>
    </div>
  )
}
