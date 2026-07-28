import type * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Yuza uslubi. `rounded-xl border bg-card` yetti joyda qo'lda takrorlangan edi;
 * ba'zilari `<div>` emas (`<ul>`, `<details>`, `<section>`), shuning uchun
 * komponentdan tashqari klass konstantasi ham eksport qilinadi.
 *
 * shadcn'ning to'liq Card API'si (Header/Title/Description/Content/Footer)
 * ataylab olinmadi — bu kodbazada sarlavhalar sahifa darajasida beriladi,
 * besh qismli abstraksiya ishlatilmay qolardi.
 */
export const cardSurface = "rounded-xl border bg-card"

export function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="card" className={cn(cardSurface, className)} {...props} />
  )
}
