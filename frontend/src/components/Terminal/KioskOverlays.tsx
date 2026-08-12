// Terminalning ikkita to'siq ekrani. Ikkalasi ham butun ekranni yopadi va bitta
// katta tugmadan iborat — sexda qo'lqop bilan bosiladi.

import { Expand, Lock } from "lucide-react"

import { Button } from "@/components/ui/button"

export function KioskOverlays({
  fullscreen,
  locked,
  onUnlock,
}: {
  fullscreen: boolean
  locked: boolean
  onUnlock: () => void
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
      {/* Qulf ekrani: tasodifiy tegishlardan himoya */}
      {locked && (
        <Overlay
          icon={<Lock className="size-16 opacity-80" />}
          title="Ekran qulflangan"
          action="Ochish"
          onAction={onUnlock}
          className="z-50"
        />
      )}
    </>
  )
}

function Overlay({
  icon,
  title,
  action,
  onAction,
  className = "z-40",
}: {
  icon: React.ReactNode
  title: string
  action: string
  onAction: () => void
  className?: string
}) {
  return (
    <div
      className={`fixed inset-0 flex flex-col items-center justify-center gap-6 bg-slate-900/95 text-white ${className}`}
    >
      {icon}
      <div className="text-2xl font-black">{title}</div>
      <Button
        size="lg"
        variant="secondary"
        className="h-14 px-10 text-lg font-bold"
        onClick={onAction}
      >
        {action}
      </Button>
    </div>
  )
}
