import { useEffect, useRef, useState } from "react"

/**
 * Oxirgi skan bo'lgan qatorni belgilaydi va uni markazga scroll qiladi.
 *
 * Belgi vaqt bo'yicha o'chmaydi — bu bildirishnoma emas, XATCHO'P: operator
 * skanerlagach detalni olib stanokka boradi, bir necha daqiqadan keyin
 * qaytadi va 100 qatorli ro'yxatda qayerda qolganini shu belgidan topadi.
 * Bir necha soniyada so'nsa, qaytganida ro'yxat bir xil ko'rinib qolardi.
 *
 * Belgi qatorning HOLAT rangini almashtirmasligi kerak (bajarilgan qator
 * yashil qolaveradi) — u boshqa o'q: "siz shu yerda edingiz". Chizilishi
 * chaqiruvchida: chap chetdagi yo'g'on chiziq.
 *
 * Qator DOM id'si: `${rowIdPrefix}${key}`.
 */
export function useScanFlash<T>(
  items: T[],
  getKey: (item: T) => string | number,
  getCount: (item: T) => number,
  rowIdPrefix: string,
): string | number | null {
  const prevRef = useRef<Map<string | number, number>>(new Map())
  const [flashId, setFlashId] = useState<string | number | null>(null)
  useEffect(() => {
    const prev = prevRef.current
    let changed: string | number | null = null
    for (const it of items) {
      const old = prev.get(getKey(it))
      if (old !== undefined && getCount(it) !== old) changed = getKey(it)
    }
    prevRef.current = new Map(items.map((it) => [getKey(it), getCount(it)]))
    if (changed !== null) {
      setFlashId(changed)
      // Saralash qatorni siljitadi — yangi render joylashgach scroll qilamiz
      const t = setTimeout(() => {
        document
          .getElementById(`${rowIdPrefix}${changed}`)
          ?.scrollIntoView({ block: "center", behavior: "smooth" })
      }, 150)
      return () => clearTimeout(t)
    }
  }, [items, getKey, getCount, rowIdPrefix])
  return flashId
}
