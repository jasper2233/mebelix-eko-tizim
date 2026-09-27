import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"

/** AB12CD34 -> AB12-CD34: telefonda aytish oson. MES agenti ham, chek
 *  qurilmasi ham bir xil 8 belgili kod oladi (`bridge_agents.new_pair_code`). */
export const fmtCode = (c: string) => `${c.slice(0, 4)}-${c.slice(4)}`

/** Kodning qolgan muddati — backendda `PAIR_TTL` 15 daqiqa.
 *
 * Kodni ko'rsatib, muddatini yashirish odamni taxminga majbur qilardi: agent
 * o'rnatilayotgan kompyuterga borguncha 12 daqiqa qoldimi yoki 20 soniyami —
 * bilinmasdi. Muddati o'tgani esa faqat kod TERILGANDAN KEYIN ma'lum bo'lardi.
 *
 * Soat SHU komponent ichida: bo'lmasa har soniyada butun jadval qayta chizilardi.
 */
export function CodeTtl({ expiresAt }: { expiresAt: string }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  const qoldi = Math.max(
    0,
    Math.round((new Date(expiresAt).getTime() - now) / 1000),
  )
  return (
    <span
      className={cn(
        "num mt-1 block text-xs tabular-nums",
        // Oxirgi 2 daqiqa — endi yangi kod olish tezroq
        qoldi <= 120
          ? "font-semibold text-destructive"
          : "text-muted-foreground",
      )}
    >
      {Math.floor(qoldi / 60)}:{String(qoldi % 60).padStart(2, "0")} qoldi
    </span>
  )
}
