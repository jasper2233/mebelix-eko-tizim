// O'zbekcha sana tanlagich (deadline, hisobot oralig'i): react-day-picker + brend ranglar.
// Qiymat form/API bilan mos "YYYY-MM-DD" satr; ko'rinish — 10.07.2026.

import { CalendarDays, X } from "lucide-react"
import { useState } from "react"
import { DayPicker } from "react-day-picker"
import { uz } from "react-day-picker/locale"

import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"

function toDate(value: string): Date | undefined {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!m) return undefined
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
}

function toValue(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function display(value: string): string {
  const d = toDate(value)
  if (!d) return ""
  const p = (n: number) => String(n).padStart(2, "0")
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}`
}

export function DatePicker({
  value,
  onChange,
  placeholder = "Sanani tanlang",
  className,
  "aria-label": ariaLabel,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  "aria-label"?: string
}) {
  const [open, setOpen] = useState(false)
  const selected = toDate(value)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      {/* Tozalash tugmasi trigger'dan TASHQARIDA: avval u `<Button>` ichidagi
          onClick'li `<svg>` edi — tugma ichida tugma (yaroqsiz HTML), tab bilan
          yetib bo'lmasdi va nishoni 14px edi. */}
      <div className={cn("relative flex items-center", className)}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            aria-label={ariaLabel}
            className={cn(
              "w-full justify-start gap-2 font-normal",
              !value && "text-muted-foreground",
              value && "pr-10",
            )}
          >
            <CalendarDays className="size-4 shrink-0 opacity-70" />
            <span className="num">{value ? display(value) : placeholder}</span>
          </Button>
        </PopoverTrigger>
        {value && (
          <button
            type="button"
            onClick={() => onChange("")}
            aria-label="Sanani tozalash"
            className="absolute right-1 inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
          >
            <X className="size-4" />
          </button>
        )}
      </div>
      <PopoverContent className="w-auto">
        <DayPicker
          mode="single"
          locale={uz}
          selected={selected}
          defaultMonth={selected}
          onSelect={(d) => {
            onChange(d ? toValue(d) : "")
            setOpen(false)
          }}
          showOutsideDays
          classNames={{
            months: "relative",
            month_caption:
              "flex h-9 items-center justify-center text-sm font-semibold capitalize",
            nav: "absolute inset-x-0 top-0 z-10 flex h-9 items-center justify-between",
            button_previous:
              "flex size-8 items-center justify-center rounded-lg hover:bg-muted [&>svg]:size-4 [&>svg]:fill-current",
            button_next:
              "flex size-8 items-center justify-center rounded-lg hover:bg-muted [&>svg]:size-4 [&>svg]:fill-current",
            weekdays: "flex",
            weekday:
              "w-9 py-1.5 text-center text-2xs font-semibold uppercase text-muted-foreground",
            week: "flex",
            day: "p-0",
            day_button:
              "num flex size-9 items-center justify-center rounded-lg text-sm hover:bg-muted aria-selected:hover:bg-primary",
            today: "[&>button]:font-bold [&>button]:text-primary",
            selected:
              "[&>button]:bg-primary [&>button]:text-primary-foreground",
            outside: "[&>button]:text-muted-foreground/40",
            disabled: "[&>button]:opacity-30",
          }}
        />
        <div className="mt-1 flex items-center justify-between border-t pt-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange(toValue(new Date()))
              setOpen(false)
            }}
          >
            Bugun
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground"
            onClick={() => {
              onChange("")
              setOpen(false)
            }}
          >
            Tozalash
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
