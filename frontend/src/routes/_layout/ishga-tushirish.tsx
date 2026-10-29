// Ishga tushirish (EKO TZ §11, 7-bosqich): tizimni real ishlatishdan oldingi tayyorlik ro'yxati va ochilish
// qoldiqlari (tizimga o'tish kunidagi eski qarzlar). Ro'yxat bazadan hisoblanadi — qo'lda belgilanmaydi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { CheckCircle2, CircleAlert, TriangleAlert, Upload } from "lucide-react"
import { type ReactNode, useState } from "react"

import {
  ClientsService,
  MoliyaService,
  type OchilishIn,
  TayyorlikService,
} from "@/client"
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

export const Route = createFileRoute("/_layout/ishga-tushirish")({
  component: IshgaTushirish,
  beforeLoad: requireAccess(isMoliya),
  head: () => ({ meta: [{ title: "Ishga tushirish | MebeliX" }] }),
})

const bugun = () => new Date().toLocaleDateString("sv-SE")
const r = "num text-right whitespace-nowrap"

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

function IshgaTushirish() {
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-xl font-bold">ISHGA TUSHIRISH</h1>
      <div className="grid gap-3 xl:grid-cols-[1fr_1.2fr]">
        <Tayyorlik />
        <Ochilish />
      </div>
    </div>
  )
}

function Tayyorlik() {
  const { data, isFetching } = useQuery({
    queryKey: ["tayyorlik"],
    queryFn: async () => (await TayyorlikService.tayyorlik()).data,
  })
  const xato = (data ?? []).filter((t) => t.holat === "xato").length
  const ogoh = (data ?? []).filter((t) => t.holat === "ogoh").length
  return (
    <Karta
      title={
        <span className="flex items-center justify-between">
          Tayyorlik
          <span className="text-sm font-normal">
            {xato ? (
              <span className="text-red-700">{xato} ta to'siq</span>
            ) : (
              <span className="text-emerald-700">to'siq yo'q</span>
            )}
            {ogoh > 0 && (
              <span className="text-amber-700"> · {ogoh} ta e'tibor</span>
            )}
            {isFetching && " · tekshirilmoqda…"}
          </span>
        </span>
      }
    >
      <p className="text-xs text-muted-foreground">
        Bazadan hisoblanadi. Qizil — ishga tushirishdan oldin tuzatilsin; sariq
        — ishlaydi, lekin tekshirib tasdiqlang. ESF operatori, E-IMZO va fiskal
        chek keyin ulanadi.
      </p>
      {(data ?? []).map((t) => (
        <Link
          key={`${t.modul}-${t.nom}`}
          to={t.havola.split("?")[0]}
          search={Object.fromEntries(
            new URLSearchParams(t.havola.split("?")[1] ?? ""),
          )}
          className="flex items-start gap-3 rounded border px-3 py-2 text-sm hover:bg-muted"
        >
          {t.holat === "ok" ? (
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
          ) : t.holat === "ogoh" ? (
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" />
          ) : (
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-red-600" />
          )}
          <span>
            <span className="text-xs text-muted-foreground">{t.modul} · </span>
            <b>{t.nom}</b>
            <span className="block text-xs text-muted-foreground">
              {t.izoh}
            </span>
          </span>
        </Link>
      ))}
    </Karta>
  )
}

/** CSV: `tur;telefon yoki nom;summa;sana;izoh` — tur: mijoz | taminotchi; sana: YYYY-MM-DD yoki DD.MM.YYYY */
function csvOqi(matn: string): { qatorlar: OchilishIn[]; xato: string[] } {
  const qatorlar: OchilishIn[] = []
  const xato: string[] = []
  matn
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .forEach((l, i) => {
      const p = l.split(/[;\t]/).map((x) => x.trim())
      if (i === 0 && /tur/i.test(p[0])) return // sarlavha
      const [tur, kim, summa, sana, izoh] = p
      const t = tur?.toLowerCase().startsWith("t")
        ? "taminotchi"
        : tur?.toLowerCase().startsWith("m")
          ? "mijoz"
          : ""
      const s = Number((summa ?? "").replace(/\s/g, "").replace(",", "."))
      const d = /^\d{2}\.\d{2}\.\d{4}$/.test(sana ?? "")
        ? sana.split(".").reverse().join("-")
        : sana
      if (
        !t ||
        !kim ||
        !Number.isFinite(s) ||
        s === 0 ||
        !/^\d{4}-\d{2}-\d{2}$/.test(d ?? "")
      ) {
        xato.push(`${i + 1}-qator: «${l}»`)
        return
      }
      const telefon = /^[+\d\s()-]{9,}$/.test(kim) && t === "mijoz" ? kim : ""
      qatorlar.push({
        tur: t,
        telefon,
        nomi: telefon ? "" : kim,
        summa: String(s),
        sana: d,
        izoh: izoh ?? "",
      })
    })
  return { qatorlar, xato }
}

function Ochilish() {
  const qc = useQueryClient()
  const [xato, setXato] = useState("")
  const [ok, setOk] = useState("")
  const [tur, setTur] = useState<"mijoz" | "taminotchi">("mijoz")
  const [q, setQ] = useState("")
  const [mijoz, setMijoz] = useState<{ id: number; nom: string } | null>(null)
  const [nom, setNom] = useState("")
  const [summa, setSumma] = useState("")
  const [sana, setSana] = useState(bugun())
  const [izoh, setIzoh] = useState("")
  const [csv, setCsv] = useState("")
  const { data } = useQuery({
    queryKey: ["ochilish"],
    queryFn: async () => (await MoliyaService.moliyaOchilish()).data,
  })
  const { data: topilgan } = useQuery({
    queryKey: ["clients", "ochilish", q],
    enabled: tur === "mijoz" && q.length >= 2 && !mijoz,
    queryFn: async () =>
      (await ClientsService.readClients({ query: { search: q, limit: 6 } }))
        .data,
  })
  const yoz = useMutation({
    mutationFn: async (rows: OchilishIn[]) =>
      (await MoliyaService.moliyaOchilishQosh({ body: rows })).data,
    onSuccess: (n) => {
      setXato("")
      setOk(`${n.yozildi} qator yozildi`)
      setSumma("")
      setIzoh("")
      setMijoz(null)
      setQ("")
      setNom("")
      setCsv("")
      qc.invalidateQueries({ queryKey: ["ochilish"] })
      qc.invalidateQueries({ queryKey: ["tayyorlik"] })
    },
    onError: (e) => {
      setOk("")
      setXato(extractErrorMessage(e))
    },
  })
  const bitta = () =>
    yoz.mutate([
      {
        tur,
        client_id: tur === "mijoz" ? (mijoz?.id ?? null) : null,
        nomi: tur === "taminotchi" ? nom : "",
        summa: summa.replace(/\s/g, ""),
        sana,
        izoh,
      },
    ])
  const oqilgan = csv.trim() ? csvOqi(csv) : null
  const fayl = async (f: File | undefined) => f && setCsv(await f.text())
  return (
    <div className="flex flex-col gap-3">
      <Karta title="Ochilish qoldiqlari — tizimga o'tish kunidagi eski qarzlar">
        <p className="text-xs text-muted-foreground">
          Mijoz bizga qarz (manfiy — mijoz oldindan bergan avans) yoki biz
          ta'minotchiga qarz. Mijozning «Qarzni to'lash»i avval shu qarzni
          yopadi. Xato bo'lsa teskari ishorali qator yozing — o'chirilmaydi.
        </p>
        <div className="flex gap-2">
          {(["mijoz", "taminotchi"] as const).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={tur === t ? "default" : "outline"}
              onClick={() => setTur(t)}
            >
              {t === "mijoz" ? "Mijoz qarzi" : "Ta'minotchiga qarz"}
            </Button>
          ))}
        </div>
        <div className="grid grid-cols-[1fr_10rem_10rem] gap-2">
          {tur === "mijoz" ? (
            <div className="relative">
              <Input
                placeholder="Mijoz: ism yoki telefon"
                value={mijoz ? mijoz.nom : q}
                onChange={(e) => {
                  setMijoz(null)
                  setQ(e.target.value)
                }}
              />
              {(topilgan?.data ?? []).length > 0 && !mijoz && (
                <div className="absolute z-10 mt-1 w-full rounded border bg-background shadow">
                  {topilgan?.data.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className="block w-full px-3 py-1 text-left text-sm hover:bg-muted"
                      onClick={() => setMijoz({ id: c.id, nom: c.full_name })}
                    >
                      {c.full_name}{" "}
                      <span className="text-xs text-muted-foreground">
                        {c.phone}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <Input
              placeholder="Yetkazib beruvchi nomi"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
            />
          )}
          <Input
            placeholder="Summa"
            className="num text-right"
            value={summa}
            onChange={(e) =>
              setSumma(e.target.value.replace(/[^0-9.\- ]/g, ""))
            }
          />
          <Input
            type="date"
            value={sana}
            onChange={(e) => setSana(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Input
            placeholder="Izoh (masalan: 1C dan, akt sverki bo'yicha)"
            value={izoh}
            onChange={(e) => setIzoh(e.target.value)}
          />
          <LoadingButton loading={yoz.isPending} onClick={bitta}>
            Yozish
          </LoadingButton>
        </div>
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold">
            Ko'p qator: CSV / Excel dan
          </summary>
          <p className="mt-1 text-xs text-muted-foreground">
            Ustunlar: <code>tur;telefon yoki nom;summa;sana;izoh</code> (Excel
            dan nusxa — tab bilan ham bo'ladi). Bitta qator xato bo'lsa hech
            biri yozilmaydi.
          </p>
          <textarea
            className="mt-1 h-28 w-full rounded border bg-background p-2 font-mono text-xs"
            placeholder={
              "mijoz;+998901234567;1500000;01.10.2026;1C dan\ntaminotchi;Kronospan Tashkent;7000000;2026-10-01;"
            }
            value={csv}
            onChange={(e) => setCsv(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <label className="flex cursor-pointer items-center gap-1 rounded border px-2 py-1 text-xs">
              <Upload className="size-3" /> Fayl tanlash
              <input
                type="file"
                accept=".csv,.txt"
                className="hidden"
                onChange={(e) => fayl(e.target.files?.[0])}
              />
            </label>
            {oqilgan && (
              <span className="text-xs">
                {oqilgan.qatorlar.length} qator, jami{" "}
                {formatMoney(
                  oqilgan.qatorlar.reduce((a, x) => a + num(x.summa), 0),
                )}
                {oqilgan.xato.length > 0 && (
                  <span className="text-red-700">
                    {" "}
                    · o'qilmadi: {oqilgan.xato.join(", ")}
                  </span>
                )}
              </span>
            )}
            <LoadingButton
              size="sm"
              className="ml-auto"
              loading={yoz.isPending}
              disabled={
                !oqilgan ||
                oqilgan.qatorlar.length === 0 ||
                oqilgan.xato.length > 0
              }
              onClick={() => oqilgan && yoz.mutate(oqilgan.qatorlar)}
            >
              Hammasini yozish
            </LoadingButton>
          </div>
        </details>
        {xato && (
          <div className="flex items-start gap-2 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-900">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            {xato}
          </div>
        )}
        {ok && (
          <div className="rounded border border-emerald-300 bg-emerald-50 p-2 text-sm text-emerald-900">
            {ok}
          </div>
        )}
      </Karta>
      <Karta title={`Kiritilgan ochilish qoldiqlari · ${data?.length ?? 0}`}>
        <Table>
          <TableHeader>
            <TableRow>
              {["Sana", "Tur", "Kim", "Summa", "To'lanmagan", "Izoh"].map(
                (h) => (
                  <TableHead key={h}>{h}</TableHead>
                ),
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data ?? []).map((o) => (
              <TableRow key={o.id}>
                <TableCell>{formatDate(o.sana)}</TableCell>
                <TableCell>
                  {o.tur === "mijoz" ? "mijoz" : "ta'minotchi"}
                </TableCell>
                <TableCell>{o.kontragent}</TableCell>
                <TableCell
                  className={cn(r, num(o.summa) < 0 && "text-red-700")}
                >
                  {formatMoney(o.summa)}
                </TableCell>
                <TableCell className={r}>
                  {o.qolgan != null ? formatMoney(o.qolgan) : "—"}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {o.izoh}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Hali kiritilmagan</p>
        )}
      </Karta>
    </div>
  )
}
