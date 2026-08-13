// Kiosk qobig'i: tsexdagi monoblok terminal odatdagi veb-sahifa kabi tutmasligi
// kerak. Bu yerda uch narsa — kontekst menyusi, to'liq ekran holati va yangi
// build chiqqanda XAVFSIZ paytda qayta yuklash.

import { useEffect, useRef, useState } from "react"

/** Yangi build tekshiruvi va avto-reload oralig'i. */
const ETAG_CHECK_MS = 5 * 60_000
const RELOAD_TRY_MS = 30_000
/** Reload uchun "tinchlik": oxirgi skan urinishidan shuncha vaqt o'tgan bo'lsin. */
export const QUIET_MS = 120_000

export function useKioskShell(canReload: () => boolean) {
  const [fullscreen, setFullscreen] = useState(
    () =>
      !!document.fullscreenElement ||
      window.matchMedia("(display-mode: fullscreen)").matches,
  )
  const [updateReady, setUpdateReady] = useState(false)
  // Effekt qayta yozilmasin deb ref: `canReload` har renderda yangi funksiya
  const canReloadRef = useRef(canReload)
  canReloadRef.current = canReload

  // Sensorda long press Chrome kontekst menyusini ochmasin — chekni bekor
  // qilish long press'i shu tufayli xalaqitsiz ishlaydi. Admin sahifalarga
  // ta'sir qilmaydi: effekt faqat terminal ochiq turganda yashaydi.
  useEffect(() => {
    const block = (e: Event) => e.preventDefault()
    document.addEventListener("contextmenu", block)
    return () => document.removeEventListener("contextmenu", block)
  }, [])

  // To'liq ekran: Fullscreen API YOKI chrome --kiosk / PWA (display-mode)
  useEffect(() => {
    const mq = window.matchMedia("(display-mode: fullscreen)")
    const onFs = () => setFullscreen(!!document.fullscreenElement || mq.matches)
    document.addEventListener("fullscreenchange", onFs)
    mq.addEventListener("change", onFs)
    return () => {
      document.removeEventListener("fullscreenchange", onFs)
      mq.removeEventListener("change", onFs)
    }
  }, [])

  // Deploy'dan keyin yangi build: index.html ETag o'zgarsa belgilab qo'yamiz
  useEffect(() => {
    if (import.meta.env.DEV) return // Vite ETag'i o'zgaruvchan — dev'da reload sikli bo'ladi
    let etag: string | null = null
    const check = async () => {
      try {
        const r = await fetch("/", { method: "HEAD", cache: "no-store" })
        const e = r.headers.get("etag")
        if (etag === null) etag = e
        else if (e && e !== etag) setUpdateReady(true)
      } catch {
        /* oflayn — keyingi urinishda */
      }
    }
    check()
    const t = setInterval(check, ETAG_CHECK_MS)
    return () => clearInterval(t)
  }, [])

  // ...va xavfsiz payt kelganda o'zi qayta yuklaydi
  useEffect(() => {
    if (!updateReady) return
    const tryReload = () => {
      if (canReloadRef.current()) window.location.reload()
    }
    tryReload()
    const t = setInterval(tryReload, RELOAD_TRY_MS)
    return () => clearInterval(t)
  }, [updateReady])

  return fullscreen
}

/** Avto-skan (TZ 8.4.1): input doim fokusda. Skaner klaviatura sifatida yozadi,
 *  fokus boshqa joyda bo'lsa belgilar yo'qolardi. */
export function useScanFocus(
  enabled: boolean,
  inputRef: React.RefObject<HTMLInputElement | null>,
) {
  useEffect(() => {
    if (!enabled) return
    const focus = () => inputRef.current?.focus()
    focus()
    const t = setInterval(focus, 2000)
    return () => clearInterval(t)
  }, [enabled, inputRef])

  // Skaner fokussiz yozib yuborsa ham yo'qolmasin: birinchi tugma bosilishida
  // input fokusga olinadi — belgi o'sha yerga tushadi (2s intervalgacha kutilmaydi)
  useEffect(() => {
    if (!enabled) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (
        t === inputRef.current ||
        t.tagName === "INPUT" ||
        t.tagName === "TEXTAREA"
      )
        return
      if (e.key.length === 1 || e.key === "Enter") inputRef.current?.focus()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [enabled, inputRef])
}
