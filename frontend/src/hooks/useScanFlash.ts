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
  // `n` — o'zgarish hisoblagichi: bir qator ketma-ket ikki marta skan qilinsa
  // (KROMKA'da 2 tomon) id o'zgarmaydi, lekin scroll baribir kerak — aynan
  // ikkinchi skanda qator «tugagan» bo'lib saralashda pastga tushadi.
  const [flash, setFlash] = useState<{ id: string | number; n: number } | null>(
    null,
  )
  // Chaqiruvchilar getKey/getCount ni inline lambda bilan beradi: dep massivida
  // tursa, setFlash keltirgan re-render effektni qayta ishga tushirib scroll
  // taymerini bekor qilardi — avto-scroll hech qachon ishlamasdi.
  const fnsRef = useRef({ getKey, getCount })
  fnsRef.current = { getKey, getCount }
  useEffect(() => {
    const { getKey: key, getCount: count } = fnsRef.current
    const prev = prevRef.current
    let changed: string | number | null = null
    for (const it of items) {
      const old = prev.get(key(it))
      if (old !== undefined && count(it) !== old) changed = key(it)
    }
    prevRef.current = new Map(items.map((it) => [key(it), count(it)]))
    if (changed !== null) {
      const id = changed
      setFlash((f) => ({ id, n: (f?.n ?? 0) + 1 }))
    }
  }, [items])

  // Scroll alohida effektda: u faqat o'zgarish bo'lganda ishlaydi, ro'yxatning
  // har refetchida emas. Saralash qatorni siljitadi — yangi render joylashgach
  // scroll qilamiz.
  useEffect(() => {
    if (flash === null) return
    const t = setTimeout(() => {
      document
        .getElementById(`${rowIdPrefix}${flash.id}`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" })
    }, 150)
    return () => clearTimeout(t)
  }, [flash, rowIdPrefix])
  return flash?.id ?? null
}
