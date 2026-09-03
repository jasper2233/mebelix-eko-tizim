// Nusxa ID'i (chekdagi satr bilan aynan bir xil) — buyurtma prefiksi XIRA,
// farqlovchi qism QALIN. ID `B-2026-047_301401_01_001_1` ko'rinishiga o'tgach
// (qr-serialization) 32 belgigacha cho'zildi; prefiks ekrandagi har qatorda
// takrorlanadi va sarlavhada allaqachon turadi — ko'z farqlovchi qismga tushsin.
// Prefikssiz eski ID'lar o'zgarishsiz chiqadi (regex mos kelmaydi).

import { cn } from "@/lib/utils"

const ORDER_PREFIX = /^(B-\d{4}-\d+_)(.+)$/i

export function Serial({
  code,
  className,
}: {
  code: string
  className?: string
}) {
  const m = ORDER_PREFIX.exec(code)
  return (
    <span className={cn("num whitespace-nowrap", className)} title={code}>
      {m ? (
        <>
          <span className="font-medium text-muted-foreground">{m[1]}</span>
          {m[2]}
        </>
      ) : (
        code
      )}
    </span>
  )
}
