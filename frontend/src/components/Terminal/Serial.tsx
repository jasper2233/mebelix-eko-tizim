// Nusxa ID'i (chekdagi satr bilan aynan bir xil) — buyurtma prefiksi XIRA,
// farqlovchi qism QALIN. ID `B-2026-047_301401_01_001_1` ko'rinishiga o'tgach
// (qr-serialization) 32 belgigacha cho'zildi; prefiks ekrandagi har qatorda
// takrorlanadi va sarlavhada allaqachon turadi — ko'z farqlovchi qismga tushsin.
// Prefikssiz eski ID'lar o'zgarishsiz chiqadi (regex mos kelmaydi).

import { ORDER_PREFIX } from "@/lib/mes"
import { cn } from "@/lib/utils"

export function Serial({
  code,
  className,
}: {
  code: string
  className?: string
}) {
  const prefiks = ORDER_PREFIX.exec(code)?.[0]
  return (
    <span className={cn("num whitespace-nowrap", className)} title={code}>
      {prefiks ? (
        <>
          <span className="font-medium text-muted-foreground">{prefiks}</span>
          {code.slice(prefiks.length)}
        </>
      ) : (
        code
      )}
    </span>
  )
}
