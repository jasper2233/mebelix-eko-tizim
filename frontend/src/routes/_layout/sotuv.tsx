import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft, Plus, Printer, RotateCcw, X } from "lucide-react"
import { useEffect, useState } from "react"

import type { CatalogItemRead } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { SelectField } from "@/components/Common/SelectField"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { CatalogPicker } from "@/components/Warehouse/CatalogPicker"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import {
  formatMoney,
  groupThousands,
  isWarehouseStaff,
  moneyToWords,
} from "@/lib/mes"
import { cn } from "@/lib/utils"

export const Route = createFileRoute("/_layout/sotuv")({
  component: SotuvPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Sotuv listi | MebeliX" }] }),
})

//: Brauzerda saqlanadi — sotuvchi sahifani yopib ketsa ham list qolsin.
//: Bazaga YOZILMAYDI (hozircha): list qog'oz hujjat sifatida chop etiladi va
//: MES hisobotlariga kirmaydi. Bazaga ko'chirilsa versiya raqami oshiriladi.
const STORE = "mebelix.sotuv-listi.v1"

type Row = {
  id: number
  /** Katalogdan tanlansa — kodi, artikuli va birligi; erkin qatorda bo'sh */
  code?: string
  article?: string
  unit?: string
  name: string
  qty: number
  price: number
  disc: number
  note: string
}

type Head = {
  client: string
  phone: string
  ctype: string
  addr: string
  order: string
  seller: string
  dateISO: string
  dueISO: string
}

type Sheet = { head: Head; rows: Row[]; seq: number }

const bugun = () => new Date().toISOString().slice(0, 10)

const bosh = (seller = ""): Sheet => ({
  head: {
    client: "",
    phone: "",
    ctype: "Jismoniy shaxs",
    addr: "",
    order: "",
    seller,
    dateISO: bugun(),
    dueISO: "",
  },
  rows: [1, 2, 3].map((id) => ({
    id,
    name: "",
    qty: 0,
    price: 0,
    disc: 0,
    note: "",
  })),
  seq: 4,
})

const son = (s: string) => {
  const v = Number.parseFloat(
    s
      .replace(/\s/g, "")
      .replace(",", ".")
      .replace(/[^0-9.]/g, ""),
  )
  return Number.isNaN(v) ? 0 : v
}

const dmy = (iso: string) => {
  const p = iso.split("-")
  return p.length === 3 ? `${p[2]}.${p[1]}.${p[0]}` : "__.__.____"
}

const qatorSumma = (r: Row) => Math.max(0, r.qty * r.price - r.disc)

function SotuvPage() {
  const { currentUser } = useCurrentUser()
  const [sheet, setSheet] = useState<Sheet>(() => bosh())
  const [shartnoma, setShartnoma] = useState(false)

  // Saqlangani birinchi chizishdan KEYIN o'qiladi: `useState` boshlang'ich
  // qiymatida `localStorage` ga tegish sahifani brauzerdan tashqarida
  // chizganda yiqitardi
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORE)
      if (raw) {
        const s = JSON.parse(raw) as Sheet
        if (s?.head && Array.isArray(s.rows) && s.rows.length) {
          setSheet({ ...bosh(), ...s, head: { ...bosh().head, ...s.head } })
          return
        }
      }
    } catch {
      /* saqlash yo'q — ish davom etadi */
    }
    setSheet(bosh(currentUser?.name ?? ""))
  }, [currentUser?.name])

  useEffect(() => {
    try {
      localStorage.setItem(STORE, JSON.stringify(sheet))
    } catch {
      /* ignore */
    }
  }, [sheet])

  const setHead = (k: keyof Head, v: string) =>
    setSheet((s) => ({ ...s, head: { ...s.head, [k]: v } }))

  const setRow = (id: number, patch: Partial<Row>) =>
    setSheet((s) => ({
      ...s,
      rows: s.rows.map((r) => (r.id === id ? { ...r, ...patch } : r)),
    }))

  const addRow = () =>
    setSheet((s) => ({
      ...s,
      seq: s.seq + 1,
      rows: [
        ...s.rows,
        { id: s.seq, name: "", qty: 0, price: 0, disc: 0, note: "" },
      ],
    }))

  const delRow = (id: number) =>
    setSheet((s) =>
      s.rows.length === 1
        ? s
        : { ...s, rows: s.rows.filter((r) => r.id !== id) },
    )

  const tanlandi = (id: number, item: CatalogItemRead) =>
    setRow(id, {
      name: item.name,
      code: item.code,
      article: item.article ?? undefined,
      unit: item.unit ?? undefined,
      // Narx katalogdan KELADI, lekin qulflanmaydi: chegirma va kelishuv narxi
      // sotuvchining ishi
      price: Math.round(Number(item.sale_price ?? 0)),
      qty: 0,
    })

  const toldirilgan = sheet.rows.filter((r) => r.name.trim() !== "")
  const oraliq = toldirilgan.reduce((a, r) => a + r.qty * r.price, 0)
  const chegirma = toldirilgan.reduce(
    (a, r) => a + Math.min(r.disc, r.qty * r.price),
    0,
  )
  const jami = toldirilgan.reduce((a, r) => a + qatorSumma(r), 0)

  return (
    <div>
      {/* Chop qog'ozi: list — ko'ndalang (8 ustun), shartnoma — bo'yiga */}
      <style>{`@page { size: A4 ${shartnoma ? "portrait" : "landscape"}; margin: 10mm; }`}</style>

      <div className="print-hide">
        <PageHeader
          title="Sotuv listi"
          description="Mahsulotlar katalogdan tanlanadi — kod, artikul va narx o'zi to'ladi"
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="ghost" asChild>
                <Link to="/warehouse">
                  <ArrowLeft className="size-4" /> Omborga
                </Link>
              </Button>
              <Button
                variant="ghost"
                onClick={() => setSheet(bosh(currentUser?.name ?? ""))}
              >
                <RotateCcw className="size-4" /> Yangi list
              </Button>
              <Button
                variant={shartnoma ? "default" : "outline"}
                onClick={() => setShartnoma((v) => !v)}
              >
                {shartnoma ? "Listga qaytish" : "Shartnoma"}
              </Button>
              <Button onClick={() => window.print()}>
                <Printer className="size-4" /> Chop etish
              </Button>
            </div>
          }
        />
      </div>

      {shartnoma ? (
        <Shartnoma head={sheet.head} rows={toldirilgan} jami={jami} />
      ) : (
        <div className="flex flex-col gap-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Karta sarlavha="Mijoz">
              <Maydon label="F.I.Sh. / tashkilot" className="sm:col-span-2">
                <Input
                  value={sheet.head.client}
                  onChange={(e) => setHead("client", e.target.value)}
                  placeholder="Masalan: Jahongir Rustamov"
                />
              </Maydon>
              <Maydon label="Telefon">
                <Input
                  className="num"
                  value={sheet.head.phone}
                  onChange={(e) => setHead("phone", e.target.value)}
                  placeholder="+998 __ ___ __ __"
                />
              </Maydon>
              <Maydon label="Mijoz turi">
                <SelectField
                  value={sheet.head.ctype}
                  onChange={(v) => setHead("ctype", v)}
                  options={["Jismoniy shaxs", "Yuridik shaxs", "Diler"].map(
                    (x) => ({ value: x, label: x }),
                  )}
                />
              </Maydon>
              <Maydon
                label="Manzil / yetkazib berish"
                className="sm:col-span-2"
              >
                <Input
                  value={sheet.head.addr}
                  onChange={(e) => setHead("addr", e.target.value)}
                  placeholder="Shahar, tuman, ko'cha, uy"
                />
              </Maydon>
            </Karta>

            <Karta sarlavha="Buyurtma">
              <Maydon label="Buyurtma №">
                <Input
                  className="num"
                  value={sheet.head.order}
                  onChange={(e) => setHead("order", e.target.value)}
                  placeholder="B-2026-000"
                />
              </Maydon>
              <Maydon label="Sotuvchi">
                <Input
                  value={sheet.head.seller}
                  onChange={(e) => setHead("seller", e.target.value)}
                  placeholder="Xodim F.I.Sh."
                />
              </Maydon>
              <Maydon label="Sana">
                <Input
                  className="num"
                  type="date"
                  value={sheet.head.dateISO}
                  onChange={(e) => setHead("dateISO", e.target.value)}
                />
              </Maydon>
              <Maydon label="Topshirish muddati">
                <Input
                  className="num"
                  type="date"
                  value={sheet.head.dueISO}
                  onChange={(e) => setHead("dueISO", e.target.value)}
                />
              </Maydon>
            </Karta>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-4 px-1">
              <span className="font-semibold">Mahsulotlar</span>
              <span className="text-sm text-muted-foreground">
                {sheet.rows.length} ta qator
              </span>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">№</TableHead>
                  <TableHead className="min-w-[240px]">Mahsulot</TableHead>
                  <TableHead className="w-28 text-right">Soni</TableHead>
                  <TableHead className="w-32 text-right">Narxi</TableHead>
                  <TableHead className="w-28 text-right">Chegirma</TableHead>
                  <TableHead className="w-32 text-right">Summa</TableHead>
                  <TableHead className="w-40">Izoh</TableHead>
                  <TableHead className="print-hide w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sheet.rows.map((r, i) => (
                  <TableRow key={r.id}>
                    <TableCell className="num align-top text-muted-foreground">
                      {i + 1}
                    </TableCell>
                    <TableCell className="align-top">
                      <CatalogPicker
                        value={r.name}
                        onText={(t) =>
                          // Nom qo'lda o'zgartirildi — katalog bog'lami uziladi
                          setRow(r.id, {
                            name: t,
                            code: undefined,
                            article: undefined,
                          })
                        }
                        onPick={(item) => tanlandi(r.id, item)}
                      />
                      {/* Kod va artikul — KATALOGDAN, qo'lda yozilmaydi */}
                      <div className="num px-2 pt-0.5 text-[11px] tracking-wide text-muted-foreground">
                        {r.code
                          ? [r.code, r.article].filter(Boolean).join(" · ")
                          : r.name.trim()
                            ? "katalogda yo'q — erkin qator"
                            : ""}
                      </div>
                    </TableCell>
                    <RaqamKatak
                      value={r.qty}
                      kasr
                      suffix={r.unit}
                      onChange={(v) => setRow(r.id, { qty: v })}
                    />
                    <RaqamKatak
                      value={r.price}
                      onChange={(v) => setRow(r.id, { price: v })}
                    />
                    <RaqamKatak
                      value={r.disc}
                      muted
                      onChange={(v) => setRow(r.id, { disc: v })}
                    />
                    <TableCell className="num text-right align-top font-semibold">
                      {formatMoney(qatorSumma(r))}
                    </TableCell>
                    <TableCell className="align-top">
                      <Input
                        value={r.note}
                        onChange={(e) => setRow(r.id, { note: e.target.value })}
                        placeholder="—"
                        className="h-8 border-transparent bg-transparent px-2 text-sm hover:border-input focus-visible:bg-background"
                      />
                    </TableCell>
                    <TableCell className="print-hide text-right align-top">
                      <button
                        type="button"
                        title="Qatorni o'chirish"
                        onClick={() => delRow(r.id)}
                        className="rounded-md border p-1 text-muted-foreground hover:border-destructive/40 hover:text-destructive"
                      >
                        <X className="size-3.5" />
                      </button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="print-hide mt-2">
              <Button variant="outline" size="sm" onClick={addRow}>
                <Plus className="size-4" /> Yangi qator
              </Button>
            </div>
          </div>

          <div className="flex justify-end">
            <div className="w-full max-w-sm rounded-lg border bg-card p-5">
              <Jami label="Mahsulotlar summasi" value={formatMoney(oraliq)} />
              <Jami
                label="Chegirma"
                value={`− ${formatMoney(chegirma)}`}
                muted
              />
              <div className="my-3 h-px bg-border" />
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Jami summa
                </span>
                <span className="num text-2xl font-bold">
                  {formatMoney(jami)}{" "}
                  <span className="text-sm font-semibold text-muted-foreground">
                    so'm
                  </span>
                </span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap justify-between gap-10 px-1 text-sm text-muted-foreground">
            {["Sotuvchi imzosi", "Mijoz imzosi"].map((x) => (
              <div key={x} className="flex flex-col gap-6">
                <span>{x}</span>
                <span className="w-52 border-b border-dashed" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Karta({
  sarlavha,
  children,
}: {
  sarlavha: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border bg-card">
      <div className="border-b bg-muted/30 px-5 py-2.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {sarlavha}
      </div>
      <div className="grid gap-4 p-5 sm:grid-cols-2">{children}</div>
    </div>
  )
}

function Maydon({
  label,
  className,
  children,
}: {
  label: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {children}
    </div>
  )
}

/** Raqam katagi: fokusda xom son, fokusdan chiqqach minglik bo'shliqlari bilan.
 *  Vergul KASR, minglik emas (`lib/mes` dagi pul qoidasi bilan bir xil) —
 *  ekrandan nusxalab maydonga qo'yilganda ma'nosi o'zgarmaydi. */
function RaqamKatak({
  value,
  onChange,
  kasr,
  suffix,
  muted,
}: {
  value: number
  onChange: (v: number) => void
  kasr?: boolean
  suffix?: string
  muted?: boolean
}) {
  const [fokus, setFokus] = useState(false)
  const korinish = value
    ? fokus || kasr
      ? String(value).replace(".", ",")
      : groupThousands(String(Math.round(value)))
    : ""
  return (
    <TableCell className="align-top">
      <div className="flex items-baseline justify-end gap-1">
        <Input
          inputMode="decimal"
          value={korinish}
          onFocus={(e) => {
            setFokus(true)
            e.currentTarget.select()
          }}
          onBlur={() => setFokus(false)}
          onChange={(e) => onChange(son(e.target.value))}
          placeholder="0"
          className={cn(
            "num h-8 border-transparent bg-transparent px-2 text-right hover:border-input focus-visible:bg-background",
            muted && "text-amber-700",
          )}
        />
        {suffix && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {suffix}
          </span>
        )}
      </div>
    </TableCell>
  )
}

function Jami({
  label,
  value,
  muted,
}: {
  label: string
  value: string
  muted?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={cn("num font-semibold", muted && "text-amber-700")}>
        {value}
      </span>
    </div>
  )
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

/** Shartnoma — qog'oz hujjat: serif shrift, qora ramkali jadval, imzo bloklari. */
function Shartnoma({
  head,
  rows,
  jami,
}: {
  head: Head
  rows: Row[]
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
            <TableHead className="w-36">Kod · artikul</TableHead>
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
            <TableRow key={r.id}>
              <TableCell className="num text-center">{i + 1}</TableCell>
              <TableCell>
                {r.name}
                {r.note && (
                  <span className="text-muted-foreground"> — {r.note}</span>
                )}
              </TableCell>
              <TableCell className="num text-xs">
                {[r.code, r.article].filter(Boolean).join(" · ") || "—"}
              </TableCell>
              <TableCell className="num text-center">
                {r.qty}
                {r.unit ? ` ${r.unit}` : ""}
              </TableCell>
              <TableCell className="num text-right">
                {formatMoney(r.price)}
              </TableCell>
              <TableCell className="num text-right font-semibold">
                {formatMoney(qatorSumma(r))}
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
