// Moliya ichidagi EKO 10 ekranlari (ish haqi, tannarx) uchun umumiy bo'laklar.

import { TriangleAlert } from "lucide-react"
import type { ReactNode } from "react"

import { cardSurface } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

export const BIRLIK: Record<string, string> = {
  m2: "m²",
  meter: "metr",
  piece: "dona",
}
export const td = "border-b px-2 py-2"
export const tdNum = "num border-b px-2 py-2 text-right whitespace-nowrap"
export const sana = (d: Date) => d.toLocaleDateString("sv-SE")
export const bugun = () => sana(new Date())
export const kecha = () => {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return sana(d)
}
export const birlik = (b: string) => BIRLIK[b] ?? b

export function Karta({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className={cn(cardSurface, "flex flex-col gap-2 p-4")}>
      <h2 className="font-semibold">{title}</h2>
      {children}
    </section>
  )
}

export function Jadval({
  bosh,
  ong = [],
  children,
}: {
  bosh: string[]
  ong?: number[]
  children: ReactNode
}) {
  return (
    <div className="overflow-x-auto">
      <Table className="w-full text-sm">
        <TableHeader>
          <TableRow className="border-b text-left text-xs text-muted-foreground uppercase">
            {bosh.map((h, i) => (
              <TableHead
                key={h || i}
                className={cn(
                  "px-2 py-2 font-medium",
                  ong.includes(i) && "text-right",
                )}
              >
                {h}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>{children}</TableBody>
      </Table>
    </div>
  )
}

export function Xato({ text }: { text: string }) {
  if (!text) return null
  return (
    <div className="flex items-start gap-2 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-900">
      <TriangleAlert className="mt-0.5 size-4 shrink-0" />
      {text}
    </div>
  )
}

export const Bosh = ({ text }: { text: string }) => (
  <p className="p-2 text-sm text-muted-foreground">{text}</p>
)
