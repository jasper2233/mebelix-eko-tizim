import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import type { CatalogItemRead } from "@/client"
import { Input } from "@/components/ui/input"
import { useDebounced } from "@/hooks/useDebounced"
import { formatMoney } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { getCatalogItemsQueryOptions } from "@/queries/mes"

/** Katalogdan pozitsiya tanlagich — sotuv listining qatori uchun.
 *
 * Qidiruv SERVERDA (`/catalog/items?search=`): katalogda 2662 pozitsiya bor,
 * brauzerga hammasini tortib filtrlash ma'nosiz. Kod, nom, artikul va dekor
 * nomi bo'ylab qidiradi — sotuvchi qo'lidagi qog'ozda qaysi biri turgani
 * oldindan ma'lum emas.
 *
 * Maydon erkin matnni ham qabul qiladi: katalogda yo'q narsa (bir martalik
 * xizmat, mijozning o'z materiali) ham listga tushishi kerak. Shuning uchun bu
 * oddiy `Input` ustidagi TAKLIF ro'yxati, majburiy tanlov emas.
 *
 * Radix `Popover` ATAYLAB ishlatilmadi: uning trigger'i maydonni o'rab olib
 * klaviatura hodisalarini o'ziga tortadi va maydonga yozib bo'lmay qoladi. */
export function CatalogPicker({
  value,
  onText,
  onPick,
  placeholder = "Kod, nom yoki artikul",
}: {
  value: string
  onText: (text: string) => void
  onPick: (item: CatalogItemRead) => void
  placeholder?: string
}) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)
  const debounced = useDebounced(value.trim())

  const { data, isFetching } = useQuery({
    ...getCatalogItemsQueryOptions({ search: debounced }),
    enabled: open && debounced.length >= 2,
  })
  const items = (data?.data ?? []).slice(0, 20)
  const korinadi = open && (items.length > 0 || isFetching)

  // biome-ignore lint/correctness/useExhaustiveDependencies: yangi natijada belgi boshiga qaytsin
  useEffect(() => setActive(0), [debounced])
  useEffect(() => {
    listRef.current
      ?.querySelector(`[data-idx="${active}"]`)
      ?.scrollIntoView({ block: "nearest" })
  }, [active])

  const tanla = (item: CatalogItemRead) => {
    onPick(item)
    setOpen(false)
  }

  return (
    <div className="relative">
      <Input
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          onText(e.target.value)
          setOpen(true)
        }}
        // Yopilish kechiktiriladi: ro'yxatdagi tugma bosilishi `blur` dan KEYIN
        // keladi, darhol yopilsa tanlov umuman ishlamasdi
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onFocus={() => value.trim().length >= 2 && setOpen(true)}
        onKeyDown={(e) => {
          if (!korinadi || !items.length) return
          if (e.key === "ArrowDown") {
            e.preventDefault()
            setActive((a) => Math.min(a + 1, items.length - 1))
          } else if (e.key === "ArrowUp") {
            e.preventDefault()
            setActive((a) => Math.max(a - 1, 0))
          } else if (e.key === "Enter") {
            e.preventDefault()
            const it = items[active]
            if (it) tanla(it)
          } else if (e.key === "Escape") {
            setOpen(false)
          }
        }}
        className="h-8 border-transparent bg-transparent px-2 font-medium hover:border-input focus-visible:bg-background"
      />
      {korinadi && (
        <div
          ref={listRef}
          role="listbox"
          className="absolute left-0 top-full z-50 mt-1 max-h-72 w-[min(34rem,120%)] overflow-y-auto rounded-md border bg-popover p-1 shadow-md"
        >
          {isFetching && items.length === 0 && (
            <p className="flex items-center justify-center gap-2 px-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> Qidirilmoqda…
            </p>
          )}
          {items.map((c, i) => (
            <button
              key={c.id}
              data-idx={i}
              type="button"
              role="option"
              aria-selected={i === active}
              // `onMouseDown`: `onBlur` dan OLDIN ishlaydi, ya'ni ro'yxat
              // yopilib ulgurmaydi
              onMouseDown={(e) => {
                e.preventDefault()
                tanla(c)
              }}
              onMouseEnter={() => setActive(i)}
              className={cn(
                "flex w-full items-start justify-between gap-3 rounded-sm px-2 py-2 text-left text-sm",
                i === active && "bg-accent",
              )}
            >
              <span className="min-w-0">
                <span className="block truncate">{c.name}</span>
                <span className="num block truncate text-xs text-muted-foreground">
                  {[c.code, c.article, c.size_text].filter(Boolean).join(" · ")}
                </span>
              </span>
              <span className="num shrink-0 text-right text-xs">
                <span className="block font-semibold">
                  {formatMoney(c.sale_price)}
                </span>
                {c.unit && (
                  <span className="block text-muted-foreground">{c.unit}</span>
                )}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
