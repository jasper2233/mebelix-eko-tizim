// Ombor sarlavhasidagi qidiruv: kod, nom yoki SKANER (skaner klaviatura bo'lib yozadi va Enter
// bosadi). Enter — aniq kod, so'ng kod boshi, so'ng nom bo'yicha birinchi mos pozitsiyaning
// kartochkasi. «/» tugmasi har qanday ombor sahifasida shu maydonga o'tkazadi (dizayndagidek).

import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ScanLine } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { Input } from "@/components/ui/input"
import { getCatalogAllQueryOptions } from "@/queries/mes"

export function GotoSearch() {
  const { data } = useQuery(getCatalogAllQueryOptions())
  const navigate = useNavigate()
  const [q, setQ] = useState("")
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName ?? "").toUpperCase()
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(tag)) {
        e.preventDefault()
        ref.current?.focus()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const go = () => {
    const t = q.trim().toLowerCase()
    if (!t || !data) return
    const hit =
      data.find((r) => r.code.toLowerCase() === t) ??
      data.find((r) => r.code.toLowerCase().startsWith(t)) ??
      data.find((r) => r.name.toLowerCase().includes(t))
    if (!hit) {
      toast.error(`«${q.trim()}» bo'yicha tovar topilmadi`)
      return
    }
    setQ("")
    ref.current?.blur()
    navigate({ to: "/warehouse/item/$code", params: { code: hit.code } })
  }

  return (
    <div className="relative w-full sm:w-72">
      <ScanLine
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        ref={ref}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault()
            go()
          }
        }}
        placeholder="Kod / nom — skaner (/ yoki Enter)"
        aria-label="Tovarni kod yoki nom bo'yicha topish"
        className="pl-8"
      />
    </div>
  )
}
