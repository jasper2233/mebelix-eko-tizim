// Sotuv hujjatining «Shartnoma» ko'rinishi — chop etiladigan qog'oz (2026-10-16 gacha `/sotuv`
// sahifasida edi; endi Sotuv (chiqim) hujjatidan ochiladi, docs/14 §9). Huquqiy matn o'zgarmagan.

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatMoney, moneyToWords } from "@/lib/mes"

const dmy = (iso: string) => {
  const p = iso.split("-")
  return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : "__.__.____"
}

//: Shartnomaning ALOHIDA SHARTLARI — huquqiy matn, prototipdan
//: (`docs/mebelix-sotuv-listi.html`) so'zma-so'z ko'chirilgan
const SHARTLAR = [
  "Men, tanlagan dekor va kromka ushbu hujjatda ko'rsatilgan parametrlar va ranglarga to'liq mos keladi.",
  "O'lchamlar hamda kromka yopishtiriladigan taraflarni diqqat bilan tekshirib chiqdim.",
  "Buyurtma tayyor bo'lgach, ushbu hujjatda keltirilgan o'lchamlar bo'yicha hech qanday e'tirozim yo'q.",
  "Ishlab chiqarish muddati to'lov amalga oshirilgan kundan boshlab hisoblanishini tasdiqlayman.",
  "Mijoz tomonidan olib ketilmagan, ishlab chiqarish jarayoni natijasida qolgan yoki u tomonidan qabul qilib olinmagan detallar korxona hududida 3 (uch) kalendar kuni davomida saqlanadi.",
]

export type ShartnomaHead = {
  client: string
  phone: string
  order: string
  seller: string
  dateISO: string
  dueISO: string
}

export type ShartnomaRow = {
  key: string | number
  name: string
  note: string
  code?: string | null
  unit?: string | null
  qty: number
  price: number
  sum: number
}

/** Shartnoma — qog'oz hujjat: serif shrift, qora ramkali jadval, imzo bloklari. */
export function Shartnoma({
  head,
  rows,
  jami,
}: {
  head: ShartnomaHead
  rows: ShartnomaRow[]
  jami: number
}) {
  return (
    <div className="mx-auto max-w-3xl rounded-lg border bg-card p-8 font-serif text-[13px] leading-relaxed print:max-w-none print:rounded-none print:border-0 print:p-0">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
        <span className="justify-self-start rounded bg-muted px-3 py-1 text-[11px] font-bold text-muted-foreground">
          Umumiy
        </span>
        <span className="text-center text-base font-bold tracking-wide">
          SHARTNOMA № {head.order || "____"}
        </span>
        <span className="justify-self-end font-sans text-base font-bold">
          Mebeli<span className="text-sidebar-primary">X</span>
        </span>
      </div>
      <div className="my-3 h-px bg-foreground" />

      <div className="flex justify-between gap-5 font-bold">
        <span>Qabul qilingan: {dmy(head.dateISO)}</span>
        <span>Tayyor bo'lishi: {dmy(head.dueISO)}</span>
      </div>

      <p className="mt-3 text-justify">
        Mazkur buyurtma-shartnoma bir tomondan <b>"MebeliX"</b> (keyingi
        o'rinlarda <b>"Ijrochi"</b> deb ataladi) va ikkinchi tomondan{" "}
        <b>{head.client || "____________"}</b> (telefon:{" "}
        {head.phone || "____________"}, keyingi o'rinlarda <b>"Buyurtmachi"</b>{" "}
        deb ataladi) o'rtasida quyidagilar bo'yicha tuzildi:
      </p>
      <p className="mt-2 text-justify">
        1. Ijrochi ushbu shartnoma va uning ilovasiga (spesifikatsiyaga) muvofiq
        mahsulotlarni tayyorlash hamda xizmatlar ko'rsatish, Buyurtmachi esa
        ularni qabul qilish va to'lovni amalga oshirish majburiyatini oladi.
      </p>

      <div className="my-4 text-center text-sm font-bold tracking-widest text-muted-foreground">
        SPESIFIKATSIYA
      </div>

      <Table className="border-collapse [&_td]:border [&_td]:border-foreground [&_td]:p-1.5 [&_th]:h-auto [&_th]:border [&_th]:border-foreground [&_th]:p-2 [&_th]:text-center [&_th]:text-xs [&_th]:text-foreground">
        <TableHeader>
          <TableRow>
            <TableHead className="w-9">№</TableHead>
            <TableHead>Mahsulot nomi / xizmat turi</TableHead>
            <TableHead className="w-36">Kod</TableHead>
            <TableHead className="w-20">Miqdori</TableHead>
            <TableHead className="w-24">Narxi</TableHead>
            <TableHead className="w-28">Jami</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={6}
                className="text-center text-muted-foreground"
              >
                Qator yo'q
              </TableCell>
            </TableRow>
          )}
          {rows.map((r, i) => (
            <TableRow key={r.key}>
              <TableCell className="num text-center">{i + 1}</TableCell>
              <TableCell>
                {r.name}
                {r.note && (
                  <span className="text-muted-foreground"> — {r.note}</span>
                )}
              </TableCell>
              <TableCell className="num text-xs">{r.code || "—"}</TableCell>
              <TableCell className="num text-center">
                {r.qty}
                {r.unit ? ` ${r.unit}` : ""}
              </TableCell>
              <TableCell className="num text-right">
                {formatMoney(r.price)}
              </TableCell>
              <TableCell className="num text-right font-semibold">
                {formatMoney(r.sum)}
              </TableCell>
            </TableRow>
          ))}
          <TableRow>
            <TableCell colSpan={5} className="text-right font-bold">
              JAMI TO'LOV SUMMASI:
            </TableCell>
            <TableCell className="num text-right font-bold">
              {formatMoney(jami)}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <p className="mt-1.5 text-xs text-muted-foreground">
        Jami summa so'z bilan: {moneyToWords(jami)} so'm.
      </p>

      <div className="my-4 text-center text-sm font-bold tracking-wider text-muted-foreground">
        ALOHIDA SHARTLAR
      </div>
      <ol className="list-inside list-decimal space-y-1 border border-foreground p-3 text-xs leading-snug">
        {SHARTLAR.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ol>

      <div className="mt-6 grid gap-10 sm:grid-cols-2">
        <Imzolar
          sarlavha='"IJROCHI"'
          qatorlar={[
            ["Sotuvchi", head.seller],
            ["Texnolog", ""],
            ["Bazischi", ""],
          ]}
        />
        <Imzolar
          sarlavha='"BUYURTMACHI"'
          qatorlar={[
            ["F.I.Sh", head.client],
            ["Imzo", ""],
            ["Sana", dmy(head.dateISO)],
          ]}
        />
      </div>
    </div>
  )
}

function Imzolar({
  sarlavha,
  qatorlar,
}: {
  sarlavha: string
  qatorlar: [string, string][]
}) {
  return (
    <div>
      <div className="text-center text-sm font-bold">{sarlavha}</div>
      <div className="mt-4 flex flex-col gap-5">
        {qatorlar.map(([k, v]) => (
          <div
            key={k}
            className="flex items-end justify-between gap-3 border-b border-foreground pb-1"
          >
            <span>{k}:</span>
            <span className="font-bold">{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
