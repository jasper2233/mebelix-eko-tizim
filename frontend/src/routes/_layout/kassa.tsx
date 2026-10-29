// Kassa — kassir ekrani (EKO TZ §7, o'rta daraja; tuzilishi `Kassa.dc.html` prototipidan): tepada smena va naqd
// qoldiq, chapda to'lov navbati (qidiruv), o'rtada kirim/chiqim, o'ngda smena orderlari. Pul faqat order bilan;
// xato order bu yerda emas — Moliyada storno (direktor, ikki kalit).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { CheckCircle2, Lock, Search, TriangleAlert, Unlock } from "lucide-react"
import { useState } from "react"

import {
  type AmalNatija,
  KassaService,
  type NavbatRow,
  type SmenaHolat,
} from "@/client"
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
import { requireAccess } from "@/lib/guards"
import { formatDateTime, formatMoney, isKassa } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { num, parseNum } from "@/lib/warehouse"
import { extractErrorMessage } from "@/utils"

export const Route = createFileRoute("/_layout/kassa")({
  component: KassaPage,
  beforeLoad: requireAccess(isKassa),
  head: () => ({ meta: [{ title: "Kassa | MebeliX" }] }),
})

const KUPYURA = [200000, 100000, 50000, 20000, 10000, 5000, 2000, 1000]
const KIRIM = [
  { v: "avans", l: "Avans" },
  { v: "tolov", l: "Buyurtma to'lovi" },
  { v: "qarz", l: "Qarzni to'lash" },
  { v: "boshqa", l: "Boshqa kirim" },
] as const
const CHIQIM = [
  { v: "xarajat", l: "Xarajat" },
  { v: "taminotchi", l: "Ta'minotchiga" },
  { v: "qaytarish", l: "Mijozga qaytarish" },
  { v: "inkassatsiya", l: "Inkassatsiya" },
  { v: "boshqa", l: "Boshqa chiqim" },
] as const
const USUL = [
  { v: "naqd", l: "Naqd" },
  { v: "karta", l: "Karta" },
  { v: "bank", l: "Bank" },
  { v: "aralash", l: "Naqd + karta" },
] as const
const MAQSAD_NOM: Record<string, string> = {
  avans: "Avans",
  tolov: "To'lov",
  qarz: "Qarz",
  boshqa: "Boshqa",
  xarajat: "Xarajat",
  taminotchi: "Ta'minotchi",
  qaytarish: "Qaytarish",
  inkassatsiya: "Inkassatsiya",
  farq: "Smena farqi",
  otkazma: "O'tkazma",
  komissiya: "Komissiya",
  sotuv: "Sotuv",
}
const HOLAT_KEY = ["kassa", "holat"]

function KassaPage() {
  const { data: holat, isLoading } = useQuery({
    queryKey: HOLAT_KEY,
    queryFn: async () => (await KassaService.kassaHolat()).data,
    refetchInterval: 30_000,
  })
  const [smenaOyna, setSmenaOyna] = useState<"och" | "yop" | null>(null)
  const [tanlangan, setTanlangan] = useState<NavbatRow | null>(null)
  if (isLoading || !holat) return <Skeleton className="h-96" />
  const naqd = holat.hisoblar.find((h) => h.kod === "naqd")
  return (
    <div className="flex flex-col gap-3">
      <header
        className={cn(
          cardSurface,
          "flex flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3",
        )}
      >
        <h1 className="text-xl font-bold">KASSA</h1>
        <Stat
          l="Smena"
          v={holat.smena ? holat.smena.no : "yopiq"}
          danger={!holat.smena}
        />
        <Stat l="Kassir" v={holat.smena?.ochgan ?? "—"} />
        <Stat l="Naqd qoldiq" v={formatMoney(naqd?.qoldiq)} />
        {holat.smena && (
          <>
            <Stat l="Smenada kirim" v={formatMoney(holat.kirim)} />
            <Stat l="Smenada chiqim" v={formatMoney(holat.chiqim)} />
            <Stat l="Karta" v={formatMoney(holat.karta)} />
          </>
        )}
        <div className="ml-auto">
          {holat.smena ? (
            <Button variant="outline" onClick={() => setSmenaOyna("yop")}>
              <Lock /> Smenani yopish
            </Button>
          ) : (
            <Button onClick={() => setSmenaOyna("och")}>
              <Unlock /> Smenani ochish
            </Button>
          )}
        </div>
      </header>
      {holat.smena && num(holat.ochilish_farq) !== 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
          Smena ochilishida sanalgan naqd kitobdan{" "}
          {formatMoney(holat.ochilish_farq)} farq qildi — yopishda hisobga
          olinadi.
        </div>
      )}
      <div className="grid gap-3 xl:grid-cols-[20rem_1fr_24rem]">
        <Navbat tanlangan={tanlangan} onTanla={setTanlangan} />
        <Amal
          key={holat.smena?.id ?? "yopiq"}
          tanlangan={tanlangan}
          onTanla={setTanlangan}
        />
        <SmenaOrderlari smenaId={holat.smena?.id ?? null} />
      </div>
      <SmenaDialog
        rejim={smenaOyna}
        holat={holat}
        onClose={() => setSmenaOyna(null)}
      />
    </div>
  )
}

function Stat({ l, v, danger }: { l: string; v: string; danger?: boolean }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground uppercase">{l}</div>
      <div className={cn("num font-semibold", danger && "text-red-700")}>
        {v}
      </div>
    </div>
  )
}

function Navbat({
  tanlangan,
  onTanla,
}: {
  tanlangan: NavbatRow | null
  onTanla: (r: NavbatRow) => void
}) {
  const [q, setQ] = useState("")
  const { data } = useQuery({
    queryKey: ["kassa", "navbat", q],
    queryFn: async () =>
      (await KassaService.kassaNavbat({ query: { q } })).data,
  })
  return (
    <section className={cn(cardSurface, "flex flex-col gap-2 p-3")}>
      <div className="relative">
        <Search className="absolute top-2.5 left-2 size-4 text-muted-foreground" />
        <Input
          className="pl-8"
          placeholder="Buyurtma №, mijoz, telefon"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <div className="text-xs text-muted-foreground uppercase">
        To'lov kutmoqda
      </div>
      <div className="flex max-h-[60vh] flex-col gap-1 overflow-y-auto">
        {(data ?? []).map((r) => (
          <button
            key={r.order_id}
            type="button"
            onClick={() => onTanla(r)}
            className={cn(
              "rounded-md border px-3 py-2 text-left text-sm hover:bg-muted",
              tanlangan?.order_id === r.order_id &&
                "border-primary bg-primary/5",
            )}
          >
            <div className="flex justify-between gap-2">
              <b>{r.mijoz}</b>
              <span className="num font-semibold">{formatMoney(r.qolgan)}</span>
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{r.order_number}</span>
              {r.chegaraga_kerak != null && num(r.chegaraga_kerak) > 0 && (
                <span className="text-amber-700">
                  avans: {formatMoney(r.chegaraga_kerak)}
                </span>
              )}
            </div>
          </button>
        ))}
        {data?.length === 0 && (
          <p className="p-2 text-sm text-muted-foreground">Navbat bo'sh</p>
        )}
      </div>
    </section>
  )
}

function Amal({
  tanlangan,
  onTanla,
}: {
  tanlangan: NavbatRow | null
  onTanla: (r: NavbatRow | null) => void
}) {
  const queryClient = useQueryClient()
  const [tur, setTur] = useState<"kirim" | "chiqim">("kirim")
  const [maqsad, setMaqsad] = useState<string>("tolov")
  const [usul, setUsul] = useState<string>("naqd")
  const [summa, setSumma] = useState("")
  const [karta, setKarta] = useState("")
  const [berdi, setBerdi] = useState("")
  const [kim, setKim] = useState("")
  const [turkum, setTurkum] = useState("")
  const [izoh, setIzoh] = useState("")
  const [natija, setNatija] = useState<AmalNatija | null>(null)
  const [xato, setXato] = useState("")
  const { data: turkumlar } = useQuery({
    queryKey: ["kassa", "turkumlar"],
    queryFn: async () => (await KassaService.kassaTurkumlar()).data,
  })
  const buyurtmaga =
    tur === "kirim"
      ? maqsad === "avans" || maqsad === "tolov"
      : maqsad === "qaytarish"
  const s = parseNum(summa) ?? 0
  const k = usul === "aralash" ? (parseNum(karta) ?? 0) : 0
  const naqdQism = usul === "naqd" ? s : usul === "aralash" ? s : 0
  const b = parseNum(berdi)
  const qaytim = b != null && naqdQism > 0 ? b - naqdQism : null

  const reset = () => {
    setSumma("")
    setKarta("")
    setBerdi("")
    setKim("")
    setIzoh("")
  }
  const bajar = useMutation({
    mutationFn: async () => {
      if (tur === "kirim") {
        const tolovlar =
          usul === "aralash"
            ? [
                { hisob: "naqd" as const, summa: String(s) },
                { hisob: "karta" as const, summa: String(k) },
              ]
            : [{ hisob: usul as "naqd" | "karta" | "bank", summa: String(s) }]
        return (
          await KassaService.kassaKirim({
            body: {
              maqsad: maqsad as "avans",
              tolovlar,
              order_id: buyurtmaga ? (tanlangan?.order_id ?? null) : null,
              client_id:
                maqsad === "qarz" ? (tanlangan?.client_id ?? null) : null,
              kontragent: kim,
              izoh,
              mijoz_berdi: b != null && naqdQism > 0 ? String(b) : null,
            },
          })
        ).data
      }
      return (
        await KassaService.kassaChiqim({
          body: {
            maqsad: maqsad as "xarajat",
            hisob: (usul === "aralash" ? "naqd" : usul) as "naqd",
            summa: String(s),
            kontragent: kim,
            turkum,
            izoh,
            order_id: buyurtmaga ? (tanlangan?.order_id ?? null) : null,
          },
        })
      ).data
    },
    onSuccess: (r) => {
      setNatija(r)
      setXato("")
      reset()
      queryClient.invalidateQueries({ queryKey: ["kassa"] })
      onTanla(null)
    },
    onError: (e) => {
      setXato(extractErrorMessage(e))
      setNatija(null)
    },
  })

  const turlar = tur === "kirim" ? KIRIM : CHIQIM
  return (
    <section className={cn(cardSurface, "flex flex-col gap-3 p-4")}>
      <div className="flex gap-2">
        {(["kirim", "chiqim"] as const).map((t) => (
          <Button
            key={t}
            variant={tur === t ? "default" : "outline"}
            onClick={() => {
              setTur(t)
              setMaqsad(t === "kirim" ? "tolov" : "xarajat")
              setNatija(null)
              setXato("")
            }}
          >
            {t === "kirim" ? "Kirim (PKO)" : "Chiqim (RKO)"}
          </Button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {turlar.map((m) => (
          <button
            key={m.v}
            type="button"
            onClick={() => setMaqsad(m.v)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm",
              maqsad === m.v &&
                "border-primary bg-primary text-primary-foreground",
            )}
          >
            {m.l}
          </button>
        ))}
      </div>
      {(buyurtmaga || maqsad === "qarz") && (
        <div className="rounded-md border bg-muted/30 p-3 text-sm">
          {tanlangan ? (
            <div className="flex flex-wrap gap-x-6 gap-y-1">
              <b>{tanlangan.mijoz}</b>
              <span>{tanlangan.order_number}</span>
              <span>
                Summa: <b className="num">{formatMoney(tanlangan.summa)}</b>
              </span>
              <span>
                To'langan:{" "}
                <b className="num">{formatMoney(tanlangan.tolangan)}</b>
              </span>
              <span>
                Qolgan: <b className="num">{formatMoney(tanlangan.qolgan)}</b>
              </span>
            </div>
          ) : (
            <span className="text-muted-foreground">
              Chapdagi navbatdan buyurtmani tanlang
            </span>
          )}
        </div>
      )}
      {!buyurtmaga && maqsad !== "qarz" && (
        <Input
          placeholder={tur === "kirim" ? "Kimdan" : "Kimga"}
          value={kim}
          onChange={(e) => setKim(e.target.value)}
        />
      )}
      {tur === "chiqim" && maqsad === "xarajat" && (
        <div className="flex flex-wrap gap-2">
          {(turkumlar ?? []).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTurkum(t)}
              className={cn(
                "rounded border px-2 py-1 text-xs",
                turkum === t && "border-primary bg-primary/10 font-semibold",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {(tur === "kirim" ? USUL : USUL.slice(0, 3)).map((u) => (
          <Button
            key={u.v}
            size="sm"
            variant={usul === u.v ? "default" : "outline"}
            onClick={() => setUsul(u.v)}
          >
            {u.l}
          </Button>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="text-xs text-muted-foreground uppercase">
          {usul === "aralash" ? "Naqd qismi" : "Summa, so'm"}
          <Input
            className="num mt-1 h-12 text-right text-xl font-bold"
            inputMode="decimal"
            value={summa}
            onChange={(e) => setSumma(e.target.value.replace(/[^0-9.,]/g, ""))}
          />
        </div>
        {usul === "aralash" && (
          <div className="text-xs text-muted-foreground uppercase">
            Karta qismi
            <Input
              className="num mt-1 h-12 text-right text-xl font-bold"
              inputMode="decimal"
              value={karta}
              onChange={(e) =>
                setKarta(e.target.value.replace(/[^0-9.,]/g, ""))
              }
            />
          </div>
        )}
        {tur === "kirim" && naqdQism > 0 && (
          <div className="text-xs text-muted-foreground uppercase">
            Mijoz berdi (naqd)
            <Input
              className="num mt-1 h-12 text-right text-xl"
              inputMode="decimal"
              value={berdi}
              onChange={(e) =>
                setBerdi(e.target.value.replace(/[^0-9.,]/g, ""))
              }
            />
          </div>
        )}
      </div>
      {buyurtmaga && tanlangan && tur === "kirim" && (
        <div className="flex flex-wrap gap-2 text-sm">
          {tanlangan.chegaraga_kerak != null &&
            num(tanlangan.chegaraga_kerak) > 0 && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSumma(String(num(tanlangan.chegaraga_kerak)))}
              >
                Eng kam avans · {formatMoney(tanlangan.chegaraga_kerak)}
              </Button>
            )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => setSumma(String(num(tanlangan.qolgan)))}
          >
            Hammasi · {formatMoney(tanlangan.qolgan)}
          </Button>
        </div>
      )}
      {qaytim != null && (
        <div
          className={cn(
            "text-lg font-bold",
            qaytim < 0 ? "text-red-700" : "text-emerald-700",
          )}
        >
          Qaytim: {formatMoney(qaytim)}
        </div>
      )}
      <Input
        placeholder="Izoh (ixtiyoriy)"
        value={izoh}
        onChange={(e) => setIzoh(e.target.value)}
      />
      <LoadingButton
        className="h-14 text-lg"
        loading={bajar.isPending}
        disabled={s <= 0}
        onClick={() => bajar.mutate()}
      >
        {tur === "kirim" ? "Qabul qilish" : "Berish"} · {formatMoney(s + k)}
      </LoadingButton>
      {xato && (
        <div className="flex items-start gap-2 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-900">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          {xato}
        </div>
      )}
      {natija && (
        <div className="rounded border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">
          <div className="flex items-center gap-2 font-semibold">
            <CheckCircle2 className="size-4" />
            {natija.xabar}
            {natija.qaytim != null && num(natija.qaytim) > 0 && (
              <span>· qaytim {formatMoney(natija.qaytim)}</span>
            )}
          </div>
          {natija.rezerv?.map((r) => (
            <div key={r} className="mt-1 font-semibold text-emerald-800">
              {r}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function SmenaOrderlari({ smenaId }: { smenaId: number | null }) {
  const { data } = useQuery({
    queryKey: ["kassa", "orderlar", smenaId],
    queryFn: async () =>
      (
        await KassaService.kassaOrderlar({
          query: { smena_id: smenaId ?? undefined, limit: 100 },
        })
      ).data,
  })
  return (
    <section className={cn(cardSurface, "flex flex-col gap-2 p-3")}>
      <div className="flex items-baseline justify-between">
        <h2 className="font-semibold">
          {smenaId ? "Smena orderlari" : "Oxirgi orderlar"}
        </h2>
        <span className="text-xs text-muted-foreground">
          xato order Moliyada storno qilinadi
        </span>
      </div>
      <div className="flex max-h-[65vh] flex-col overflow-y-auto">
        {(data ?? []).map((o) => (
          <div
            key={o.id}
            className={cn(
              "flex items-start justify-between gap-2 border-b py-2 text-sm",
              (o.storno_no || o.storno_of_id) && "text-muted-foreground",
            )}
          >
            <div>
              <div className="font-mono text-xs">{o.no}</div>
              <div>
                {o.kontragent || MAQSAD_NOM[o.maqsad] || o.maqsad}
                {o.order_number && (
                  <span className="text-muted-foreground">
                    {" "}
                    · {o.order_number}
                  </span>
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                {MAQSAD_NOM[o.maqsad] ?? o.maqsad} · {o.hisob} ·{" "}
                {formatDateTime(o.created_at)}
                {o.storno_no && (
                  <span className="text-red-700"> · storno {o.storno_no}</span>
                )}
              </div>
            </div>
            <div
              className={cn(
                "num font-semibold whitespace-nowrap",
                o.tur === "kirim" ? "text-emerald-700" : "text-red-700",
              )}
            >
              {o.tur === "kirim" ? "+" : "−"}
              {formatMoney(Math.abs(num(o.summa)))}
            </div>
          </div>
        ))}
        {data?.length === 0 && (
          <p className="p-2 text-sm text-muted-foreground">Hali order yo'q</p>
        )}
      </div>
    </section>
  )
}

function SmenaDialog({
  rejim,
  holat,
  onClose,
}: {
  rejim: "och" | "yop" | null
  holat: SmenaHolat
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [soni, setSoni] = useState<Record<string, string>>({})
  const [terminal, setTerminal] = useState("")
  const [xato, setXato] = useState("")
  const jami = KUPYURA.reduce((a, k) => a + k * (Number(soni[k]) || 0), 0)
  const kitob =
    rejim === "yop"
      ? num(holat.kutilgan)
      : num(holat.hisoblar.find((h) => h.kod === "naqd")?.qoldiq)
  const farq = jami - kitob
  const saqla = useMutation({
    mutationFn: async () => {
      const kupyura = Object.fromEntries(
        KUPYURA.filter((k) => Number(soni[k]) > 0).map((k) => [
          String(k),
          Number(soni[k]),
        ]),
      )
      return rejim === "och"
        ? (await KassaService.kassaSmenaOch({ body: { kupyura } })).data
        : (
            await KassaService.kassaSmenaYop({
              body: {
                kupyura,
                terminal_z:
                  parseNum(terminal) != null
                    ? String(parseNum(terminal))
                    : null,
              },
            })
          ).data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["kassa"] })
      setSoni({})
      setTerminal("")
      setXato("")
      onClose()
    },
    onError: (e) => setXato(extractErrorMessage(e)),
  })
  return (
    <Dialog open={rejim != null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {rejim === "och"
              ? "Smenani ochish"
              : `Smenani yopish · ${holat.smena?.no ?? ""}`}
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Kassadagi naqd pulni kupyura bo'yicha sanang — dastur o'zi qo'shadi.
          {rejim === "yop" &&
            " Farq bo'lsa alohida order bo'lib yoziladi va Z-hisobotda ko'rinadi."}
        </p>
        <div className="grid grid-cols-2 gap-2">
          {KUPYURA.map((k) => (
            <div key={k} className="flex items-center gap-2 text-sm">
              <span className="num w-20 text-right">
                {k.toLocaleString("ru-RU")}
              </span>
              ×
              <Input
                className="num h-8 w-20 text-right"
                inputMode="numeric"
                value={soni[k] ?? ""}
                onChange={(e) =>
                  setSoni({
                    ...soni,
                    [k]: e.target.value.replace(/[^0-9]/g, ""),
                  })
                }
              />
            </div>
          ))}
        </div>
        <div className="flex flex-wrap justify-between gap-2 rounded bg-muted/40 p-3 text-sm">
          <span>
            Jami sanaldi: <b className="num">{formatMoney(jami)}</b>
          </span>
          <span>
            {rejim === "yop" ? "Kutilgan" : "Kitobda"}:{" "}
            <b className="num">{formatMoney(kitob)}</b>
          </span>
          <span className={cn(Math.abs(farq) >= 1 && "font-bold text-red-700")}>
            Farq: <b className="num">{formatMoney(farq)}</b>
          </span>
        </div>
        {rejim === "yop" && (
          <div className="flex items-center gap-2 text-sm">
            Karta terminali Z-hisoboti
            <Input
              className="num h-8 w-40 text-right"
              inputMode="decimal"
              value={terminal}
              onChange={(e) =>
                setTerminal(e.target.value.replace(/[^0-9.,]/g, ""))
              }
            />
            <span className="text-xs text-muted-foreground">
              tizimda: {formatMoney(holat.karta)}
            </span>
          </div>
        )}
        {xato && <p className="text-sm text-red-700">{xato}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Bekor
          </Button>
          <LoadingButton
            loading={saqla.isPending}
            onClick={() => saqla.mutate()}
          >
            {rejim === "och" ? "Smenani ochish" : "Yopish va Z-hisobot"}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
