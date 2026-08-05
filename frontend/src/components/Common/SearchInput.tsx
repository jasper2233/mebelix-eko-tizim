import { Search } from "lucide-react"

import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

/**
 * Qidiruv maydoni — ichida Search ikonkasi.
 *
 * Reyestr sahifalarida (mijozlar, hodimlar, buyurtmalar, materiallar, loglar)
 * bir xil `relative` div + absolyut ikonka + `pl-8` Input naqshi qo'lda
 * takrorlanardi. Kenglik/joylashuv (`max-w-sm`, `w-72`, `ml-auto`...)
 * `className` orqali chaqiruvchidan.
 */
export function SearchInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}) {
  return (
    <div className={cn("relative", className)}>
      <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
      <Input
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="pl-8"
      />
    </div>
  )
}
