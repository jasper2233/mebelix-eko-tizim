import { useEffect, useRef, useState } from "react"

/**
 * Oxirgi skan bo'lgan qator KEYINGI skangacha ajralib turadi va avtomatik
 * markazga scroll bo'ladi — operator sichqoncha bilan qidirmasin.
 * Bitta mexanizm uch joyda (prisadka, kromka, vazifalar) ishlaydi: items
 * yangilanganda hisobi O'ZGARGAN element flash oladi (skan ham, bekor ham).
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
