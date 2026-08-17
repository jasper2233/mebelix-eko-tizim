import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export type SelectOption = {
  value: string
  label: string
  /** Ikkinchi darajali matn — kod, telefon, guruh. Asosiy yorliqni uzaytirmaydi. */
  hint?: string
}

/** Dialoglardagi tanlov maydoni.
 *
 * Xom `<select>` ISHLATILMAYDI: u brauzerning o'z ko'rinishida chiqadi va
 * yonidagi `Input`/`Button` bilan bir xil bo'lmaydi — balandligi, burchagi,
 * shrifti, fokus halqasi boshqacha. Formada bitta shunday maydon butun
 * dialogni "tayyor shablon" qilib ko'rsatadi.
 *
 * Radix `Select` ni har dialogda beshta komponent bilan yozish o'rniga shu
 * o'ram: tanlov maydoni loyihada BIR XIL ko'rinishi kerak, ya'ni uning shakli
 * bitta joyda turishi kerak.
 *
 * Bo'sh qiymat (`""`) Radix'da ruxsat etilmaydi, shuning uchun `emptyLabel`
 * berilsa u ichki sentinel qiymat bilan ifodalanadi va tashqariga `""` qaytadi. */
const EMPTY = "__empty__"

export function SelectField({
  value,
  onChange,
  options,
  placeholder,
  emptyLabel,
  disabled,
  className,
}: {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  /** "— tanlanmagan —" varianti. Berilmasa bo'sh variant ko'rsatilmaydi. */
  emptyLabel?: string
  disabled?: boolean
  className?: string
}) {
  return (
    <Select
      value={value === "" ? (emptyLabel ? EMPTY : undefined) : value}
      onValueChange={(v) => onChange(v === EMPTY ? "" : v)}
      disabled={disabled}
    >
      <SelectTrigger className={className ?? "w-full"}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {emptyLabel && <SelectItem value={EMPTY}>{emptyLabel}</SelectItem>}
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
            {!!o.hint && (
              <span className="ml-1.5 text-muted-foreground">{o.hint}</span>
            )}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
