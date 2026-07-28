import { useEffect, useState } from "react"

/**
 * Qiymatni kechiktirib qaytaradi — qidiruv maydonlari uchun.
 *
 * Busiz har bosilgan harf yangi query key yaratadi, yangi kalit uchun kesh bo'sh
 * bo'lgani sababli `isLoading` yoqiladi va jadval o'rnini skeleton egallaydi:
 * "shkaf" so'zini terganda jadval besh marta yo'qolib-paydo bo'ladi.
 */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

export default useDebounced
