import { useCallback, useEffect, useRef } from "react"

/**
 * Chaqiruvlarni jamlaydi: birinchisi DARHOL bajariladi, keyingi `ms` ichida
 * kelganlari bittaga yig'ilib oyna oxirida BIR marta bajariladi (leading +
 * trailing). Oxirgi hodisadan keyingi holat baribir olinadi — faqat oraliqdagi
 * takrorlar tushib qoladi.
 *
 * WS hodisalari to'lqin bo'lib keladi: TMO qadog'i N ta `scan.recorded`, KROMKA
 * har qirra uchun skan. Har biriga butun ekranni qayta so'rash (TanStack uchib
 * yurgan so'rovni bekor qilib yangisini boshlaydi, server esa eskisini baribir
 * oxirigacha hisoblaydi) serverning ikki ishchisidan birini band qilib, boshqa
 * postlarning chek va skan so'rovlarini kuttirardi (2026-09-26 o'lchovi).
 */
export function useThrottled(fn: () => void, ms: number): () => void {
  const fnRef = useRef(fn)
  const last = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    fnRef.current = fn
  })
  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current)
    },
    [],
  )
  return useCallback(() => {
    const wait = last.current + ms - Date.now()
    if (wait <= 0) {
      last.current = Date.now()
      fnRef.current()
    } else if (timer.current === null) {
      timer.current = setTimeout(() => {
        timer.current = null
        last.current = Date.now()
        fnRef.current()
      }, wait)
    }
  }, [ms])
}
