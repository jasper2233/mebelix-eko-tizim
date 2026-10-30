// Moliya (EKO TZ §8, 3-daraja; tuzilishi `Moliya.dc.html` prototipidan): pul qayerda, kim kimga qarzdor, oy
// foydasi. Raqamlarning hammasi jurnallardan (kassa orderlari, ombor hujjatlari) — bu sahifa pul yozmaydi;
// yagona "yozuv" amallari: storno (ikki kalit), rejali to'lov, sozlamalar va davr yopish.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Download, Printer, TriangleAlert } from "lucide-react"
import { type ReactNode, useState } from "react"

import {
  type Akt,
  type Debitor,
  KassaService,
  type KunOqim,
  MoliyaService,
  type OyOqim,
  type Qator,
} from "@/client"
import { client } from "@/client/client.gen"
import { useTasdiq } from "@/components/Common/useTasdiq"
import { BuyurtmaHavola } from "@/components/Moliya/BuyurtmaKarta"
import { IshHaqi } from "@/components/Moliya/IshHaqi"
import { Tannarx } from "@/components/Moliya/Tannarx"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { MOLIYA_BOLIMLAR } from "@/lib/bolimlar"
import { requireAccess } from "@/lib/guards"
import { formatDate, formatDateTime, formatMoney, isMoliya } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { num, parseNum } from "@/lib/warehouse"
import { extractErrorMessage } from "@/utils"

const BOLIMLAR = MOLIYA_BOLIMLAR
type Bolim = (typeof BOLIMLAR)[number]["v"]

export const Route = createFileRoute("/_layout/moliya")({
  component: MoliyaPage,
  beforeLoad: requireAccess(isMoliya),
  validateSearch: (s: Record<string, unknown>): { b: Bolim } => ({
    b: BOLIMLAR.some((x) => x.v === s.b) ? (s.b as Bolim) : "bosh",
  }),
  head: () => ({ meta: [{ title: "Moliya | MebeliX" }] }),
})

/** Kirim / chiqim grafigi ranglari — dataviz palitrasining 1- va 2-slotlari (ko'k, to'q sariq; CVD tekshirilgan) */
const KIRIM_RANG = "#2a78d6"
const CHIQIM_RANG = "#eb6834"
const bugun = () => new Date().toLocaleDateString("sv-SE")
const oyBoshi = () => `${bugun().slice(0, 8)}01`

function MoliyaPage() {
  const { b } = Route.useSearch()
  const navigate = useNavigate({ from: "/moliya" })
  const ochish = (v: Bolim) => navigate({ search: { b: v } })
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <h1 className="mr-4 text-xl font-bold">MOLIYA</h1>
        {BOLIMLAR.map((x) => (
          <button
            key={x.v}
            type="button"
            onClick={() => ochish(x.v)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm",
              b === x.v && "border-primary bg-primary text-primary-foreground",
            )}
          >
            {x.l}
          </button>
        ))}
      </div>
      {b === "bosh" && <BoshSahifa ochish={ochish} />}
      {b === "debitorlar" && <Debitorlar />}
      {b === "kreditorlar" && <Kreditorlar />}
      {b === "kalendar" && <Kalendar />}
      {b === "jurnal" && <Jurnal />}
      {b === "smenalar" && <Smenalar />}
      {b === "hisobotlar" && <Hisobotlar />}
      {b === "ishhaqi" && <IshHaqi />}
      {b === "tannarx" && <Tannarx />}
      {b === "davrlar" && <Davrlar />}
      {b === "sozlamalar" && <Sozlamalar />}
    </div>
  )
}

// ───────────────────────── umumiy bo'laklar ─────────────────────────
function Karta({
  title,
  children,
  className,
}: {
  title?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn(cardSurface, "flex flex-col gap-2 p-4", className)}>
      {title && <h2 className="font-semibold">{title}</h2>}
      {children}
    </section>
  )
}

function Kpi({
  l,
  v,
  izoh,
  danger,
}: {
  l: string
  v: string
  izoh?: ReactNode
  danger?: boolean
}) {
  return (
    <div className={cn(cardSurface, "p-4")}>
      <div className="text-xs text-muted-foreground uppercase">{l}</div>
      <div
        className={cn("num mt-1 text-2xl font-bold", danger && "text-red-700")}
      >
        {v}
      </div>
      {izoh && <div className="mt-1 text-xs text-muted-foreground">{izoh}</div>}
    </div>
  )
}

function Jadval({
  bosh,
  children,
  bosh_ong = [],
}: {
  bosh: string[]
  children: ReactNode
  bosh_ong?: number[]
}) {
  return (
    <div className="overflow-x-auto">
      <Table className="w-full text-sm">
        <TableHeader>
          <TableRow className="border-b text-left text-xs text-muted-foreground uppercase">
            {bosh.map((h, i) => (
              <TableHead
                key={h}
                className={cn(
                  "px-2 py-2 font-medium",
                  bosh_ong.includes(i) && "text-right",
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

const td = "border-b px-2 py-2"
const tdNum = "num border-b px-2 py-2 text-right whitespace-nowrap"

function Bosh({ text }: { text: string }) {
  return <p className="p-2 text-sm text-muted-foreground">{text}</p>
}

function Xato({ text }: { text: string }) {
  if (!text) return null
  return (
    <div className="flex items-start gap-2 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-900">
      <TriangleAlert className="mt-0.5 size-4 shrink-0" />
      {text}
    </div>
  )
}

/** Kirim/chiqim yonma-yon ustunlari: legenda, hover'da sana va ikkala summa (dataviz: yagona o'q, ingichka ustun) */
function OqimGrafik({
  rows,
  belgi,
}: {
  rows: { k: string; kirim: number; chiqim: number }[]
  belgi: (k: string) => string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const max = Math.max(1, ...rows.flatMap((r) => [r.kirim, r.chiqim]))
  const h = hover != null ? rows[hover] : null
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span
            className="inline-block size-3 rounded-sm"
            style={{ background: KIRIM_RANG }}
          />
          Kirim
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block size-3 rounded-sm"
            style={{ background: CHIQIM_RANG }}
          />
          Chiqim
        </span>
        <span className="ml-auto min-h-4 text-foreground">
          {h ? (
            <>
              <b>{belgi(h.k)}</b> · kirim{" "}
              <span className="num">{formatMoney(h.kirim)}</span> · chiqim{" "}
              <span className="num">{formatMoney(h.chiqim)}</span>
            </>
          ) : (
            "Ustun ustiga olib boring"
          )}
        </span>
      </div>
      {/* biome-ignore lint/a11y/noStaticElementInteractions: hover faqat tooltip uchun, qiymatlar aria-label da */}
      <div
        className="flex h-40 items-end border-b border-border"
        onMouseLeave={() => setHover(null)}
      >
        {rows.map((r, i) => (
          <div
            key={r.k}
            role="img"
            aria-label={`${belgi(r.k)}: kirim ${formatMoney(r.kirim)}, chiqim ${formatMoney(r.chiqim)}`}
            className={cn(
              "flex h-full flex-1 items-end justify-center gap-0.5 px-px",
              hover === i && "bg-muted/60",
            )}
            onMouseEnter={() => setHover(i)}
          >
            {[r.kirim, r.chiqim].map((v, j) => (
              <div
                key={j}
                className="w-full max-w-3 rounded-t"
                style={{
                  height: `${(v / max) * 100}%`,
                  minHeight: v > 0 ? 2 : 0,
                  background: j === 0 ? KIRIM_RANG : CHIQIM_RANG,
                }}
              />
            ))}
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{rows[0] && belgi(rows[0].k)}</span>
        <span>{rows.length > 0 && belgi(rows[rows.length - 1].k)}</span>
      </div>
    </div>
  )
}

function PnlJadval({
  p,
}: {
  p: {
    sotuv_buyurtma: string
    sotuv_ombor: string
    sotuv: string
    sotuv_qqs?: string
    sof_tushum?: string
    aylanma_soliq?: string
    tannarx: string
    yalpi: string
    xarajatlar: Qator[]
    kassa_farqi: string
    xarajat_jami: string
    sof: string
  }
}) {
  const qator = (l: string, v: string | number, cls?: string) => (
    <TableRow key={l} className={cls}>
      <TableCell className={td}>{l}</TableCell>
      <TableCell className={tdNum}>{formatMoney(v)}</TableCell>
    </TableRow>
  )
  return (
    <Table className="w-full text-sm">
      <TableBody>
        {qator("Sotuv — buyurtmalar", p.sotuv_buyurtma)}
        {qator("Sotuv — do'kon (ombor chiqimi)", p.sotuv_ombor)}
        {qator("Sotuv jami", p.sotuv, "font-semibold")}
        {num(p.sotuv_qqs) !== 0 && (
          <>
            {qator("Sotuvdagi QQS (byudjetga)", -num(p.sotuv_qqs))}
            {qator("Sof tushum", p.sof_tushum ?? 0, "font-semibold")}
          </>
        )}
        {qator("Tannarx (FIFO)", -num(p.tannarx))}
        {qator("Yalpi foyda", p.yalpi, "font-semibold")}
        {p.xarajatlar.map((x) => qator(`   ${x.nom}`, -num(x.summa)))}
        {num(p.aylanma_soliq) !== 0 &&
          qator("   Aylanmadan soliq", -num(p.aylanma_soliq))}
        {num(p.kassa_farqi) !== 0 &&
          qator("   Kassa kamomadi (smena farqi)", -num(p.kassa_farqi))}
        {qator("Xarajatlar jami", -num(p.xarajat_jami))}
        {qator(
          "Sof foyda",
          p.sof,
          cn("text-base font-bold", num(p.sof) < 0 && "text-red-700"),
        )}
      </TableBody>
    </Table>
  )
}

// ───────────────────────── bosh sahifa ─────────────────────────
function BoshSahifa({ ochish }: { ochish: (b: Bolim) => void }) {
  const { data: d, isLoading } = useQuery({
    queryKey: ["moliya", "bosh"],
    queryFn: async () => (await MoliyaService.moliyaBosh()).data,
  })
  if (isLoading || !d) return <Skeleton className="h-96" />
  const k30 = d.kunlar.reduce((a, x) => a + num(x.kirim), 0)
  const c30 = d.kunlar.reduce((a, x) => a + num(x.chiqim), 0)
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 md:grid-cols-4">
        <Kpi
          l="Pul mablag'lari"
          v={formatMoney(d.pul)}
          izoh={d.hisoblar
            .map((h) => `${h.nom}: ${formatMoney(h.qoldiq)}`)
            .join(" · ")}
        />
        <Kpi
          l="Mijozlar qarzi"
          v={formatMoney(d.debitorlik)}
          danger={num(d.muddati_otgan) > 0}
          izoh={
            <>
              {d.debitor_soni} mijoz · muddati o'tgan{" "}
              {formatMoney(d.muddati_otgan)} · olingan avans{" "}
              {formatMoney(d.olingan_avans)}
            </>
          }
        />
        <Kpi
          l="Bizning qarz"
          v={formatMoney(d.kreditorlik)}
          izoh="ta'minotchilarga"
        />
        <Kpi
          l="Rejali to'lovlar · 30 kun"
          v={formatMoney(d.rejali_30)}
          izoh="ijara, kredit va boshqalar"
        />
      </div>
      <div className="grid gap-3 xl:grid-cols-[1fr_1fr]">
        <Karta title={`Bugungi vazifalar · ${d.vazifalar.length}`}>
          {d.vazifalar.length === 0 && <Bosh text="Bugun vazifa yo'q ✓" />}
          {d.vazifalar.map((v) => (
            <button
              key={`${v.bolim}-${v.matn}`}
              type="button"
              onClick={() => ochish(v.bolim as Bolim)}
              className="flex items-center justify-between gap-3 rounded border px-3 py-2 text-left text-sm hover:bg-muted"
            >
              <span>
                <b>{v.matn}</b>
                <span className="block text-xs text-muted-foreground">
                  {v.izoh}
                </span>
              </span>
              {v.summa != null && (
                <span className="num font-semibold">
                  {formatMoney(v.summa)}
                </span>
              )}
            </button>
          ))}
        </Karta>
        <Karta
          title={
            <span className="flex flex-wrap justify-between gap-2">
              Pul oqimi · 30 kun
              <span className="num text-sm font-normal text-muted-foreground">
                kirim {formatMoney(k30)} · chiqim {formatMoney(c30)} · saldo{" "}
                {formatMoney(k30 - c30)}
              </span>
            </span>
          }
        >
          <OqimGrafik
            rows={d.kunlar.map((x: KunOqim) => ({
              k: x.sana,
              kirim: num(x.kirim),
              chiqim: num(x.chiqim),
            }))}
            belgi={(k) => formatDate(k)}
          />
        </Karta>
      </div>
      <Karta
        title={
          <span className="flex justify-between">
            Shu oy foyda va zarar
            <button
              type="button"
              className="text-sm font-normal text-primary"
              onClick={() => ochish("hisobotlar")}
            >
              Batafsil →
            </button>
          </span>
        }
        className="max-w-2xl"
      >
        <PnlJadval p={d.pnl} />
      </Karta>
    </div>
  )
}

// ───────────────────────── debitorlar ─────────────────────────
function Debitorlar() {
  const { data } = useQuery({
    queryKey: ["moliya", "debitorlar"],
    queryFn: async () => (await MoliyaService.moliyaDebitorlar()).data,
  })
  const [tanlangan, setTanlangan] = useState<Debitor | null>(null)
  const [akt, setAkt] = useState<number | null>(null)
  if (akt != null)
    return <AktSverki clientId={akt} onBack={() => setAkt(null)} />
  const jami = (data ?? []).reduce((a, d) => a + num(d.qarz), 0)
  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_24rem]">
      <Karta
        title={`Debitorlar: ${data?.length ?? 0} · qarz jami ${formatMoney(jami)}`}
      >
        <Jadval
          bosh={["Mijoz", "Qarz", "Kun / muddat", "Avans", "Limit"]}
          bosh_ong={[1, 3, 4]}
        >
          {(data ?? []).map((d) => (
            <TableRow
              key={d.client_id}
              onClick={() => setTanlangan(d)}
              className={cn(
                "cursor-pointer hover:bg-muted/50",
                tanlangan?.client_id === d.client_id && "bg-primary/5",
              )}
            >
              <TableCell className={td}>
                <b>{d.mijoz}</b>
                <div className="text-xs text-muted-foreground">
                  {d.telefon}
                  {d.shartnoma_no && ` · shartnoma ${d.shartnoma_no}`}
                </div>
              </TableCell>
              <TableCell className={cn(tdNum, "font-semibold")}>
                {formatMoney(d.qarz)}
              </TableCell>
              <TableCell
                className={cn(
                  td,
                  "whitespace-nowrap",
                  d.muddati_otgan && "font-semibold text-red-700",
                )}
              >
                {d.kun != null ? `${d.kun} / ${d.muddat_kun} kun` : "—"}
                {d.muddati_otgan &&
                  ` · o'tgan ${formatMoney(d.muddati_otgan_summa)}`}
              </TableCell>
              <TableCell className={tdNum}>{formatMoney(d.avans)}</TableCell>
              <TableCell
                className={cn(
                  tdNum,
                  d.limitdan_oshgan && "font-semibold text-red-700",
                )}
              >
                {d.limit != null ? formatMoney(d.limit) : "—"}
              </TableCell>
            </TableRow>
          ))}
        </Jadval>
        {data?.length === 0 && <Bosh text="Ro'yxat bo'sh" />}
      </Karta>
      {tanlangan ? (
        <MijozPanel
          key={tanlangan.client_id}
          d={tanlangan}
          onAkt={() => setAkt(tanlangan.client_id)}
        />
      ) : (
        <Karta>
          <Bosh text="Mijozni tanlang: shartnoma, to'lov muddati, limit va akt sverki" />
        </Karta>
      )}
    </div>
  )
}

function MijozPanel({ d, onAkt }: { d: Debitor; onAkt: () => void }) {
  const qc = useQueryClient()
  const [sh, setSh] = useState(d.shartnoma_no)
  const [muddat, setMuddat] = useState(String(d.muddat_kun))
  const [limit, setLimit] = useState(
    d.limit != null ? String(num(d.limit)) : "",
  )
  const [xato, setXato] = useState("")
  const saqla = useMutation({
    mutationFn: async () =>
      MoliyaService.moliyaMijozShart({
        path: { client_id: d.client_id },
        body: {
          shartnoma_no: sh,
          muddat_kun: muddat === "" ? null : Number(muddat),
          kredit_limit:
            parseNum(limit) != null ? String(parseNum(limit)) : null,
        },
      }),
    onSuccess: () => {
      setXato("")
      qc.invalidateQueries({ queryKey: ["moliya"] })
    },
    onError: (e) => setXato(extractErrorMessage(e)),
  })
  return (
    <Karta title={d.mijoz}>
      <div className="grid grid-cols-3 gap-2 rounded bg-muted/40 p-3 text-sm">
        <div>
          <div className="text-xs text-muted-foreground">QARZ</div>
          <b className="num">{formatMoney(d.qarz)}</b>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">SOTUV</div>
          <b className="num">{formatMoney(d.sotuv)}</b>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">TO'LANGAN</div>
          <b className="num">{formatMoney(d.tolangan)}</b>
        </div>
      </div>
      <div className="text-xs text-muted-foreground uppercase">
        Shartnoma №
        <Input value={sh} onChange={(e) => setSh(e.target.value)} />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="text-xs text-muted-foreground uppercase">
          Muddat, kun
          <Input
            inputMode="numeric"
            value={muddat}
            onChange={(e) => setMuddat(e.target.value.replace(/\D/g, ""))}
          />
        </div>
        <div className="text-xs text-muted-foreground uppercase">
          Qarz limiti, so'm
          <Input
            inputMode="decimal"
            value={limit}
            onChange={(e) => setLimit(e.target.value.replace(/[^0-9.,]/g, ""))}
          />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Limitdan oshsa doimiy mijoz to'lovsiz ishlab chiqarishga o'tmaydi;
        muddat o'tsa Bosh sahifada vazifa chiqadi.
      </p>
      <Xato text={xato} />
      <div className="flex gap-2">
        <LoadingButton loading={saqla.isPending} onClick={() => saqla.mutate()}>
          Saqlash
        </LoadingButton>
        <Button variant="outline" onClick={onAkt}>
          <Printer /> Akt sverki
        </Button>
      </div>
    </Karta>
  )
}

function AktSverki({
  clientId,
  onBack,
}: {
  clientId: number
  onBack: () => void
}) {
  const [dan, setDan] = useState(`${bugun().slice(0, 4)}-01-01`)
  const [gacha, setGacha] = useState(bugun())
  const { data: a } = useQuery({
    queryKey: ["moliya", "akt", clientId, dan, gacha],
    queryFn: async () =>
      (
        await MoliyaService.moliyaAkt({
          path: { client_id: clientId },
          query: { dan, gacha },
        })
      ).data,
  })
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <Button variant="outline" onClick={onBack}>
          ← Ro'yxatga
        </Button>
        <Input
          type="date"
          className="w-40"
          value={dan}
          onChange={(e) => setDan(e.target.value)}
        />
        <Input
          type="date"
          className="w-40"
          value={gacha}
          onChange={(e) => setGacha(e.target.value)}
        />
        <Button onClick={() => window.print()}>
          <Printer /> Chop etish (A4)
        </Button>
      </div>
      {a && <AktVaraq a={a} />}
    </div>
  )
}

function AktVaraq({ a }: { a: Akt }) {
  const saldo = (v: string) =>
    num(v) > 0
      ? `${formatMoney(v)} — mijoz qarzdor`
      : num(v) < 0
        ? `${formatMoney(-num(v))} — korxona qarzdor (avans)`
        : "0 — qarz yo'q"
  return (
    <div className="mx-auto w-full max-w-3xl bg-white p-8 text-sm text-black shadow print:shadow-none">
      <h2 className="text-center text-lg font-bold">
        Solishtirma dalolatnoma (akt sverki)
      </h2>
      <p className="text-center">
        {formatDate(a.dan)} — {formatDate(a.gacha)} · {a.mijoz}
      </p>
      <p className="mt-4">
        Davr boshiga saldo: <b>{saldo(a.boshlangich)}</b>
      </p>
      <Table className="mt-2 w-full border-collapse text-xs">
        <TableHeader>
          <TableRow>
            {["Sana", "Hujjat", "Mazmuni", "Debet", "Kredit", "Saldo"].map(
              (h) => (
                <TableHead key={h} className="border border-black px-1 py-1">
                  {h}
                </TableHead>
              ),
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {a.qatorlar.map((q, i) => (
            <TableRow key={i}>
              <TableCell className="border border-black px-1">
                {formatDate(q.sana)}
              </TableCell>
              <TableCell className="border border-black px-1">
                {q.hujjat}
              </TableCell>
              <TableCell className="border border-black px-1">
                {q.izoh}
              </TableCell>
              <TableCell className="num border border-black px-1 text-right">
                {num(q.debet) ? formatMoney(q.debet) : ""}
              </TableCell>
              <TableCell className="num border border-black px-1 text-right">
                {num(q.kredit) ? formatMoney(q.kredit) : ""}
              </TableCell>
              <TableCell className="num border border-black px-1 text-right">
                {formatMoney(q.saldo)}
              </TableCell>
            </TableRow>
          ))}
          <TableRow className="font-bold">
            <TableCell className="border border-black px-1" colSpan={3}>
              Aylanma
            </TableCell>
            <TableCell className="num border border-black px-1 text-right">
              {formatMoney(a.debet)}
            </TableCell>
            <TableCell className="num border border-black px-1 text-right">
              {formatMoney(a.kredit)}
            </TableCell>
            <TableCell className="border border-black px-1" />
          </TableRow>
        </TableBody>
      </Table>
      <p className="mt-3">
        Davr oxiriga saldo: <b>{saldo(a.yakuniy)}</b>
      </p>
      <div className="mt-12 grid grid-cols-2 gap-8">
        <div>Korxona: ______________</div>
        <div>Mijoz: ______________</div>
      </div>
    </div>
  )
}

// ───────────────────────── kreditorlar ─────────────────────────
function Kreditorlar() {
  const { data } = useQuery({
    queryKey: ["moliya", "kreditorlar"],
    queryFn: async () => (await MoliyaService.moliyaKreditorlar()).data,
  })
  const jami = (data ?? []).reduce((a, d) => a + num(d.qarz), 0)
  return (
    <Karta title={`Kreditorlik qarzi: ${formatMoney(jami)}`}>
      <Jadval
        bosh={[
          "Ta'minotchi",
          "Faktura",
          "To'langan",
          "Qarz",
          "Avans",
          "Muddat",
        ]}
        bosh_ong={[1, 2, 3, 4]}
      >
        {(data ?? []).map((k) => (
          <TableRow key={k.nom}>
            <TableCell className={td}>
              <b>{k.nom}</b>
              <div className="text-xs text-muted-foreground">
                {k.hujjatlar} kirim hujjati
              </div>
            </TableCell>
            <TableCell className={tdNum}>{formatMoney(k.faktura)}</TableCell>
            <TableCell className={tdNum}>{formatMoney(k.tolangan)}</TableCell>
            <TableCell className={cn(tdNum, "font-semibold")}>
              {formatMoney(k.qarz)}
            </TableCell>
            <TableCell className={tdNum}>{formatMoney(k.avans)}</TableCell>
            <TableCell
              className={cn(
                td,
                k.muddat && k.muddat < bugun() && "font-semibold text-red-700",
              )}
            >
              {k.muddat ? formatDate(k.muddat) : "—"}
            </TableCell>
          </TableRow>
        ))}
      </Jadval>
      {data?.length === 0 && (
        <Bosh text="Qarz yo'q. Ombor kirimi tasdiqlangach ta'minotchi shu yerda ko'rinadi" />
      )}
      <p className="text-xs text-muted-foreground">
        To'lov — Kassada «Ta'minotchiga» chiqimi, kontragent nomi kirim
        hujjatidagi bilan bir xil bo'lsin; eng eski hujjatdan yopiladi.
      </p>
    </Karta>
  )
}

// ───────────────────────── kalendar va rejalar ─────────────────────────
function Kalendar() {
  const qc = useQueryClient()
  const { data } = useQuery({
    queryKey: ["moliya", "kalendar"],
    queryFn: async () =>
      (await MoliyaService.moliyaKalendar({ query: { kun: 45 } })).data,
  })
  const { data: rejalar } = useQuery({
    queryKey: ["moliya", "rejalar"],
    queryFn: async () => (await MoliyaService.moliyaRejalar()).data,
  })
  const [nom, setNom] = useState("")
  const [summa, setSumma] = useState("")
  const [takror, setTakror] = useState<"oylik" | "bir">("oylik")
  const [sana, setSana] = useState(bugun())
  const [xato, setXato] = useState("")
  const qosh = useMutation({
    mutationFn: async () =>
      MoliyaService.moliyaRejaQosh({
        body: {
          nom,
          summa: String(parseNum(summa) ?? 0),
          takror,
          sana,
          tur: "chiqim",
        },
      }),
    onSuccess: () => {
      setNom("")
      setSumma("")
      setXato("")
      qc.invalidateQueries({ queryKey: ["moliya"] })
    },
    onError: (e) => setXato(extractErrorMessage(e)),
  })
  const ochir = useMutation({
    mutationFn: async (r: NonNullable<typeof rejalar>[number]) =>
      MoliyaService.moliyaRejaSaqla({
        path: { reja_id: r.id },
        body: { ...r, faol: !r.faol },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["moliya"] }),
  })
  const kirim = (data ?? []).filter((r) => r.tur === "kirim")
  const chiqim = (data ?? []).filter((r) => r.tur === "chiqim")
  const sum = (x: typeof kirim) => x.reduce((a, r) => a + num(r.summa), 0)
  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_26rem]">
      <Karta
        title={`Yaqin 45 kun · kutilayotgan kirim ${formatMoney(sum(kirim))} · to'lov ${formatMoney(sum(chiqim))}`}
      >
        <Jadval bosh={["Sana", "Nima", "Manba", "Summa"]} bosh_ong={[3]}>
          {(data ?? []).map((r, i) => (
            <TableRow key={i} className={cn(r.muddati_otgan && "text-red-700")}>
              <TableCell className={cn(td, "whitespace-nowrap")}>
                {formatDate(r.sana)}
                {r.muddati_otgan && " · o'tgan"}
              </TableCell>
              <TableCell className={td}>{r.nom}</TableCell>
              <TableCell className={cn(td, "text-xs text-muted-foreground")}>
                {r.manba === "mijoz"
                  ? "mijozdan"
                  : r.manba === "taminotchi"
                    ? "ta'minotchiga"
                    : "rejali"}
              </TableCell>
              <TableCell className={cn(tdNum, "font-semibold")}>
                {r.tur === "kirim" ? "+" : "−"}
                {formatMoney(r.summa)}
              </TableCell>
            </TableRow>
          ))}
        </Jadval>
        {data?.length === 0 && <Bosh text="Yaqin 45 kunda to'lov yo'q" />}
      </Karta>
      <Karta title="Rejali to'lovlar">
        <Input
          placeholder="Nomi (ijara, kredit…)"
          value={nom}
          onChange={(e) => setNom(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-2">
          <Input
            placeholder="Summa, so'm"
            inputMode="decimal"
            value={summa}
            onChange={(e) => setSumma(e.target.value.replace(/[^0-9.,]/g, ""))}
          />
          <Input
            type="date"
            value={sana}
            onChange={(e) => setSana(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          {(["oylik", "bir"] as const).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={takror === t ? "default" : "outline"}
              onClick={() => setTakror(t)}
            >
              {t === "oylik" ? "Har oy" : "Bir marta"}
            </Button>
          ))}
          <LoadingButton
            size="sm"
            className="ml-auto"
            loading={qosh.isPending}
            disabled={!nom.trim() || !parseNum(summa)}
            onClick={() => qosh.mutate()}
          >
            Saqlash
          </LoadingButton>
        </div>
        <Xato text={xato} />
        {(rejalar ?? []).map((r) => (
          <div
            key={r.id}
            className={cn(
              "flex items-center justify-between gap-2 border-b py-2 text-sm",
              !r.faol && "text-muted-foreground line-through",
            )}
          >
            <span>
              <b>{r.nom}</b>
              <span className="block text-xs text-muted-foreground">
                {r.takror === "oylik"
                  ? `har oy ${r.sana.slice(8)}-kuni`
                  : formatDate(r.sana)}
              </span>
            </span>
            <span className="num">{formatMoney(r.summa)}</span>
            <Button size="sm" variant="ghost" onClick={() => ochir.mutate(r)}>
              {r.faol ? "To'xtatish" : "Yoqish"}
            </Button>
          </div>
        ))}
      </Karta>
    </div>
  )
}

// ───────────────────────── orderlar jurnali ─────────────────────────
function Jurnal() {
  const qc = useQueryClient()
  const [q, setQ] = useState("")
  const [dan, setDan] = useState(oyBoshi())
  const [gacha, setGacha] = useState(bugun())
  const [storno, setStorno] = useState<{ id: number; no: string } | null>(null)
  const [sabab, setSabab] = useState("")
  const [xato, setXato] = useState("")
  const { data } = useQuery({
    queryKey: ["kassa", "orderlar", "jurnal", q],
    queryFn: async () =>
      (await KassaService.kassaOrderlar({ query: { q, limit: 500 } })).data,
  })
  const qil = useMutation({
    mutationFn: async () =>
      storno &&
      (
        await KassaService.kassaStorno({
          path: { kassa_order_id: storno.id },
          body: { sabab },
        })
      ).data,
    onSuccess: () => {
      setStorno(null)
      setSabab("")
      setXato("")
      qc.invalidateQueries({ queryKey: ["kassa"] })
      qc.invalidateQueries({ queryKey: ["moliya"] })
    },
    onError: (e) => setXato(extractErrorMessage(e)),
  })
  // CSV `client.instance` orqali — token yangilanishi va xato toast'i ishlaydi (reports.tsx kabi)
  const csv = useMutation({
    mutationFn: async () => {
      const res = await client.instance.get<Blob>(
        `/api/v1/moliya/jurnal.csv?dan=${dan}&gacha=${gacha}`,
        { responseType: "blob" },
      )
      const url = URL.createObjectURL(res.data)
      const a = document.createElement("a")
      a.href = url
      a.download = `orderlar_${dan}_${gacha}.csv`
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 0)
    },
  })
  const rows = (data ?? []).filter(
    (o) =>
      o.created_at.slice(0, 10) >= dan && o.created_at.slice(0, 10) <= gacha,
  )
  const kirim = rows
    .filter((o) => o.tur === "kirim" && o.maqsad !== "otkazma")
    .reduce((a, o) => a + num(o.summa), 0)
  const chiqim = rows
    .filter((o) => o.tur === "chiqim" && o.maqsad !== "otkazma")
    .reduce((a, o) => a + num(o.summa), 0)
  return (
    <Karta>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="w-56"
          placeholder="Order №, kontragent"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Input
          type="date"
          className="w-40"
          value={dan}
          onChange={(e) => setDan(e.target.value)}
        />
        <Input
          type="date"
          className="w-40"
          value={gacha}
          onChange={(e) => setGacha(e.target.value)}
        />
        <LoadingButton
          variant="outline"
          loading={csv.isPending}
          onClick={() => csv.mutate()}
        >
          <Download /> Excel (CSV)
        </LoadingButton>
        <span className="num ml-auto text-sm text-muted-foreground">
          kirim {formatMoney(kirim)} · chiqim {formatMoney(chiqim)} · saldo{" "}
          {formatMoney(kirim - chiqim)} · {rows.length} order
        </span>
      </div>
      <Jadval
        bosh={["Sana", "Order", "Kontragent · modda", "Hisob", "Summa", ""]}
        bosh_ong={[4]}
      >
        {rows.map((o) => {
          const bekor = Boolean(o.storno_no || o.storno_of_id)
          return (
            <TableRow
              key={o.id}
              className={cn(bekor && "text-muted-foreground")}
            >
              <TableCell className={cn(td, "whitespace-nowrap")}>
                {formatDateTime(o.created_at)}
              </TableCell>
              <TableCell className={cn(td, "font-mono text-xs")}>
                {o.no}
              </TableCell>
              <TableCell className={td}>
                {o.kontragent || "—"}
                {o.order_number && (
                  <>
                    {" · "}
                    <BuyurtmaHavola id={o.order_id}>
                      {o.order_number}
                    </BuyurtmaHavola>
                  </>
                )}
                <div className="text-xs text-muted-foreground">
                  {o.turkum || o.maqsad}
                  {o.storno_no && (
                    <span className="text-red-700">
                      {" "}
                      · storno {o.storno_no}
                    </span>
                  )}
                  {o.izoh && ` · ${o.izoh}`}
                </div>
              </TableCell>
              <TableCell className={td}>{o.hisob}</TableCell>
              <TableCell
                className={cn(
                  tdNum,
                  "font-semibold",
                  !bekor &&
                    (o.tur === "kirim" ? "text-emerald-700" : "text-red-700"),
                )}
              >
                {(o.tur === "kirim") === num(o.summa) >= 0 ? "+" : "−"}
                {formatMoney(Math.abs(num(o.summa)))}
              </TableCell>
              <TableCell className={cn(td, "text-right")}>
                {!bekor && o.maqsad !== "farq" && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setStorno({ id: o.id, no: o.no })}
                  >
                    Storno
                  </Button>
                )}
              </TableCell>
            </TableRow>
          )
        })}
      </Jadval>
      {rows.length === 0 && <Bosh text="Yozuv yo'q" />}
      <Dialog open={storno != null} onOpenChange={(o) => !o && setStorno(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Storno · {storno?.no}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Order o'chirilmaydi — teskari order yoziladi. Orderni yozgan xodim
            uni o'zi storno qila olmaydi (ikki kalit). O'tkazma va komissiya
            juftligi bilan birga qaytadi.
          </p>
          <Input
            placeholder="Sabab"
            value={sabab}
            onChange={(e) => setSabab(e.target.value)}
          />
          <Xato text={xato} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setStorno(null)}>
              Bekor
            </Button>
            <LoadingButton
              loading={qil.isPending}
              disabled={!sabab.trim()}
              onClick={() => qil.mutate()}
            >
              Storno qilish
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Karta>
  )
}

// ───────────────────────── smenalar ─────────────────────────
function Smenalar() {
  const { data } = useQuery({
    queryKey: ["kassa", "smenalar"],
    queryFn: async () =>
      (await KassaService.kassaSmenalar({ query: { limit: 100 } })).data,
  })
  const farqlar = (data ?? []).filter(
    (s) => s.farq != null && num(s.farq) !== 0,
  )
  const kam = farqlar.reduce((a, s) => a + Math.min(num(s.farq), 0), 0)
  const ort = farqlar.reduce((a, s) => a + Math.max(num(s.farq), 0), 0)
  return (
    <Karta
      title={`Smenalar · sanash farqlari: kamomad ${formatMoney(kam)}, ortiqcha ${formatMoney(ort)}`}
    >
      <Jadval
        bosh={[
          "Smena",
          "Kassir",
          "Ochildi",
          "Yopildi",
          "Boshlang'ich",
          "Kirim",
          "Chiqim",
          "Sanaldi",
          "Farq",
        ]}
        bosh_ong={[4, 5, 6, 7, 8]}
      >
        {(data ?? []).map((s) => (
          <TableRow key={s.id}>
            <TableCell className={cn(td, "font-mono text-xs")}>
              {s.no}
            </TableCell>
            <TableCell className={td}>{s.ochgan ?? "—"}</TableCell>
            <TableCell className={cn(td, "whitespace-nowrap")}>
              {formatDateTime(s.ochilgan_at)}
            </TableCell>
            <TableCell
              className={cn(
                td,
                "whitespace-nowrap",
                !s.yopilgan_at && "font-semibold text-amber-700",
              )}
            >
              {s.yopilgan_at ? formatDateTime(s.yopilgan_at) : "ochiq"}
            </TableCell>
            <TableCell className={tdNum}>
              {formatMoney(s.ochilish_naqd)}
            </TableCell>
            <TableCell className={tdNum}>{formatMoney(s.kirim)}</TableCell>
            <TableCell className={tdNum}>{formatMoney(s.chiqim)}</TableCell>
            <TableCell className={tdNum}>
              {formatMoney(s.yopilish_naqd)}
            </TableCell>
            <TableCell
              className={cn(
                tdNum,
                s.farq != null &&
                  num(s.farq) !== 0 &&
                  "font-semibold text-red-700",
              )}
            >
              {formatMoney(s.farq)}
            </TableCell>
          </TableRow>
        ))}
      </Jadval>
      {data?.length === 0 && <Bosh text="Hali smena yo'q" />}
    </Karta>
  )
}

// ───────────────────────── hisobotlar ─────────────────────────
function Hisobotlar() {
  const [oy, setOy] = useState(bugun().slice(0, 7))
  const dan = `${oy}-01`
  const oxir = new Date(Number(oy.slice(0, 4)), Number(oy.slice(5, 7)), 0)
  const gacha =
    oy === bugun().slice(0, 7) ? bugun() : oxir.toLocaleDateString("sv-SE")
  const { data: p } = useQuery({
    queryKey: ["moliya", "pnl", oy],
    queryFn: async () =>
      (await MoliyaService.moliyaPnl({ query: { oy } })).data,
  })
  const { data: o } = useQuery({
    queryKey: ["moliya", "pul-oqimi", dan, gacha],
    queryFn: async () =>
      (await MoliyaService.moliyaPulOqimi({ query: { dan, gacha } })).data,
  })
  const { data: b } = useQuery({
    queryKey: ["moliya", "byudjet", oy],
    queryFn: async () =>
      (await MoliyaService.moliyaByudjet({ query: { oy } })).data,
  })
  const { data: bl } = useQuery({
    queryKey: ["moliya", "balans"],
    queryFn: async () => (await MoliyaService.moliyaBalans()).data,
  })
  const qatorlar = (rows: Qator[], ishora: string) =>
    rows.map((r) => (
      <TableRow key={r.nom}>
        <TableCell className={td}>{r.nom}</TableCell>
        <TableCell className={cn(td, "text-xs text-muted-foreground")}>
          {r.soni} order
        </TableCell>
        <TableCell className={tdNum}>
          {ishora}
          {formatMoney(r.summa)}
        </TableCell>
      </TableRow>
    ))
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 print:hidden">
        <Input
          type="month"
          className="w-44"
          value={oy}
          onChange={(e) => e.target.value && setOy(e.target.value)}
        />
        <Button variant="outline" onClick={() => window.print()}>
          <Printer /> A4
        </Button>
        {p?.yopiq && (
          <span className="rounded bg-muted px-2 py-1 text-xs">
            Oy yopilgan — yopilgan paytdagi natija
          </span>
        )}
      </div>
      <div className="grid gap-3 xl:grid-cols-2">
        <Karta title={`Foyda va zarar · ${oy}`}>
          {p ? <PnlJadval p={p} /> : <Skeleton className="h-64" />}
        </Karta>
        <Karta title="Byudjet · shu oy">
          {(b ?? []).map((r) => (
            <div key={r.nom} className="text-sm">
              <div className="flex justify-between">
                <span>{r.nom}</span>
                <span className="num">
                  {formatMoney(r.fakt)}
                  {r.limit != null && ` / ${formatMoney(r.limit)}`}
                </span>
              </div>
              {r.limit != null && (
                <div className="mt-1 h-1.5 rounded bg-muted">
                  <div
                    className={cn(
                      "h-1.5 rounded",
                      (r.foiz ?? 0) > 100 ? "bg-red-600" : "bg-primary",
                    )}
                    style={{ width: `${Math.min(r.foiz ?? 0, 100)}%` }}
                  />
                </div>
              )}
            </div>
          ))}
          {b?.every((r) => r.limit == null) && (
            <Bosh text="Limit yozilmagan — Sozlamalar → Xarajat moddalari" />
          )}
        </Karta>
      </div>
      {o && (
        <div className="grid gap-3 xl:grid-cols-2">
          <Karta
            title={`Pul oqimi · kirim ${formatMoney(o.kirim)} · chiqim ${formatMoney(o.chiqim)} · saldo ${formatMoney(o.saldo)} (o'tkazmalarsiz)`}
          >
            <Table className="w-full text-sm">
              <TableBody>
                <TableRow>
                  <TableCell
                    colSpan={3}
                    className="pt-1 text-xs font-semibold uppercase"
                  >
                    Kirim — moddalar bo'yicha
                  </TableCell>
                </TableRow>
                {qatorlar(o.kirim_moddalar, "+")}
                <TableRow>
                  <TableCell
                    colSpan={3}
                    className="pt-3 text-xs font-semibold uppercase"
                  >
                    Chiqim — moddalar bo'yicha
                  </TableCell>
                </TableRow>
                {qatorlar(o.chiqim_moddalar, "−")}
              </TableBody>
            </Table>
          </Karta>
          <div className="flex flex-col gap-3">
            <Karta title="12 oy kirim / chiqim">
              <OqimGrafik
                rows={o.oylar.map((x: OyOqim) => ({
                  k: x.oy,
                  kirim: num(x.kirim),
                  chiqim: num(x.chiqim),
                }))}
                belgi={(k) => k}
              />
            </Karta>
            <Karta title="Hisoblar va kassirlar">
              <Jadval
                bosh={["Hisob", "Kirim", "Chiqim", "Qoldiq"]}
                bosh_ong={[1, 2, 3]}
              >
                {o.hisoblar.map((h) => (
                  <TableRow key={h.kod}>
                    <TableCell className={td}>{h.nom}</TableCell>
                    <TableCell className={tdNum}>
                      {formatMoney(h.kirim)}
                    </TableCell>
                    <TableCell className={tdNum}>
                      {formatMoney(h.chiqim)}
                    </TableCell>
                    <TableCell className={cn(tdNum, "font-semibold")}>
                      {formatMoney(h.qoldiq)}
                    </TableCell>
                  </TableRow>
                ))}
                {o.kassirlar.map((k) => (
                  <TableRow key={k.nom} className="text-muted-foreground">
                    <TableCell className={td}>
                      {k.nom} · {k.soni} order
                    </TableCell>
                    <TableCell className={tdNum}>
                      {formatMoney(k.kirim)}
                    </TableCell>
                    <TableCell className={tdNum}>
                      {formatMoney(k.chiqim)}
                    </TableCell>
                    <TableCell className={td} />
                  </TableRow>
                ))}
              </Jadval>
            </Karta>
          </div>
        </div>
      )}
      {bl && (
        <Karta title="Balans · bugun" className="max-w-2xl">
          <Table className="w-full text-sm">
            <TableBody>
              {(
                [
                  ["Pul mablag'lari", bl.pul],
                  ["Mijozlar qarzi", bl.debitorlik],
                  ["Ombor qiymati (tannarxda)", bl.ombor],
                  ["Ta'minotchiga berilgan avans", bl.berilgan_avans],
                  ["Aktivlar jami", bl.aktiv],
                  ["Ta'minotchilarga qarz", bl.kreditorlik],
                  ["Mijozdan olingan avans", bl.olingan_avans],
                  ["Majburiyatlar jami", bl.passiv],
                  ["Sof aktiv (kapital)", bl.sof],
                ] as const
              ).map(([l, v]) => (
                <TableRow
                  key={l}
                  className={cn(
                    l.includes("jami") || l.startsWith("Sof")
                      ? "font-semibold"
                      : "",
                  )}
                >
                  <TableCell className={td}>{l}</TableCell>
                  <TableCell className={tdNum}>{formatMoney(v)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Karta>
      )}
    </div>
  )
}

// ───────────────────────── davr yopish ─────────────────────────
function Davrlar() {
  const qc = useQueryClient()
  const [tasdiqOyna, sora] = useTasdiq()
  const { data } = useQuery({
    queryKey: ["moliya", "davrlar"],
    queryFn: async () => (await MoliyaService.moliyaDavrlar()).data,
  })
  const d = new Date()
  d.setDate(0)
  const [oy, setOy] = useState(d.toLocaleDateString("sv-SE").slice(0, 7))
  const [sabab, setSabab] = useState("")
  const [xato, setXato] = useState("")
  const amal = useMutation({
    mutationFn: async ({
      t,
      o,
    }: {
      t: "yop" | "sorov" | "tasdiq"
      o: string
    }) =>
      t === "yop"
        ? MoliyaService.moliyaDavrYop({ path: { oy: o } })
        : t === "sorov"
          ? MoliyaService.moliyaDavrOchishSorov({
              path: { oy: o },
              body: { sabab },
            })
          : MoliyaService.moliyaDavrOchishTasdiq({ path: { oy: o } }),
    onSuccess: () => {
      setXato("")
      setSabab("")
      qc.invalidateQueries({ queryKey: ["moliya"] })
    },
    onError: (e) => setXato(extractErrorMessage(e)),
  })
  return (
    <Karta title="Davr yopish">
      {tasdiqOyna}
      <p className="text-sm text-muted-foreground">
        Yopilgan oyning sanasi bilan hujjat yozilmaydi va foyda-zarari qotadi.
        Keyingi tuzatish joriy oyda storno bilan. Qayta ochish — ikki kalit: bir
        xodim so'raydi, boshqasi tasdiqlaydi.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="month"
          className="w-44"
          value={oy}
          onChange={(e) => setOy(e.target.value)}
        />
        <LoadingButton
          loading={amal.isPending}
          onClick={() =>
            sora({
              title: `${oy} oyini yopasizmi?`,
              description:
                "Yopilgan oyga orqa sana bilan order, provodka va hujjat yozilmaydi. Qayta ochish — sabab bilan so'rov va boshqa xodimning tasdig'i orqali.",
              confirmText: "Oyni yopish",
              onConfirm: () => amal.mutate({ t: "yop", o: oy }),
            })
          }
        >
          Oyni yopish
        </LoadingButton>
        <Input
          className="w-72"
          placeholder="Qayta ochish sababi"
          value={sabab}
          onChange={(e) => setSabab(e.target.value)}
        />
      </div>
      <Xato text={xato} />
      <Jadval
        bosh={["Oy", "Holat", "Yopdi", "Sof foyda", "Qayta ochish", ""]}
        bosh_ong={[3]}
      >
        {(data ?? []).map((r) => (
          <TableRow key={r.oy}>
            <TableCell className={cn(td, "font-semibold")}>{r.oy}</TableCell>
            <TableCell className={td}>
              {r.holat === "yopiq" ? "yopiq" : "qayta ochilgan"}
            </TableCell>
            <TableCell className={td}>
              {r.yopgan} · {formatDateTime(r.yopilgan_at)}
            </TableCell>
            <TableCell className={tdNum}>
              {r.sof != null ? formatMoney(r.sof) : "—"}
            </TableCell>
            <TableCell className={cn(td, "text-xs")}>
              {r.ochish_sorov && `${r.ochish_sorov} so'radi: ${r.ochish_sabab}`}
              {r.ochgan && ` · ${r.ochgan} tasdiqladi`}
            </TableCell>
            <TableCell className={cn(td, "text-right")}>
              {r.holat === "yopiq" && !r.ochish_sorov && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={!sabab.trim()}
                  onClick={() => amal.mutate({ t: "sorov", o: r.oy })}
                >
                  Ochishni so'rash
                </Button>
              )}
              {r.holat === "yopiq" && r.ochish_sorov && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => amal.mutate({ t: "tasdiq", o: r.oy })}
                >
                  Ochishni tasdiqlash
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </Jadval>
      {data?.length === 0 && <Bosh text="Hali yopilgan oy yo'q" />}
    </Karta>
  )
}

// ───────────────────────── sozlamalar ─────────────────────────
function Sozlamalar() {
  const qc = useQueryClient()
  const [xato, setXato] = useState("")
  const onError = (e: unknown) => setXato(extractErrorMessage(e as Error))
  const ok = () => {
    setXato("")
    qc.invalidateQueries({ queryKey: ["moliya"] })
    qc.invalidateQueries({ queryKey: ["kassa"] })
  }
  const { data: hisoblar } = useQuery({
    queryKey: ["moliya", "hisoblar"],
    queryFn: async () => (await MoliyaService.moliyaHisoblar()).data,
  })
  const { data: soz } = useQuery({
    queryKey: ["moliya", "sozlamalar"],
    queryFn: async () => (await MoliyaService.moliyaSozlamalar()).data,
  })
  const { data: moddalar } = useQuery({
    queryKey: ["moliya", "moddalar"],
    queryFn: async () => (await MoliyaService.moliyaModdalar()).data,
  })
  const [yangi, setYangi] = useState("")
  const hisob = useMutation({
    mutationFn: async (v: {
      kod: string
      boshlangich?: string
      komissiya_foiz?: string
    }) =>
      MoliyaService.moliyaHisobSaqla({
        path: { kod: v.kod },
        body: {
          boshlangich: v.boshlangich ?? null,
          komissiya_foiz: v.komissiya_foiz ?? null,
        },
      }),
    onSuccess: ok,
    onError,
  })
  const sozlama = useMutation({
    mutationFn: async (v: {
      eng_kam_avans_foiz: number
      tolov_muddat_kun: number
    }) => MoliyaService.moliyaSozlamalarSaqla({ body: v }),
    onSuccess: ok,
    onError,
  })
  const modda = useMutation({
    mutationFn: async (v: {
      id?: number
      nom: string
      oylik_limit: string | null
      faol: boolean
    }) =>
      v.id
        ? MoliyaService.moliyaModdaSaqla({ path: { modda_id: v.id }, body: v })
        : MoliyaService.moliyaModdaQosh({ body: v }),
    onSuccess: () => {
      setYangi("")
      ok()
    },
    onError,
  })
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <div className="flex flex-col gap-3">
        <Xato text={xato} />
        <Karta title="Hisoblar">
          <p className="text-xs text-muted-foreground">
            Terminal va bank uchun boshlang'ich qoldiqni bir marta yozing (order
            yozilgach o'zgarmaydi). Naqd kassa birinchi smenada sanalgan puldan
            boshlanadi. Bank komissiyasi chiqimda alohida order bo'lib
            ushlanadi.
          </p>
          {(hisoblar ?? []).map((h) => (
            <div
              key={h.kod}
              className="grid grid-cols-[1fr_9rem_6rem] items-end gap-2 text-sm"
            >
              <div>
                <b>{h.nom}</b>
                <div className="text-xs text-muted-foreground">
                  hozir: {formatMoney(h.qoldiq)}
                </div>
              </div>
              <div className="text-xs text-muted-foreground">
                Boshlang'ich
                <Input
                  key={`b${h.boshlangich}`}
                  className="num text-right"
                  defaultValue={String(num(h.boshlangich))}
                  disabled={h.tur === "naqd"}
                  onBlur={(e) =>
                    parseNum(e.target.value) !== num(h.boshlangich) &&
                    hisob.mutate({
                      kod: h.kod,
                      boshlangich: String(parseNum(e.target.value) ?? 0),
                    })
                  }
                />
              </div>
              <div className="text-xs text-muted-foreground">
                Komissiya, %
                <Input
                  key={`k${h.komissiya_foiz}`}
                  className="num text-right"
                  defaultValue={String(num(h.komissiya_foiz))}
                  disabled={h.tur === "naqd"}
                  onBlur={(e) =>
                    parseNum(e.target.value) !== num(h.komissiya_foiz) &&
                    hisob.mutate({
                      kod: h.kod,
                      komissiya_foiz: String(parseNum(e.target.value) ?? 0),
                    })
                  }
                />
              </div>
            </div>
          ))}
        </Karta>
        {soz && (
          <Karta title="Mijozlar bilan hisob-kitob">
            <div className="grid grid-cols-2 gap-3 text-xs text-muted-foreground">
              <div>
                Eng kam avans, % — shundan kam to'lovda material buyurtmaga
                biriktirilmaydi
                <Input
                  key={`a${soz.eng_kam_avans_foiz}`}
                  className="num mt-1"
                  defaultValue={soz.eng_kam_avans_foiz}
                  onBlur={(e) =>
                    Number(e.target.value) !== soz.eng_kam_avans_foiz &&
                    sozlama.mutate({
                      ...soz,
                      eng_kam_avans_foiz: Number(e.target.value),
                    })
                  }
                />
              </div>
              <div>
                Standart to'lov muddati, kun — shartnomasi yo'q mijoz qarzi
                shundan keyin «muddati o'tgan»
                <Input
                  key={`m${soz.tolov_muddat_kun}`}
                  className="num mt-1"
                  defaultValue={soz.tolov_muddat_kun}
                  onBlur={(e) =>
                    Number(e.target.value) !== soz.tolov_muddat_kun &&
                    sozlama.mutate({
                      ...soz,
                      tolov_muddat_kun: Number(e.target.value),
                    })
                  }
                />
              </div>
            </div>
          </Karta>
        )}
      </div>
      <Karta title="Xarajat moddalari va oylik byudjet">
        {(moddalar ?? []).map((x) => (
          <div
            key={x.id}
            className={cn(
              "grid grid-cols-[1fr_9rem_6rem] items-center gap-2 text-sm",
              !x.faol && "text-muted-foreground",
            )}
          >
            <span className={cn(!x.faol && "line-through")}>{x.nom}</span>
            <Input
              key={`l${x.oylik_limit}`}
              className="num text-right"
              placeholder="limit yo'q"
              defaultValue={
                x.oylik_limit != null ? String(num(x.oylik_limit)) : ""
              }
              onBlur={(e) => {
                const v = parseNum(e.target.value)
                if (v !== (x.oylik_limit != null ? num(x.oylik_limit) : null))
                  modda.mutate({
                    ...x,
                    faol: x.faol ?? true,
                    oylik_limit: v != null ? String(v) : null,
                  })
              }}
            />
            <Button
              size="sm"
              variant="ghost"
              onClick={() =>
                modda.mutate({
                  ...x,
                  oylik_limit: x.oylik_limit ?? null,
                  faol: !x.faol,
                })
              }
            >
              {x.faol ? "O'chirish" : "Yoqish"}
            </Button>
          </div>
        ))}
        <div className="flex gap-2">
          <Input
            placeholder="Yangi modda"
            value={yangi}
            onChange={(e) => setYangi(e.target.value)}
          />
          <LoadingButton
            loading={modda.isPending}
            disabled={!yangi.trim()}
            onClick={() =>
              modda.mutate({ nom: yangi, oylik_limit: null, faol: true })
            }
          >
            Qo'shish
          </LoadingButton>
        </div>
      </Karta>
    </div>
  )
}
