// Harakatsizlikdan keyin chiqish: kirish kechgacha ishlab ertasiga ham saqlanib
// qolardi va odam qayta kirmasdan ishini davom ettirardi. Chegara (daqiqa) hisob
// turiga qarab serverdan keladi — tsex 90, ofis 240, TABLO chiqarilmaydi
// (Tizim sozlamalari). Ish jadvali ATAYLAB hisobga olinmaydi: smena kechroq tugashi mumkin.
//
// Ekran ochiq qolgan bo'lsa ham ishlaydi: tekshiruv har 30 s da va oynaga qaytilganda,
// ya'ni odam soatlardan keyin kelib birinchi bosishidayoq login sahifasini ko'radi.
// Brauzer yopilgan/monoblok o'chirilgan holatni server yopadi: refresh rad etiladi,
// ochiq smenani worker yopadi (`backend/app/services/activity.py`).

import { useQuery } from "@tanstack/react-query"
import { useCallback, useEffect, useRef } from "react"

import { UsersService } from "@/client"
import { useAuth } from "@/hooks/useAuth"

/** Oxirgi harakat vaqti (ms). localStorage — tablar va sahifa qayta yuklanishi orasida
 *  umumiy: monoblok tunda o'chib ertalab yoqilsa ham eski vaqt saqlanib turadi. */
export const LAST_ACTIVITY_KEY = "mes.lastActivity"
/** Serverga faollik xabari — ko'pi bilan shuncha vaqtda bir marta. */
const PING_MS = 60_000
const CHECK_MS = 30_000
const INPUT_EVENTS = ["pointerdown", "keydown", "wheel", "touchstart"] as const

const readLast = () => {
  try {
    return Number(localStorage.getItem(LAST_ACTIVITY_KEY)) || null
  } catch {
    return null // saqlash yopiq — mahalliy tekshiruv yo'q, serverniki qoladi
  }
}
const writeLast = (at: number) => {
  try {
    localStorage.setItem(LAST_ACTIVITY_KEY, String(at))
  } catch {
    /* saqlash yopiq */
  }
}

/** Yangi kirish: eski vaqt tozalanadi, aks holda kirgan zahoti yana chiqarib yuborardi.
 *  Login sahifasi chaqiradi — chiqishning hamma yo'li (tugma, harakatsizlik, 401) shu yerga keladi. */
export const resetLastActivity = () => {
  try {
    localStorage.removeItem(LAST_ACTIVITY_KEY)
  } catch {
    /* saqlash yopiq */
  }
}

/** Qobiqda bir marta chaqiriladi. Qaytgan `touch` — kiritishdan tashqari faollik
 *  (terminalda: shu ish markazidagi stanok skaneri skani). */
export function useIdleLogout() {
  const { logout } = useAuth()
  const logoutRef = useRef(logout)
  logoutRef.current = logout
  const { data: minutes } = useQuery({
    queryKey: ["users", "me", "idle-limit"],
    queryFn: async () =>
      (await UsersService.readIdleLimit()).data.idle_minutes ?? null,
    staleTime: 5 * 60_000,
  })
  const limitMs = minutes ? minutes * 60_000 : null
  const lastPingRef = useRef(0)
  const firedRef = useRef(false)

  /** Chegara oshganmi — oshgan bo'lsa chiqaradi (bir marta). */
  const expired = useCallback(() => {
    const last = readLast()
    if (limitMs === null || last === null || Date.now() - last <= limitMs)
      return false
    if (!firedRef.current) {
      firedRef.current = true
      logoutRef.current()
    }
    return true
  }, [limitMs])

  const touch = useCallback(() => {
    // Soatlardan keyingi birinchi bosish faollik EMAS — u chiqishga olib keladi
    if (limitMs === null || expired()) return
    const now = Date.now()
    writeLast(now)
    if (now - lastPingRef.current > PING_MS) {
      lastPingRef.current = now
      UsersService.touchUserActivity().catch(() => {
        lastPingRef.current = 0 // tarmoq uzildi — keyingi harakatda qayta urinamiz
      })
    }
  }, [limitMs, expired])

  useEffect(() => {
    if (limitMs === null) return
    // Kirishdan keyingi birinchi ochilish: hisob shu paytdan boshlanadi
    if (readLast() === null) writeLast(Date.now())
    expired()
    const opts = { capture: true, passive: true }
    for (const e of INPUT_EVENTS) window.addEventListener(e, touch, opts)
    // Oynaga qaytish: `visibilityState` ga qaralmaydi — u fokusdagi oynada ham
    // "hidden" bo'lishi mumkin (o'lchandi), tekshiruv esa baribir zararsiz
    document.addEventListener("visibilitychange", expired)
    window.addEventListener("focus", expired)
    const timer = setInterval(expired, CHECK_MS)
    return () => {
      for (const e of INPUT_EVENTS) window.removeEventListener(e, touch, opts)
      document.removeEventListener("visibilitychange", expired)
      window.removeEventListener("focus", expired)
      clearInterval(timer)
    }
  }, [limitMs, expired, touch])

  return touch
}
