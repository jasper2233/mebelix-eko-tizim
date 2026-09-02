import { useQuery } from "@tanstack/react-query"
import { Check, ChevronsUpDown, Loader2, Plus } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { AddClient } from "@/components/Clients/AddClient"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { useDebounced } from "@/hooks/useDebounced"
import { cn } from "@/lib/utils"
import { getClientsQueryOptions } from "@/queries/mes"

interface ClientComboboxProps {
  value: string
  onChange: (id: string) => void
  /** Tanlangan mijoz nomi (EditOrder kabi tashqaridan kelganda) */
  initialLabel?: string
  disabled?: boolean
}

/**
 * Server-qidiruvli mijoz tanlagich: ro'yxat backend `?search=` bilan
 * filtrlanadi, shuning uchun mijozlar soni mingga yetsa ham ishlayveradi.
 */
export function ClientCombobox({
  value,
  onChange,
  initialLabel,
  disabled,
}: ClientComboboxProps) {
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const [label, setLabel] = useState(initialLabel ?? "")
  const [search, setSearch] = useState("")
  const [active, setActive] = useState(0)
  const debounced = useDebounced(search.trim())

  const { data, isFetching } = useQuery({
    ...getClientsQueryOptions(debounced),
    enabled: open,
  })
  const items = data?.data ?? []

  // biome-ignore lint/correctness/useExhaustiveDependencies: yangi natijada belgilangan qator boshiga qaytsin
  useEffect(() => setActive(0), [debounced])

  // Yopilganda qidiruvni tozalaymiz — aks holda keyingi ochilishda eski filtr ko'rinadi
  const changeOpen = (v: boolean) => {
    setOpen(v)
    if (!v) {
      setSearch("")
      setActive(0)
    }
  }

  const select = (id: string, name: string) => {
    onChange(id)
    setLabel(name)
    changeOpen(false)
  }

  return (
    // modal: Dialog ichida ochilganda pointer-events/scroll qulfi to'g'ri ishlashi uchun
    <Popover open={open} onOpenChange={changeOpen} modal>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          aria-expanded={open}
          className="w-full justify-between font-normal"
        >
          <span className={cn("truncate", !label && "text-muted-foreground")}>
            {label || "Mijozni tanlang"}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[var(--radix-popover-trigger-width)] p-0"
        onOpenAutoFocus={(e) => {
          // Radix'ning o'z avto-fokusi Dialog fokus-tuzog'i bilan urishadi —
          // o'zimiz to'g'ridan qidiruv maydoniga beramiz
          e.preventDefault()
          inputRef.current?.focus()
        }}
      >
        <div className="relative border-b p-2">
          <Input
            ref={inputRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault()
                setActive((a) => Math.min(a + 1, items.length - 1))
              } else if (e.key === "ArrowUp") {
                e.preventDefault()
                setActive((a) => Math.max(a - 1, 0))
              } else if (e.key === "Enter") {
                e.preventDefault()
                const c = items[active]
                if (c) select(String(c.id), c.full_name)
              }
            }}
            placeholder="Ism yoki telefon bo'yicha qidiring"
            className="h-9 pr-8"
          />
          {isFetching && (
            <Loader2 className="absolute right-4 top-4.5 size-4 animate-spin text-muted-foreground" />
          )}
        </div>
        <div role="listbox" className="max-h-64 overflow-y-auto p-1">
          {items.length === 0 && isFetching && (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              Qidirilmoqda…
            </p>
          )}
          {items.length === 0 && !isFetching && (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              {debounced
                ? `"${debounced}" bo'yicha mijoz topilmadi`
                : "Mijozlar yo'q"}
            </p>
          )}
          {items.map((c, i) => (
            <button
              key={c.id}
              type="button"
              role="option"
              aria-selected={String(c.id) === value}
              onClick={() => select(String(c.id), c.full_name)}
              onMouseEnter={() => setActive(i)}
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded-sm px-2 py-2 text-left text-sm focus-visible:bg-accent",
                i === active && "bg-accent",
              )}
            >
              <span className="min-w-0">
                <span className="block truncate">{c.full_name}</span>
                {c.phone && (
                  <span className="num block truncate text-xs text-muted-foreground">
                    {c.phone}
                  </span>
                )}
              </span>
              {String(c.id) === value && (
                <Check className="size-4 shrink-0 text-primary" />
              )}
            </button>
          ))}
        </div>
        <div className="border-t p-1">
          <AddClient
            trigger={
              <Button
                type="button"
                variant="ghost"
                className="w-full justify-start font-normal"
              >
                <Plus className="size-4" /> Yangi mijoz qo'shish
              </Button>
            }
            onCreated={(c) => select(String(c.id), c.full_name)}
          />
        </div>
      </PopoverContent>
    </Popover>
  )
}
