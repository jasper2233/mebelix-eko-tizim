import * as React from "react"

import { cn } from "@/lib/utils"

/** Excel kabi ustun kengligi: har ustun o'z kontenti kengligida (`th` — `w-px` + `nowrap`), bo'sh joyni
 *  bitta ustun oladi — matni eng uzun chapga tekislangan ustun (nom, izoh, kontragent). Sana va hujjat
 *  raqami (`PKO-2026-0001`) hisobga olinmaydi. Har jadvalda qo'lda belgilamaslik uchun chizilgandan keyin
 *  tanlanadi: tanadan 30 qator o'qiladi, kenglik o'lchanmaydi (layout siklisiz). */
const QISQA = /^(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}(-\d{2})?|[A-ZА-Я]{1,6}-\d{4}-\d+|—|-)/

function useOsuvchiUstun(ref: React.RefObject<HTMLTableElement | null>) {
  React.useLayoutEffect(() => {
    const t = ref.current
    const bosh = t?.tHead?.rows[0]
    if (!t || !bosh) return
    const ball = new Map<number, number>()
    for (const tr of Array.from(t.tBodies[0]?.rows ?? []).slice(0, 30)) {
      let i = 0
      for (const td of tr.cells) {
        if (td.colSpan === 1 && !td.classList.contains("text-right")) {
          const m = td.textContent?.trim() ?? ""
          if (m && !QISQA.test(m)) ball.set(i, (ball.get(i) ?? 0) + m.length)
        }
        i += td.colSpan
      }
    }
    let eng = -1
    for (const [i, b] of ball) if (eng < 0 || b > (ball.get(eng) ?? 0)) eng = i
    let i = 0
    for (const th of bosh.cells) {
      const kerak = i === eng && th.colSpan === 1 && !!th.textContent?.trim()
      if (th.hasAttribute("data-osadi") !== kerak)
        th.toggleAttribute("data-osadi", kerak)
      i += th.colSpan
    }
  })
}

function Table({ className, ...props }: React.ComponentProps<"table">) {
  const ref = React.useRef<HTMLTableElement>(null)
  useOsuvchiUstun(ref)
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto rounded-lg border"
    >
      <table
        ref={ref}
        data-slot="table"
        className={cn(
          // Excel kabi to'r: har katak vertikal chiziq bilan ajraladi; raqamlar `tabular-nums` — ustun
          // bo'ylab bir tekis. Ustun kengligi — `useOsuvchiUstun`.
          "w-full caption-bottom text-sm",
          "[&_td:not(:last-child)]:border-r [&_th:not(:last-child)]:border-r",
          "[&_th:not([data-osadi])]:w-px [&_td.text-right]:tabular-nums",
          className,
        )}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("bg-muted/50 [&_tr]:border-b", className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "hover:bg-muted/50 data-[state=selected]:bg-muted border-b transition-colors",
        className
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "text-muted-foreground h-11 px-4 text-left align-middle text-xs font-semibold uppercase tracking-wider whitespace-nowrap [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "px-4 py-3 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]",
        className
      )}
      {...props}
    />
  )
}

export { Table, TableHeader, TableBody, TableHead, TableRow, TableCell }
