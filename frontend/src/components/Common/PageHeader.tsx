import type { ReactNode } from "react"

export function PageHeader({
  title,
  titleAside,
  description,
  actions,
}: {
  title: string
  /** Sarlavha bilan BIR QATORDA turadigan element (holat/prioritet badge'lari,
   *  bosqichlar) — alohida qator o'rniga; tor ekranda pastga buqiladi */
  titleAside?: ReactNode
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h1 className="text-xl font-bold tracking-tight md:text-2xl">
            {title}
          </h1>
          {titleAside}
        </div>
        {/* `div`: description badge qatori ham bo'lishi mumkin (buyurtma sahifasi) —
            `<p>` ichida blok element HTML'da noto'g'ri */}
        {description && (
          <div className="mt-1 text-sm text-muted-foreground">
            {description}
          </div>
        )}
      </div>
      {/* `flex-wrap`: qidiruv + tugma birga kelganda (Mijozlar, Hodimlar) telefonda
          qator sig'maydi va butun sahifa yonga skroll bo'lardi — 390 px da
          o'lchandi (sahifa kengligi 441/434 px). Endi tugma pastga tushadi. */}
      {/* Telefonda to'liq kenglik — ichidagi qidiruv `w-full` shunga tayanadi */}
      {actions && (
        <div className="flex w-full flex-wrap items-center gap-2 md:w-auto">
          {actions}
        </div>
      )}
    </div>
  )
}
