import { Delete } from "lucide-react"

import { Button } from "@/components/ui/button"

export type PinEmployeeOption = {
  id: number
  full_name: string
  position: string | null
}

/** Skaneri yo'q postda kirish (ARRA — u yerda chek chiqarish skanning o'zi, ya'ni
 * skaner faqat kirish uchun sotib olinardi). Ikki qadam: ismni bosish + 4 raqam.
 *
 * Klaviatura KERAK EMAS — monoblokda u yo'q. Barcha tugmalar barmoq uchun katta,
 * raqam paneli telefon qulfi tartibida (1-9, ostida 0) — bu tartib odamlarga
 * tanish, ya'ni qarab o'tirmasdan teriladi. */
export function PinPad({
  employees,
  selected,
  onSelect,
  digits,
  onDigits,
  onComplete,
  pending,
  error,
}: {
  employees: PinEmployeeOption[]
  selected: PinEmployeeOption | null
  onSelect: (e: PinEmployeeOption | null) => void
  digits: string
  onDigits: (v: string) => void
  onComplete: (pin: string) => void
  pending: boolean
  error: string
}) {
  if (!selected) {
    if (!employees.length)
      return (
        <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
          Kod bilan kiradigan hodim yo'q. Admin Hodimlar bo'limidan kod
          o'rnatishi kerak.
        </p>
      )
    return (
      <div className="grid grid-cols-2 gap-2">
        {employees.map((e) => (
          <Button
            key={e.id}
            type="button"
            variant="outline"
            className="h-16 flex-col gap-0.5 text-base font-bold"
            onClick={() => onSelect(e)}
          >
            {e.full_name}
            {!!e.position && (
              <span className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
                {e.position}
              </span>
            )}
          </Button>
        ))}
      </div>
    )
  }

  const tap = (d: string) => {
    if (digits.length >= 4 || pending) return
    const next = digits + d
    onDigits(next)
    // Oxirgi raqam kirishni O'ZI boshlaydi — "tasdiqlash" tugmasi yo'q, kod
    // uzunligi qat'iy 4. Effekt orqali emas, aynan shu yerdan: effekt har
    // renderda qayta baholanib, ikki marta yuborilib ketish xavfini tug'dirardi.
    if (next.length === 4) onComplete(next)
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <button
        type="button"
        className="text-base font-bold underline-offset-4 hover:underline"
        onClick={() => onSelect(null)}
      >
        {selected.full_name}
      </button>

      <div className="flex gap-3" aria-label="Terilgan raqamlar">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={`h-3.5 w-3.5 rounded-full border-2 ${
              i < digits.length
                ? "border-primary bg-primary"
                : "border-muted-foreground/40"
            }`}
          />
        ))}
      </div>

      {!!error && (
        <div
          role="alert"
          className="w-full rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-center text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <div className="grid w-full max-w-[15rem] grid-cols-3 gap-2">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <Button
            key={d}
            type="button"
            variant="outline"
            className="h-14 text-xl font-bold"
            onClick={() => tap(d)}
          >
            {d}
          </Button>
        ))}
        <span />
        <Button
          type="button"
          variant="outline"
          className="h-14 text-xl font-bold"
          onClick={() => tap("0")}
        >
          0
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="h-14"
          aria-label="O'chirish"
          disabled={!digits.length || pending}
          onClick={() => onDigits(digits.slice(0, -1))}
        >
          <Delete className="size-6" />
        </Button>
      </div>
    </div>
  )
}
