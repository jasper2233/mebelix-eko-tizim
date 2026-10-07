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

const p = (n: number) => String(n).padStart(2, "0")

function toValue(d: Date): string {
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

// `lib/mes.ts` dagi formatDate EMAS: u `new Date(value)` bilan parslaydi (UTC
// yarim tuni), bu yerda esa sana LOKAL komponentlardan quriladi — tanlangan
// katak bilan ko'rinadigan matn hech qachon bir kunga siljimasin.
function display(value: string): string {
  const d = toDate(value)
  if (!d) return ""
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}`
}

export function DatePicker({
  value,
  onChange,
  placeholder = "Sanani tanlang",
  className,
  disablePast = false,
  "aria-label": ariaLabel,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  /** Bugundan oldingi kunlar xira va tanlanmaydi — kelajakdagi sana so'raladigan joyda
   *  (yangi buyurtma muddati). Hisobot, log va sozlama sanalari o'tgan kunni tanlaydi. */
  disablePast?: boolean
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
              value && "pr-10 has-[>svg]:pr-10",
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
      <PopoverContent>
        <DayPicker
          mode="single"
          locale={uz}
          selected={selected}
          defaultMonth={selected}
          onSelect={(d) => {
            onChange(d ? toValue(d) : "")
            setOpen(false)
          }}
          // O'tgan oyga o'tish ataylab ochiq: `startMonth` qo'yilsa react-day-picker undan oldingi kunlarni
          // bo'sh katak qiladi, `flex` qatorda birinchi hafta chapga suriladi va sana boshqa hafta kuni ostiga tushadi
          disabled={disablePast ? { before: new Date() } : undefined}
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
            // Bugun — tizimdagi «bugun» rangi (amber, jadvaldagi bugungi muddat ham shu): och amber fon va
            // qalin to'q amber raqam (6.41:1). Ilgari qalin `text-primary` edi — oddiy kun raqami bilan
            // kontrasti 1.56:1, ya'ni bugun ko'zga tashlanmasdi. Halqa emas, fon: ilovada amber halqa — fokus.
            // Rang faqat TANLANMAGAN bugunga (`data-selected` katakda, tugmada emas): tanlangani to'q ko'k.
            today:
              "[&>button]:font-bold [&:not([data-selected])>button]:bg-amber-100 [&:not([data-selected])>button]:text-amber-800 [&:not([data-selected])>button]:hover:bg-amber-200",
            selected:
              "[&>button]:bg-primary [&>button]:text-primary-foreground",
            // Qo'shni oy kunlari tanlanadi — xira (tanlanmaydigan) o'tgan kunlardan to'qroq bo'lsin
            outside: "[&>button]:text-muted-foreground/70",
            disabled:
              "[&>button]:cursor-not-allowed [&>button]:opacity-30 [&>button]:hover:bg-transparent",
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
