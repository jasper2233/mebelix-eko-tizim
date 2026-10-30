import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ExternalLink } from "lucide-react"
import { type ReactNode, useEffect, useState } from "react"

import { MoliyaService } from "@/client"
import { EsfHolat } from "@/components/Common/EsfHolat"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import {
  formatDate,
  formatDateTime,
  formatMoney,
  isMoliya,
  isProductionStaff,
  ORDER_STATUS_LABELS,
} from "@/lib/mes"
import { cn } from "@/lib/utils"

// Hisobot qatoridan manba hujjatga o'tish (ERP sharhlarida «drill-down» yo'qligi — eng ko'p shikoyatlardan).
// Moliyachi ishlab chiqarish sahifasini ko'rmaydi, shuning uchun buyurtma bu yerda faqat pul tomonidan
// ochiladi: summa, kassa orderlari, qarz, ESF, tannarx. Oyna `_layout` da bitta; havolalar hodisa yuboradi.

const OCHISH = "mebelix:buyurtma-karta"

export function openBuyurtmaKarta(orderId: number) {
  window.dispatchEvent(new CustomEvent(OCHISH, { detail: orderId }))
}

/** Hisobotdagi buyurtma raqami — bosilsa karta ochiladi */
export function BuyurtmaHavola({
  id,
  children,
}: {
  id: number | null | undefined
  children: ReactNode
}) {
  if (id == null) return <>{children}</>
  return (
    <button
      type="button"
      onClick={() => openBuyurtmaKarta(id)}
      className="cursor-pointer underline decoration-dotted underline-offset-2 hover:text-primary"
      title="Buyurtma kartasi: to'lovlar, ESF, tannarx"
    >
      {children}
    </button>
  )
}

const MAQSAD: Record<string, string> = {
  avans: "Avans",
  tolov: "To'lov",
  qarz: "Qarz to'lovi",
  qaytarish: "Qaytarish",
  sotuv: "Sotuv",
  boshqa: "Boshqa",
}

const num = "num text-right whitespace-nowrap"

export function BuyurtmaKartaOyna() {
  const { currentUser } = useCurrentUser()
  const [id, setId] = useState<number | null>(null)
  const ruxsat = isMoliya(currentUser)

  useEffect(() => {
    const on = (e: Event) => setId((e as CustomEvent<number>).detail)
    window.addEventListener(OCHISH, on)
    return () => window.removeEventListener(OCHISH, on)
  }, [])

  const { data: k, error } = useQuery({
    queryKey: ["moliya", "buyurtma-karta", id],
    queryFn: async () =>
      (await MoliyaService.moliyaBuyurtmaKarta({ path: { order_id: id ?? 0 } }))
        .data,
    enabled: ruxsat && id != null,
  })

  if (!ruxsat) return null
  const qator = (nom: string, v: ReactNode, cls?: string) => (
    <div className="flex justify-between gap-4 py-1">
      <span className="text-muted-foreground">{nom}</span>
      <span className={cn("num text-right", cls)}>{v}</span>
    </div>
  )

  return (
    <Sheet open={id != null} onOpenChange={(o) => !o && setId(null)}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{k ? `Buyurtma ${k.number}` : "Buyurtma"}</SheetTitle>
          <SheetDescription>
            {k
              ? `${k.mijoz} · ${ORDER_STATUS_LABELS[k.status as keyof typeof ORDER_STATUS_LABELS] ?? k.status}`
              : error
                ? "Buyurtma topilmadi"
                : "Yuklanmoqda…"}
          </SheetDescription>
        </SheetHeader>
        {k && (
          <div className="flex flex-col gap-5 px-4 pb-6 text-sm">
            <section>
              {qator("Yaratilgan", formatDate(k.yaratilgan))}
              {k.muddat && qator("Muddat", formatDate(k.muddat))}
              {qator(
                "Topshirilgan",
                k.topshirilgan ? formatDate(k.topshirilgan) : "hali yo'q",
              )}
            </section>

            <section className="rounded-md border p-3">
              {qator(
                "Buyurtma summasi",
                k.summa == null ? "yozilmagan" : formatMoney(k.summa),
                "font-semibold",
              )}
              {qator("To'langan", formatMoney(k.tolangan))}
              {Number(k.kassagacha) > 0 &&
                qator("shundan kassagacha", formatMoney(k.kassagacha))}
              {qator(
                "Qarz",
                formatMoney(k.qarz),
                cn("font-semibold", Number(k.qarz) > 0 && "text-red-700"),
              )}
            </section>

            <section>
              <h3 className="mb-1 font-medium">Kassa orderlari</h3>
              {k.tolovlar.length === 0 ? (
                <p className="text-muted-foreground">Kassadan to'lov yo'q</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Sana</TableHead>
                      <TableHead>Order</TableHead>
                      <TableHead className="text-right">Summa</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {k.tolovlar.map((t) => (
                      <TableRow
                        key={t.kassa_order_id}
                        className={cn(t.storno && "text-muted-foreground")}
                      >
                        <TableCell className="whitespace-nowrap">
                          {formatDateTime(t.sana)}
                        </TableCell>
                        <TableCell>
                          <span className="font-mono text-xs">{t.no}</span>
                          <div className="text-xs text-muted-foreground">
                            {t.storno
                              ? "storno"
                              : (MAQSAD[t.maqsad] ?? t.maqsad)}{" "}
                            · {t.hisob}
                          </div>
                        </TableCell>
                        <TableCell
                          className={cn(
                            num,
                            Number(t.summa) < 0 && "text-red-700",
                          )}
                        >
                          {formatMoney(t.summa)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </section>

            <section>
              <h3 className="mb-1 font-medium">ESF</h3>
              {k.esflar.length === 0 ? (
                <p className="text-muted-foreground">ESF yozilmagan</p>
              ) : (
                k.esflar.map((e) => (
                  <div
                    key={e.id}
                    className="flex items-center justify-between gap-3 py-1"
                  >
                    <span>
                      <span className="font-mono text-xs">{e.no}</span>{" "}
                      <span className="text-muted-foreground">
                        {formatDate(e.sana)}
                      </span>
                    </span>
                    <span className="flex items-center gap-2">
                      <EsfHolat h={e.holat} />
                      <span className="num">{formatMoney(e.jami)}</span>
                    </span>
                  </div>
                ))
              )}
            </section>

            <section className="rounded-md border p-3">
              {qator("Material (FIFO)", formatMoney(k.material))}
              {qator("Mehnat (ishbay)", formatMoney(k.mehnat))}
              {qator("Tannarx", formatMoney(k.tannarx), "font-semibold")}
              {/* Foyda faqat topshirilganda (P&L ham shunday): jarayonda tannarx hali to'liq emas */}
              {k.foyda != null &&
                k.topshirilgan &&
                qator(
                  "Foyda",
                  formatMoney(k.foyda),
                  cn(
                    "font-semibold",
                    Number(k.foyda) < 0 ? "text-red-700" : "text-emerald-700",
                  ),
                )}
              {Number(k.tannarx) === 0 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Tannarx hali yo'q: material chiqimi yoki tasdiqlangan vedomost
                  yozilmagan.
                </p>
              )}
            </section>

            {isProductionStaff(currentUser) && (
              <Link
                to="/orders/$orderId"
                params={{ orderId: String(k.order_id) }}
                onClick={() => setId(null)}
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                Ishlab chiqarish sahifasi <ExternalLink className="size-3.5" />
              </Link>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
