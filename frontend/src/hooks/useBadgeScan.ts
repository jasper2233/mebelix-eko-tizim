// Sahifaning ISTALGAN joyida beyjik skanini tutadi — fokusni tortib olmasdan.
//
// Login sahifasida yashirin inputga fokus berib bo'lmaydi: ofis xodimi o'sha
// paytda foydalanuvchi nomi va parolni terayotgan bo'lishi mumkin, fokus esa
// har necha soniyada tortib olinardi. Shuning uchun `document` darajasida
// tinglaymiz va HECH NARSAGA tegmaymiz.
//
// Skanerni odamdan farqlash — TEZLIK: u klaviatura bo'lib belgilarni ketma-ket,
// millisekundlarda yozadi va Enter bilan tugatadi. Odam qo'lda 36 belgili UUID
// ni shu tezlikda tera olmaydi, ya'ni bufer hech qachon tasodifan to'lmaydi.

import { useEffect, useRef } from "react"

import { BADGE_RE } from "@/lib/mes"

/** Belgilar orasidagi tanaffus shundan oshsa — bu odam terayapti, bufer tozalanadi. */
const GAP_MS = 120

export function useBadgeScan(onBadge: (badgeId: string) => void) {
  const handler = useRef(onBadge)
  handler.current = onBadge

  useEffect(() => {
    let buffer = ""
    let last = 0

    const onKey = (e: KeyboardEvent) => {
      const now = Date.now()
      if (now - last > GAP_MS) buffer = ""
      last = now
      if (e.key === "Enter") {
        const value = buffer.trim()
        buffer = ""
        if (BADGE_RE.test(value)) {
          // Bufer to'liq beyjik — bu Enter skanerniki, odamniki emas. Bloklamasak
          // parol maydoni fokusda bo'lganda brauzer login formasini ham yuboradi:
          // bitta skan bir vaqtda beyjik so'rovini ham, forma xatosini ham chiqarardi.
          e.preventDefault()
          handler.current(value)
        }
        return
      }
      // `e.key` HAR DOIM ham bo'lmaydi: brauzer avtoto'ldirishi (parol menejeri)
      // va ba'zi IME'lar `key` siz sintetik keydown yuboradi. Tekshiruvsiz bu
      // butun tinglagichni yiqitardi — login sahifasida parol avtoto'lganda
      // konsolda "Cannot read properties of undefined (reading 'length')".
      if (e.key?.length === 1) buffer += e.key
    }

    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])
}
