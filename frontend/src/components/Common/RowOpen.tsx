// «Bu qator nimadir ochadi» ishorasi — o'ng chetdagi kichik strelka.
//
// Ilgari yagona belgi `cursor-pointer` va qator yonishi edi. Ammo `TableRow`
// ning O'ZIDA `hover:bg-muted/50` bor, ya'ni Hodimlar, Ish markazlari, MES
// agentlar va Hisobotlar qatorlari ham yonadi — hech narsa ochmasa ham. Ya'ni
// yonish "men bosiladi" degani emas edi va foydalanuvchi buni faqat bosib
// ko'rib bilardi.
//
// Strelka FAQAT qator bosilganda sahifa/dialog/panel ochiladigan jadvallarda:
// Buyurtmalar (sahifa), Kontragentlar (karta), Loglar (panel). Tanlash uchun
// bosiladigan qator (terminal PRISADKA) strelka OLMAYDI — u hech narsa ochmaydi.

import { ChevronRight } from "lucide-react"

import { TableCell } from "@/components/ui/table"

export function RowOpenCell() {
  return (
    <TableCell className="w-6 px-1 md:w-8 md:pr-3 md:pl-2">
      {/* Bezak: qatorning o'zi bosiladi, strelka alohida nishon emas */}
      <ChevronRight
        aria-hidden
        className="ml-auto size-4 text-muted-foreground/50"
      />
    </TableCell>
  )
}
