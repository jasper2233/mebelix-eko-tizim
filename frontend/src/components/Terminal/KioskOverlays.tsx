// Terminalning ikkita to'siq ekrani. Ikkalasi ham butun ekranni yopadi va bitta
// katta tugmadan iborat — tsexda qo'lqop bilan bosiladi.

import { Expand, Lock } from "lucide-react"

import { Button } from "@/components/ui/button"

export function KioskOverlays({
  fullscreen,
  locked,
  onLogout,
}: {
  fullscreen: boolean
  locked: boolean
  /** Beyjiksiz hisob (operator roli) qulf ostida qolib ketmasin — chiqish yo'li */
  onLogout: () => void
}) {
  return (
    <>
      {/* Majburiy to'liq ekran: kiosk tartibi — to'liq ekranga o'tmaguncha ish
          yo'q. `requestFullscreen` user-gesture talab qiladi, shuning uchun tugma. */}
      {!fullscreen && !locked && (
        <Overlay
          icon={<Expand className="size-16 opacity-80" />}
          title="Terminal to'liq ekranda ishlaydi"
          action="To'liq ekranga o'tish"
          onAction={() => document.documentElement.requestFullscreen()}
        />
      )}
      {/* Qulf ekrani. Tugma bilan ochilmaydi: qulf tasodifiy tegishdan ham,
          begona odamdan ham himoya — kalit BEYJIK. Skan maydoni qulf ostida
          ham fokusda turadi, beyjik skani ekranni ochadi va smenani o'ziga
          oladi (odatdagi sessiya oqimi). */}
      {locked && (
        <Overlay
          icon={<Lock className="size-16 opacity-80" />}
          title="Ekran qulflangan"
          hint="Ochish uchun beyjikni skanerlang"
          action="Chiqish"
          actionVariant="ghost"
          onAction={onLogout}
          className="z-50"
        />
      )}
    </>
  )
}

function Overlay({
  icon,
  title,
  hint,
  action,
  actionVariant = "secondary",
  onAction,
  className = "z-40",
}: {
  icon: React.ReactNode
  title: string
  hint?: string
  action: string
  actionVariant?: "secondary" | "ghost"
  onAction: () => void
  className?: string
}) {
  return (
    <div
      className={`fixed inset-0 flex flex-col items-center justify-center gap-6 bg-slate-900/95 text-white ${className}`}
    >
      {icon}
      <div className="text-2xl font-black">{title}</div>
      {hint && <div className="text-lg text-white/70">{hint}</div>}
      <Button
        size="lg"
        variant={actionVariant}
        className={
          actionVariant === "ghost"
            ? "h-12 px-8 text-base text-white/60 hover:bg-white/10 hover:text-white"
            : "h-14 px-10 text-lg font-bold"
        }
        onClick={onAction}
      >
        {action}
      </Button>
    </div>
  )
}
