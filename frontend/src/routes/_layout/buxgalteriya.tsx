// Buxgalteriya (EKO 7, 1C siz): aylanma-saldo vedomosti, schyot kartochkasi, provodkalar, nazorat, sozlamalar.
// Provodkalar manba jurnallaridan avtomatik yasaladi (kassa, ombor, buyurtma, soliq); qo'lda — faqat ish haqi,
// asosiy vosita kabi manbasi yo'q operatsiyalar. Har hisobot oldidan sinxron (backend) — raqamlar doim joriy.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { CheckCircle2, Download, Printer, TriangleAlert } from "lucide-react"
import { type ReactNode, useState } from "react"

import { BuxgalteriyaService, type YozuvRead } from "@/client"
import { client } from "@/client/client.gen"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { requireAccess } from "@/lib/guards"
import { formatDate, formatMoney, isMoliya } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { num } from "@/lib/warehouse"
import { extractErrorMessage } from "@/utils"

const BOLIMLAR = [
  { v: "saldo", l: "Aylanma-saldo" },
  { v: "kartochka", l: "Schyot kartochkasi" },
  { v: "provodkalar", l: "Provodkalar" },
  { v: "nazorat", l: "Nazorat" },
  { v: "sozlamalar", l: "Schyotlar va qoidalar" },
] as const
type Bolim = (typeof BOLIMLAR)[number]["v"]

export const Route = createFileRoute("/_layout/buxgalteriya")({
  component: BuxPage,
  beforeLoad: requireAccess(isMoliya),
  validateSearch: (s: Record<string, unknown>): { b: Bolim; kod?: string } => ({
    b: BOLIMLAR.some((x) => x.v === s.b) ? (s.b as Bolim) : "saldo",
    kod: typeof s.kod === "string" ? s.kod : undefined,
  }),
  head: () => ({ meta: [{ title: "Buxgalteriya | MebeliX" }] }),
})

const bugun = () => new Date().toLocaleDateString("sv-SE")
const oyBoshi = () => `${bugun().slice(0, 8)}01`
const r = "num text-right whitespace-nowrap"
/** Nol bo'lsa bo'sh katak — vedomost o'qilishi uchun */
const pul = (v: string | number) => (num(v) === 0 ? "" : formatMoney(v))

function BuxPage() {
  const { b, kod } = Route.useSearch()
  const navigate = useNavigate({ from: "/buxgalteriya" })
  const [dan, setDan] = useState(oyBoshi())
  const [gacha, setGacha] = useState(bugun())
  const ochish = (v: Bolim, k?: string) =>
    navigate({ search: { b: v, kod: k } })
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <h1 className="mr-4 text-xl font-bold">BUXGALTERIYA</h1>
        {BOLIMLAR.map((x) => (
          <button
            key={x.v}
            type="button"
            onClick={() => ochish(x.v, kod)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm",
              b === x.v && "border-primary bg-primary text-primary-foreground",
            )}
          >
            {x.l}
          </button>
        ))}
        {b !== "nazorat" && b !== "sozlamalar" && (
          <span className="ml-auto flex items-center gap-2">
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
          </span>
        )}
      </div>
      {b === "saldo" && (
        <Saldo dan={dan} gacha={gacha} onKod={(k) => ochish("kartochka", k)} />
      )}
      {b === "kartochka" && (
        <Kartochka
          kod={kod ?? "5010"}
          dan={dan}
          gacha={gacha}
          onKod={(k) => ochish("kartochka", k)}
        />
      )}
      {b === "provodkalar" && <Provodkalar dan={dan} gacha={gacha} />}
      {b === "nazorat" && <Nazorat />}
      {b === "sozlamalar" && <Sozlamalar />}
    </div>
  )
}

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

function Xato({ text }: { text: string }) {
  if (!text) return null
  return (
    <div className="flex items-start gap-2 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-900">
      <TriangleAlert className="mt-0.5 size-4 shrink-0" />
      {text}
    </div>
  )
}

// ───────────────────────── aylanma-saldo ─────────────────────────
function Saldo({
  dan,
  gacha,
  onKod,
}: {
  dan: string
  gacha: string
  onKod: (k: string) => void
}) {
  const { data, isFetching } = useQuery({
    queryKey: ["bux", "saldo", dan, gacha],
    queryFn: async () =>
      (await BuxgalteriyaService.buxAylanmaSaldo({ query: { dan, gacha } }))
        .data,
  })
  const csv = useMutation({
    mutationFn: async () => {
      const res = await client.instance.get<Blob>(
        `/api/v1/bux/aylanma-saldo.csv?dan=${dan}&gacha=${gacha}`,
        {
          responseType: "blob",
        },
      )
      const url = URL.createObjectURL(res.data)
      const a = document.createElement("a")
      a.href = url
      a.download = `aylanma_saldo_${dan}_${gacha}.csv`
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 0)
    },
  })
  const jami = (
    k: "bosh_d" | "bosh_k" | "ayl_d" | "ayl_k" | "yak_d" | "yak_k",
  ) => (data ?? []).reduce((a, x) => a + num(x[k]), 0)
  return (
    <Karta
      title={
        <span className="flex flex-wrap items-center justify-between gap-2">
          Aylanma-saldo vedomosti · {formatDate(dan)} — {formatDate(gacha)}
          <span className="flex gap-2 print:hidden">
            <LoadingButton
              size="sm"
              variant="outline"
              loading={csv.isPending}
              onClick={() => csv.mutate()}
            >
              <Download /> Excel (CSV)
            </LoadingButton>
            <Button size="sm" variant="outline" onClick={() => window.print()}>
              <Printer /> A4
            </Button>
          </span>
        </span>
      }
    >
      <p className="text-xs text-muted-foreground print:hidden">
        4010 va 6010 saldosi har mijoz / yetkazib beruvchi bo'yicha alohida
        (debet — bizga qarz, kredit — avans yoki bizning qarz). Schyotni bosing
        — kartochka ochiladi.
        {isFetching && " Yangilanmoqda…"}
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead rowSpan={2}>Schyot</TableHead>
            <TableHead colSpan={2} className="text-center">
              Boshlang'ich saldo
            </TableHead>
            <TableHead colSpan={2} className="text-center">
              Aylanma
            </TableHead>
            <TableHead colSpan={2} className="text-center">
              Yakuniy saldo
            </TableHead>
          </TableRow>
          <TableRow>
            {["Debet", "Kredit", "Debet", "Kredit", "Debet", "Kredit"].map(
              (h, i) => (
                <TableHead key={`${h}${i}`} className="text-right">
                  {h}
                </TableHead>
              ),
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {(data ?? []).map((x) => (
            <TableRow
              key={x.kod}
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => onKod(x.kod)}
            >
              <TableCell>
                <b className="font-mono">{x.kod}</b>{" "}
                <span className="text-sm">{x.nom}</span>
              </TableCell>
              <TableCell className={r}>{pul(x.bosh_d)}</TableCell>
              <TableCell className={r}>{pul(x.bosh_k)}</TableCell>
              <TableCell className={r}>{pul(x.ayl_d)}</TableCell>
              <TableCell className={r}>{pul(x.ayl_k)}</TableCell>
              <TableCell className={cn(r, "font-semibold")}>
                {pul(x.yak_d)}
              </TableCell>
              <TableCell className={cn(r, "font-semibold")}>
                {pul(x.yak_k)}
              </TableCell>
            </TableRow>
          ))}
          <TableRow className="font-bold">
            <TableCell>Jami</TableCell>
            {(
              ["bosh_d", "bosh_k", "ayl_d", "ayl_k", "yak_d", "yak_k"] as const
            ).map((k) => (
              <TableCell key={k} className={r}>
                {formatMoney(jami(k))}
              </TableCell>
            ))}
          </TableRow>
        </TableBody>
      </Table>
      {data && (
        <p className="text-sm">
          {Math.abs(jami("yak_d") - jami("yak_k")) < 0.01 ? (
            <span className="flex items-center gap-1 text-emerald-700">
              <CheckCircle2 className="size-4" /> Balans: debet = kredit
            </span>
          ) : (
            <span className="text-red-700">
              Balans buzilgan: farq {formatMoney(jami("yak_d") - jami("yak_k"))}
            </span>
          )}
        </p>
      )}
    </Karta>
  )
}

// ───────────────────────── kartochka ─────────────────────────
function Kartochka({
  kod,
  dan,
  gacha,
  onKod,
}: {
  kod: string
  dan: string
  gacha: string
  onKod: (k: string) => void
}) {
  const [k, setK] = useState(kod)
  const { data } = useQuery({
    queryKey: ["bux", "kartochka", kod, dan, gacha],
    queryFn: async () =>
      (
        await BuxgalteriyaService.buxKartochka({
          path: { kod },
          query: { dan, gacha },
        })
      ).data,
  })
  let saldo = num(data?.boshlangich ?? 0)
  return (
    <Karta
      title={
        <span className="flex flex-wrap items-center gap-2">
          Schyot kartochkasi
          <Input
            className="w-24 font-mono print:hidden"
            value={k}
            onChange={(e) =>
              setK(e.target.value.replace(/\D/g, "").slice(0, 4))
            }
            onKeyDown={(e) => e.key === "Enter" && onKod(k)}
          />
          <span>
            {data?.kod} {data?.nom}
          </span>
        </span>
      }
    >
      <p className="text-sm">
        Boshlang'ich saldo:{" "}
        <b className="num">{formatMoney(data?.boshlangich ?? 0)}</b>
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            {[
              "Sana",
              "Mazmuni",
              "Qarshi schyot",
              "Debet",
              "Kredit",
              "Saldo",
            ].map((h) => (
              <TableHead key={h}>{h}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {(data?.yozuvlar ?? []).map((y) => {
            const d = y.debet === kod
            saldo += d ? num(y.summa) : -num(y.summa)
            return (
              <TableRow key={y.id}>
                <TableCell className="whitespace-nowrap">
                  {formatDate(y.sana)}
                </TableCell>
                <TableCell className="text-sm">
                  {y.izoh}
                  {y.kontragent && (
                    <span className="text-muted-foreground">
                      {" "}
                      · {y.kontragent}
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <button
                    type="button"
                    className="font-mono text-primary underline"
                    onClick={() => onKod(d ? y.kredit : y.debet)}
                  >
                    {d ? y.kredit : y.debet}
                  </button>
                </TableCell>
                <TableCell className={r}>
                  {d ? formatMoney(y.summa) : ""}
                </TableCell>
                <TableCell className={r}>
                  {d ? "" : formatMoney(y.summa)}
                </TableCell>
                <TableCell className={cn(r, "font-semibold")}>
                  {formatMoney(saldo)}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <p className="text-sm">
        Yakuniy saldo: <b className="num">{formatMoney(data?.yakuniy ?? 0)}</b>{" "}
        (musbat — debet, manfiy — kredit)
      </p>
    </Karta>
  )
}

// ───────────────────────── provodkalar ─────────────────────────
function Provodkalar({ dan, gacha }: { dan: string; gacha: string }) {
  const qc = useQueryClient()
  const [faqatQolda, setFaqatQolda] = useState(false)
  const [xato, setXato] = useState("")
  const [f, setF] = useState({
    sana: bugun(),
    debet: "",
    kredit: "",
    summa: "",
    izoh: "",
  })
  const { data } = useQuery({
    queryKey: ["bux", "yozuvlar", dan, gacha, faqatQolda],
    queryFn: async () =>
      (
        await BuxgalteriyaService.buxYozuvlar({
          query: { dan, gacha, qolda: faqatQolda },
        })
      ).data,
  })
  const onError = (e: unknown) => setXato(extractErrorMessage(e as Error))
  const qosh = useMutation({
    mutationFn: async () =>
      BuxgalteriyaService.buxYozuvQosh({ body: { ...f, summa: f.summa } }),
    onSuccess: () => {
      setXato("")
      setF({ ...f, summa: "", izoh: "" })
      qc.invalidateQueries({ queryKey: ["bux"] })
    },
    onError,
  })
  const storno = useMutation({
    mutationFn: async (y: YozuvRead) =>
      BuxgalteriyaService.buxYozuvStorno({
        path: { yozuv_id: y.id },
        body: { sabab: "Xato provodka" },
      }),
    onSuccess: () => {
      setXato("")
      qc.invalidateQueries({ queryKey: ["bux"] })
    },
    onError,
  })
  return (
    <div className="flex flex-col gap-3">
      <Karta title="Qo'lda provodka (ish haqi, asosiy vosita va boshqa manbasiz operatsiyalar)">
        <div className="grid grid-cols-[9rem_6rem_6rem_10rem_1fr_auto] items-end gap-2">
          <Input
            type="date"
            value={f.sana}
            onChange={(e) => setF({ ...f, sana: e.target.value })}
          />
          <Input
            placeholder="Debet"
            className="font-mono"
            value={f.debet}
            onChange={(e) =>
              setF({
                ...f,
                debet: e.target.value.replace(/\D/g, "").slice(0, 4),
              })
            }
          />
          <Input
            placeholder="Kredit"
            className="font-mono"
            value={f.kredit}
            onChange={(e) =>
              setF({
                ...f,
                kredit: e.target.value.replace(/\D/g, "").slice(0, 4),
              })
            }
          />
          <Input
            placeholder="Summa"
            className="num text-right"
            value={f.summa}
            onChange={(e) =>
              setF({ ...f, summa: e.target.value.replace(/[^0-9.]/g, "") })
            }
          />
          <Input
            placeholder="Mazmuni"
            value={f.izoh}
            onChange={(e) => setF({ ...f, izoh: e.target.value })}
          />
          <LoadingButton loading={qosh.isPending} onClick={() => qosh.mutate()}>
            Yozish
          </LoadingButton>
        </div>
        <Xato text={xato} />
      </Karta>
      <Karta
        title={
          <span className="flex items-center justify-between">
            Provodkalar jurnali
            <label className="flex items-center gap-2 text-sm font-normal">
              <input
                type="checkbox"
                checked={faqatQolda}
                onChange={(e) => setFaqatQolda(e.target.checked)}
              />
              faqat qo'lda yozilganlar
            </label>
          </span>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              {["Sana", "Debet", "Kredit", "Summa", "Mazmuni", "Manba", ""].map(
                (h) => (
                  <TableHead key={h}>{h}</TableHead>
                ),
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data ?? []).map((y) => (
              <TableRow
                key={y.id}
                className={cn(y.storno_of_id && "text-muted-foreground")}
              >
                <TableCell className="whitespace-nowrap">
                  {formatDate(y.sana)}
                </TableCell>
                <TableCell className="font-mono">{y.debet}</TableCell>
                <TableCell className="font-mono">{y.kredit}</TableCell>
                <TableCell className={r}>{formatMoney(y.summa)}</TableCell>
                <TableCell className="text-sm">
                  {y.izoh}
                  {y.kontragent && (
                    <span className="text-muted-foreground">
                      {" "}
                      · {y.kontragent}
                    </span>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {y.guruh ?? "qo'lda"}
                </TableCell>
                <TableCell className="text-right">
                  {!y.guruh && !y.storno_of_id && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => storno.mutate(y)}
                    >
                      Storno
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Provodka yo'q</p>
        )}
      </Karta>
    </div>
  )
}

// ───────────────────────── nazorat ─────────────────────────
function Nazorat() {
  const { data, isFetching } = useQuery({
    queryKey: ["bux", "nazorat"],
    queryFn: async () => (await BuxgalteriyaService.buxNazorat()).data,
  })
  return (
    <Karta
      title="Nazorat: buxgalteriya modullardagi raqamlar bilan mosmi"
      className="max-w-5xl"
    >
      <p className="text-xs text-muted-foreground">
        Provodkalar kassa, ombor, buyurtma va soliq jurnallaridan avtomatik
        yasaladi; bu yerda ular manbaning o'zi bilan qayta solishtiriladi. Farq
        bo'lsa — qaysidir operatsiya buxgalteriyaga tushmagan.
        {isFetching && " Tekshirilmoqda…"}
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            {["Ko'rsatkich", "Buxgalteriya", "Manba", "Manba nomi", "Farq"].map(
              (h) => (
                <TableHead key={h}>{h}</TableHead>
              ),
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {(data ?? []).map((x) => {
            const ok = Math.abs(num(x.farq)) < 0.01
            // FIFO tannarx har harakatda tiyingacha yaxlitlanadi, partiya qiymati esa yaxlitlanmaydi
            const yaxlit = !ok && Math.abs(num(x.farq)) < 1
            return (
              <TableRow key={x.nom}>
                <TableCell>{x.nom}</TableCell>
                <TableCell className={r}>
                  {formatMoney(x.buxgalteriya)}
                </TableCell>
                <TableCell className={r}>{formatMoney(x.manba)}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {x.izoh}
                </TableCell>
                <TableCell
                  className={cn(
                    r,
                    ok
                      ? "text-emerald-700"
                      : yaxlit
                        ? "text-amber-700"
                        : "font-bold text-red-700",
                  )}
                >
                  {ok
                    ? "✓ 0"
                    : yaxlit
                      ? `≈0 (yaxlitlash ${num(x.farq).toFixed(2)})`
                      : formatMoney(x.farq)}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </Karta>
  )
}

// ───────────────────────── sozlamalar ─────────────────────────
function Sozlamalar() {
  const qc = useQueryClient()
  const [xato, setXato] = useState("")
  const { data: sch } = useQuery({
    queryKey: ["bux", "schyotlar"],
    queryFn: async () => (await BuxgalteriyaService.buxSchyotlar()).data,
  })
  const { data: qoida } = useQuery({
    queryKey: ["bux", "qoidalar"],
    queryFn: async () => (await BuxgalteriyaService.buxQoidalar()).data,
  })
  const [yangi, setYangi] = useState({ kalit: "", schyot: "" })
  const saqla = useMutation({
    mutationFn: async (v: { kalit: string; schyot: string }) =>
      BuxgalteriyaService.buxQoidaSaqla({ body: v }),
    onSuccess: () => {
      setXato("")
      setYangi({ kalit: "", schyot: "" })
      qc.invalidateQueries({ queryKey: ["bux"] })
    },
    onError: (e) => setXato(extractErrorMessage(e)),
  })
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <Karta title="Schyotlar rejasi (BHMS 21 asosida)">
        <p className="text-xs text-muted-foreground">
          Asosiy schyotlar; nomlari va ro'yxatni buxgalter tasdiqlaydi. A —
          aktiv, P — passiv, AP — aktiv-passiv.
        </p>
        {(sch ?? []).map((s) => (
          <div key={s.kod} className="flex gap-3 border-b py-1 text-sm">
            <b className="w-12 font-mono">{s.kod}</b>
            <span className="flex-1">{s.nom}</span>
            <span className="text-xs text-muted-foreground">{s.tur}</span>
          </div>
        ))}
      </Karta>
      <Karta title="Avtomatik provodka qoidalari">
        <p className="text-xs text-muted-foreground">
          Kalit → schyot. Masalan «xarajat:Ijara» → 9420 (ma'muriy) yoki 9410
          (sotish). O'zgartirilsa keyingi sinxron eski provodkalarni tuzatish
          provodkasi bilan qayta tasniflaydi — jurnal o'chirilmaydi.
        </p>
        <Xato text={xato} />
        {(qoida ?? []).map((q) => (
          <div
            key={q.kalit}
            className="flex items-center gap-2 border-b py-1 text-sm"
          >
            <span className="flex-1 font-mono text-xs">{q.kalit}</span>
            <Input
              key={`${q.kalit}${q.schyot}`}
              className="h-8 w-24 font-mono"
              defaultValue={q.schyot}
              onBlur={(e) =>
                e.target.value !== q.schyot &&
                saqla.mutate({ kalit: q.kalit, schyot: e.target.value })
              }
            />
          </div>
        ))}
        <div className="flex gap-2">
          <Input
            placeholder="xarajat:Modda nomi"
            value={yangi.kalit}
            onChange={(e) => setYangi({ ...yangi, kalit: e.target.value })}
          />
          <Input
            placeholder="Schyot"
            className="w-24 font-mono"
            value={yangi.schyot}
            onChange={(e) =>
              setYangi({
                ...yangi,
                schyot: e.target.value.replace(/\D/g, "").slice(0, 4),
              })
            }
          />
          <LoadingButton
            loading={saqla.isPending}
            onClick={() => saqla.mutate(yangi)}
          >
            Qo'shish
          </LoadingButton>
        </div>
      </Karta>
    </div>
  )
}
