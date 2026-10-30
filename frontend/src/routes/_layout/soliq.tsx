// Soliq (EKO TZ §9, 3-daraja): ESF (chiquvchi va kiruvchi), oylik soliq va QQS kitobi, sozlamalar. Rejim va
// stavkalar obunachining o'zi sozlaydi (QQS to'lovchi yoki aylanmadan soliq, sanadan boshlab tarix bilan).
// ESF operatori hozir LOKAL SINOV operatori — haqiqiy soliq tizimiga hech narsa yuborilmaydi (sahifada yozilgan).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Download, Printer, TriangleAlert } from "lucide-react"
import { type ReactNode, useState } from "react"

import {
  CatalogService,
  ClientsService,
  type EsfRead,
  type MijozIo,
  type Nomzod,
  SoliqService,
} from "@/client"
import { client } from "@/client/client.gen"
import { useTasdiq } from "@/components/Common/useTasdiq"
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { SOLIQ_BOLIMLAR } from "@/lib/bolimlar"
import { requireAccess } from "@/lib/guards"
import { formatDate, formatMoney, isMoliya } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { num } from "@/lib/warehouse"
import { extractErrorMessage } from "@/utils"

const BOLIMLAR = SOLIQ_BOLIMLAR
type Bolim = (typeof BOLIMLAR)[number]["v"]

export const Route = createFileRoute("/_layout/soliq")({
  component: SoliqPage,
  beforeLoad: requireAccess(isMoliya),
  validateSearch: (s: Record<string, unknown>): { b: Bolim } => ({
    b: BOLIMLAR.some((x) => x.v === s.b) ? (s.b as Bolim) : "esf",
  }),
  head: () => ({ meta: [{ title: "Soliq | MebeliX" }] }),
})

const HOLAT: Record<string, { l: string; c: string }> = {
  qoralama: { l: "qoralama", c: "bg-muted text-foreground" },
  navbatda: { l: "navbatda", c: "bg-amber-100 text-amber-900" },
  yuborildi: { l: "yuborildi", c: "bg-sky-100 text-sky-900" },
  qabul_qilindi: { l: "qabul qilindi", c: "bg-emerald-100 text-emerald-900" },
  rad_etildi: { l: "rad etildi", c: "bg-red-100 text-red-900" },
  kutilmoqda: { l: "javob kutmoqda", c: "bg-amber-100 text-amber-900" },
  xato: { l: "operator xatosi", c: "bg-red-100 text-red-900" },
  bekor: { l: "bekor", c: "bg-muted text-muted-foreground line-through" },
}
const bugun = () => new Date().toLocaleDateString("sv-SE")

function SoliqPage() {
  const { b } = Route.useSearch()
  const navigate = useNavigate({ from: "/soliq" })
  const { data: k } = useQuery({
    queryKey: ["soliq", "korxona"],
    queryFn: async () => (await SoliqService.soliqKorxona()).data,
  })
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <h1 className="mr-4 text-xl font-bold">SOLIQ</h1>
        {BOLIMLAR.map((x) => (
          <button
            key={x.v}
            type="button"
            onClick={() => navigate({ search: { b: x.v } })}
            className={cn(
              "rounded-full border px-3 py-1 text-sm",
              b === x.v && "border-primary bg-primary text-primary-foreground",
            )}
          >
            {x.l}
          </button>
        ))}
        {k?.esf_operator === "sinov" && (
          <span className="ml-auto rounded bg-amber-100 px-2 py-1 text-xs text-amber-900">
            ESF operatori: lokal SINOV — soliq tizimiga hech narsa yuborilmaydi
          </span>
        )}
      </div>
      {b === "esf" && <Chiquvchi />}
      {b === "kiruvchi" && <Kiruvchi />}
      {b === "hisobot" && <Hisobot />}
      {b === "sozlamalar" && <Sozlamalar />}
    </div>
  )
}

// ───────────────────────── umumiy ─────────────────────────
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

function Holat({ h }: { h: string }) {
  const x = HOLAT[h] ?? { l: h, c: "bg-muted" }
  return (
    <span className={cn("rounded px-2 py-0.5 text-xs whitespace-nowrap", x.c)}>
      {x.l}
    </span>
  )
}

const num_r = "num text-right whitespace-nowrap"

function Maydon({
  l,
  v,
  on,
  className,
  placeholder,
}: {
  l: string
  v: string
  on: (v: string) => void
  className?: string
  placeholder?: string
}) {
  return (
    <div className={cn("text-xs text-muted-foreground uppercase", className)}>
      {l}
      <Input
        className="mt-1 normal-case"
        value={v}
        placeholder={placeholder}
        onChange={(e) => on(e.target.value)}
      />
    </div>
  )
}

/** Mijoz soliq rekvizitlari (ESF dan oldin): yuridik — STIR, jismoniy — JShShIR */
function MijozDialog({
  clientId,
  nomi,
  onClose,
  onSaved,
}: {
  clientId: number | null
  nomi: string
  onClose: () => void
  onSaved: () => void
}) {
  const [m, setM] = useState<MijozIo | null>(null)
  const [xato, setXato] = useState("")
  useQuery({
    queryKey: ["soliq", "mijoz", clientId],
    enabled: clientId != null,
    queryFn: async () => {
      const d = (
        await SoliqService.soliqMijoz({ path: { client_id: clientId ?? 0 } })
      ).data
      setM({ ...d, nomi: d.nomi || nomi, yuridik: true })
      return d
    },
  })
  const saqla = useMutation({
    mutationFn: async () =>
      m &&
      SoliqService.soliqMijozSaqla({
        path: { client_id: clientId ?? 0 },
        body: m,
      }),
    onSuccess: () => {
      setXato("")
      onSaved()
    },
    onError: (e) => setXato(extractErrorMessage(e)),
  })
  const set = (k: keyof MijozIo) => (v: string) =>
    m && setM({ ...m, [k]: v.replace(k === "nomi" ? /$^/ : /\D/g, "") })
  return (
    <Dialog open={clientId != null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Mijoz rekvizitlari · {nomi}</DialogTitle>
        </DialogHeader>
        {m && (
          <div className="grid grid-cols-2 gap-2">
            <Maydon
              l="Yuridik nomi"
              v={m.nomi ?? ""}
              on={(v) => setM({ ...m, nomi: v })}
              className="col-span-2"
            />
            <Maydon l="STIR (9)" v={m.stir ?? ""} on={set("stir")} />
            <Maydon l="QQS kodi" v={m.qqs_kod ?? ""} on={set("qqs_kod")} />
            <Maydon
              l="Bank"
              v={m.bank ?? ""}
              on={(v) => setM({ ...m, bank: v })}
              className="col-span-2"
            />
            <Maydon l="MFO (5)" v={m.mfo ?? ""} on={set("mfo")} />
            <Maydon
              l="Hisob raqami (20)"
              v={m.hisob_raqam ?? ""}
              on={set("hisob_raqam")}
            />
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          ESF faqat yuridik mijozga yoziladi; jismoniy shaxsga — fiskal chek.
        </p>
        <Xato text={xato} />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Bekor
          </Button>
          <LoadingButton
            loading={saqla.isPending}
            onClick={() => saqla.mutate()}
          >
            Saqlash
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** ESF ko'rinishi (hisob-faktura shakli, chop etiladi) */
function EsfVaraq({ e }: { e: EsfRead }) {
  const r = e.rekvizit as Record<string, Record<string, string>>
  const tomon = (t: string, x?: Record<string, string>) => (
    <div className="text-xs">
      <div className="font-semibold uppercase">{t}</div>
      <div className="font-semibold">{x?.nomi}</div>
      <div>STIR: {x?.stir || x?.jshshir || "—"}</div>
      {x?.qqs_kod && <div>QQS kodi: {x.qqs_kod}</div>}
      {x?.bank && (
        <div>
          {x.bank}, MFO {x.mfo}, h/r {x.hisob_raqam}
        </div>
      )}
      {x?.manzil && <div>{x.manzil}</div>}
    </div>
  )
  return (
    <div className="bg-white p-6 text-sm text-black">
      <h2 className="text-center text-base font-bold">
        HISOB-FAKTURA № {e.raqam || e.no} · {formatDate(e.sana)}
      </h2>
      <p className="text-center text-xs">
        {e.rejim === "qqs"
          ? "QQS bilan"
          : "QQSsiz (aylanmadan soliq to'lovchi)"}
      </p>
      <div className="mt-4 grid grid-cols-2 gap-4">
        {tomon("Sotuvchi", r.sotuvchi)}
        {tomon("Xaridor", r.xaridor)}
      </div>
      <Table className="mt-3 text-xs">
        <TableHeader>
          <TableRow>
            {[
              "№",
              "Nomi",
              "MXIK",
              "Birlik",
              "Miqdor",
              "Narx",
              "Summa",
              "QQS %",
              "QQS",
              "Jami",
            ].map((h) => (
              <TableHead key={h}>{h}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {e.qatorlar.map((q, i) => (
            <TableRow key={`${q.mxik}-${i}`}>
              <TableCell>{i + 1}</TableCell>
              <TableCell>{String(q.nom)}</TableCell>
              <TableCell className="font-mono">{String(q.mxik)}</TableCell>
              <TableCell>{String(q.birlik ?? "")}</TableCell>
              <TableCell className={num_r}>{String(q.miqdor)}</TableCell>
              <TableCell className={num_r}>
                {formatMoney(String(q.narx))}
              </TableCell>
              <TableCell className={num_r}>
                {formatMoney(String(q.summa))}
              </TableCell>
              <TableCell className={num_r}>
                {q.ozod
                  ? "ozod"
                  : q.qqs_foiz == null
                    ? "QQSsiz"
                    : `${num(String(q.qqs_foiz))} %`}
              </TableCell>
              <TableCell className={num_r}>
                {formatMoney(String(q.qqs))}
              </TableCell>
              <TableCell className={num_r}>
                {formatMoney(String(q.jami))}
              </TableCell>
            </TableRow>
          ))}
          <TableRow className="font-bold">
            <TableCell colSpan={6}>Jami</TableCell>
            <TableCell className={num_r}>{formatMoney(e.summa)}</TableCell>
            <TableCell />
            <TableCell className={num_r}>{formatMoney(e.qqs)}</TableCell>
            <TableCell className={num_r}>{formatMoney(e.jami)}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <div className="mt-8 grid grid-cols-2 gap-8 text-xs">
        <div>Rahbar: {r.sotuvchi?.direktor || "______________"}</div>
        <div>Bosh buxgalter: {r.sotuvchi?.buxgalter || "______________"}</div>
      </div>
    </div>
  )
}

function EsfDialog({ e, onClose }: { e: EsfRead | null; onClose: () => void }) {
  return (
    <Dialog open={e != null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-auto sm:max-w-6xl">
        <DialogHeader className="print:hidden">
          <DialogTitle>
            {e?.no} {e && <Holat h={e.holat} />}
          </DialogTitle>
        </DialogHeader>
        {e && <EsfVaraq e={e} />}
        {e?.xato && <Xato text={e.xato} />}
        <DialogFooter className="print:hidden">
          <Button variant="outline" onClick={() => window.print()}>
            <Printer /> Chop etish
          </Button>
          <Button onClick={onClose}>Yopish</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ───────────────────────── chiquvchi ESF ─────────────────────────
function Chiquvchi() {
  const qc = useQueryClient()
  const [tasdiqOyna, sora] = useTasdiq()
  const [xato, setXato] = useState("")
  const [korish, setKorish] = useState<EsfRead | null>(null)
  const [rekvizit, setRekvizit] = useState<{
    id: number
    nomi: string
    keyin?: Nomzod
  } | null>(null)
  const [hujjat, setHujjat] = useState<Nomzod | null>(null)
  const { data: nomzod } = useQuery({
    queryKey: ["soliq", "nomzodlar"],
    queryFn: async () => (await SoliqService.soliqNomzodlar()).data,
  })
  const { data: esflar } = useQuery({
    queryKey: ["soliq", "esf", "chiquvchi"],
    queryFn: async () =>
      (await SoliqService.soliqEsflar({ query: { tur: "chiquvchi" } })).data,
    refetchInterval: 15_000,
  })
  const yangila = () => qc.invalidateQueries({ queryKey: ["soliq"] })
  const onError = (e: unknown) => setXato(extractErrorMessage(e as Error))
  const yoz = useMutation({
    mutationFn: async (n: Nomzod) =>
      (await SoliqService.soliqEsfBuyurtma({ body: { order_id: n.id } })).data,
    onSuccess: (e) => {
      setXato("")
      setKorish(e)
      yangila()
    },
    onError,
  })
  const amal = useMutation({
    mutationFn: async ({ id, t }: { id: number; t: "yubor" | "bekor" }) =>
      t === "yubor"
        ? SoliqService.soliqEsfYubor({ path: { esf_id: id } })
        : SoliqService.soliqEsfBekor({ path: { esf_id: id } }),
    onSuccess: () => {
      setXato("")
      yangila()
    },
    onError,
  })
  const ishlov = useMutation({
    mutationFn: async () => (await SoliqService.soliqIshlov()).data,
    onSuccess: yangila,
    onError,
  })
  const boshla = (n: Nomzod) => {
    if (n.tur === "hujjat") return setHujjat(n)
    if (!n.tayyor && n.client_id != null)
      return setRekvizit({ id: n.client_id, nomi: n.mijoz, keyin: n })
    yoz.mutate(n)
  }
  return (
    <div className="grid gap-3 xl:grid-cols-[26rem_1fr]">
      {tasdiqOyna}
      <Karta title={`ESF yozilmagan sotuvlar · ${nomzod?.length ?? 0}`}>
        <p className="text-xs text-muted-foreground">
          Yetkazilgan buyurtmalar va ombor sotuvlari (90 kun). Yuridik mijozniki
          uchun ESF yoziladi.
        </p>
        {(nomzod ?? []).map((n) => (
          <div
            key={`${n.tur}-${n.id}`}
            className="flex items-center justify-between gap-2 border-b py-2 text-sm"
          >
            <span>
              <b>{n.no}</b> · {n.mijoz || "—"}
              <span className="block text-xs text-muted-foreground">
                {formatDate(n.sana)} ·{" "}
                {n.tur === "buyurtma" ? "buyurtma" : "ombor sotuvi"}
                {n.tur === "buyurtma" && !n.tayyor && " · rekvizit yo'q"}
              </span>
            </span>
            <span className="num">{formatMoney(n.summa)}</span>
            <Button size="sm" variant="outline" onClick={() => boshla(n)}>
              ESF yozish
            </Button>
          </div>
        ))}
        {nomzod?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Hammasiga ESF yozilgan
          </p>
        )}
      </Karta>
      <Karta
        title={
          <span className="flex items-center justify-between gap-2">
            Chiquvchi ESF
            <LoadingButton
              size="sm"
              variant="outline"
              loading={ishlov.isPending}
              onClick={() => ishlov.mutate()}
            >
              Navbatni hozir yuborish
            </LoadingButton>
          </span>
        }
      >
        <Xato text={xato} />
        <Table>
          <TableHeader>
            <TableRow>
              {[
                "ESF",
                "Sana",
                "Xaridor",
                "Manba",
                "QQS",
                "Jami",
                "Holat",
                "",
              ].map((h) => (
                <TableHead key={h}>{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {(esflar ?? []).map((e) => (
              <TableRow key={e.id}>
                <TableCell>
                  <button
                    type="button"
                    className="font-mono text-xs text-primary underline"
                    onClick={() => setKorish(e)}
                  >
                    {e.no}
                  </button>
                </TableCell>
                <TableCell>{formatDate(e.sana)}</TableCell>
                <TableCell>
                  {e.kontragent}
                  <span className="block text-xs text-muted-foreground">
                    STIR {e.kontragent_stir}
                  </span>
                </TableCell>
                <TableCell className="text-xs">
                  {e.order_number ?? e.stock_doc_no}
                </TableCell>
                <TableCell className={num_r}>{formatMoney(e.qqs)}</TableCell>
                <TableCell className={cn(num_r, "font-semibold")}>
                  {formatMoney(e.jami)}
                </TableCell>
                <TableCell>
                  <Holat h={e.holat} />
                  {e.xato && (
                    <span
                      className="block max-w-56 truncate text-xs text-red-700"
                      title={e.xato}
                    >
                      {e.xato}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {(e.holat === "qoralama" || e.holat === "xato") && (
                    <Button
                      size="sm"
                      onClick={() =>
                        sora({
                          title: "ESF ni soliq operatoriga yuborasizmi?",
                          description:
                            "Yuborilgan ESF o'zgartirilmaydi — xato bo'lsa faqat bekor qilinadi va yangisi yoziladi.",
                          confirmText: "Yuborish",
                          onConfirm: () =>
                            amal.mutate({ id: e.id, t: "yubor" }),
                        })
                      }
                    >
                      Yuborish
                    </Button>
                  )}
                  {!["bekor", "rad_etildi"].includes(e.holat) && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        sora({
                          title: "ESF ni bekor qilasizmi?",
                          description: "Bekor qilingan ESF qaytarilmaydi.",
                          confirmText: "Bekor qilish",
                          destructive: true,
                          onConfirm: () =>
                            amal.mutate({ id: e.id, t: "bekor" }),
                        })
                      }
                    >
                      Bekor
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {esflar?.length === 0 && (
          <p className="text-sm text-muted-foreground">Hali ESF yo'q</p>
        )}
      </Karta>
      <EsfDialog e={korish} onClose={() => setKorish(null)} />
      <MijozDialog
        clientId={rekvizit?.id ?? null}
        nomi={rekvizit?.nomi ?? ""}
        onClose={() => setRekvizit(null)}
        onSaved={() => {
          const n = rekvizit?.keyin
          setRekvizit(null)
          yangila()
          if (n) yoz.mutate(n)
        }}
      />
      <HujjatDialog
        n={hujjat}
        onClose={() => setHujjat(null)}
        onDone={(e) => {
          setHujjat(null)
          setKorish(e)
          yangila()
        }}
        onRekvizit={(id, nomi) => setRekvizit({ id, nomi })}
      />
    </div>
  )
}

/** Ombor sotuvi uchun ESF: xaridor mijozni tanlash (hujjatda mijoz matn bilan yozilgan) */
function HujjatDialog({
  n,
  onClose,
  onDone,
  onRekvizit,
}: {
  n: Nomzod | null
  onClose: () => void
  onDone: (e: EsfRead) => void
  onRekvizit: (id: number, nomi: string) => void
}) {
  const [q, setQ] = useState("")
  const [xato, setXato] = useState("")
  const { data } = useQuery({
    queryKey: ["clients", "soliq", q || n?.mijoz],
    enabled: n != null,
    queryFn: async () =>
      (
        await ClientsService.readClients({
          query: { search: q || n?.mijoz || "", limit: 10 },
        })
      ).data,
  })
  const yoz = useMutation({
    mutationFn: async (clientId: number) =>
      (
        await SoliqService.soliqEsfHujjat({
          body: { stock_doc_id: n?.id ?? 0, client_id: clientId },
        })
      ).data,
    onSuccess: (e) => {
      setXato("")
      onDone(e)
    },
    onError: (e) => setXato(extractErrorMessage(e)),
  })
  return (
    <Dialog open={n != null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{n?.no} · xaridor</DialogTitle>
        </DialogHeader>
        <Input
          placeholder={`Mijoz qidirish (${n?.mijoz ?? ""})`}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {(data?.data ?? []).map((c) => (
          <div
            key={c.id}
            className="flex items-center justify-between gap-2 text-sm"
          >
            <span>
              {c.full_name}
              <span className="block text-xs text-muted-foreground">
                {c.phone}
              </span>
            </span>
            <span className="flex gap-1">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onRekvizit(c.id, c.full_name)}
              >
                Rekvizit
              </Button>
              <LoadingButton
                size="sm"
                loading={yoz.isPending}
                onClick={() => yoz.mutate(c.id)}
              >
                ESF yozish
              </LoadingButton>
            </span>
          </div>
        ))}
        <Xato text={xato} />
      </DialogContent>
    </Dialog>
  )
}

// ───────────────────────── kiruvchi ESF ─────────────────────────
function Kiruvchi() {
  const qc = useQueryClient()
  const [tasdiqOyna, sora] = useTasdiq()
  const [xato, setXato] = useState("")
  const [korish, setKorish] = useState<EsfRead | null>(null)
  const [rad, setRad] = useState<EsfRead | null>(null)
  const [sabab, setSabab] = useState("")
  const [sv, setSv] = useState({ nomi: "", stir: "", raqam: "", jami: "" })
  const { data } = useQuery({
    queryKey: ["soliq", "esf", "kiruvchi"],
    queryFn: async () =>
      (await SoliqService.soliqEsflar({ query: { tur: "kiruvchi" } })).data,
  })
  const { data: k } = useQuery({
    queryKey: ["soliq", "korxona"],
    queryFn: async () => (await SoliqService.soliqKorxona()).data,
  })
  const yangila = () => qc.invalidateQueries({ queryKey: ["soliq"] })
  const onError = (e: unknown) => setXato(extractErrorMessage(e as Error))
  const javob = useMutation({
    mutationFn: async (v: { id: number; qabul: boolean; sabab?: string }) =>
      SoliqService.soliqEsfJavob({
        path: { esf_id: v.id },
        body: { qabul: v.qabul, sabab: v.sabab ?? "" },
      }),
    onSuccess: () => {
      setXato("")
      setRad(null)
      setSabab("")
      yangila()
    },
    onError,
  })
  const ol = useMutation({
    mutationFn: async () => (await SoliqService.soliqIshlov()).data,
    onSuccess: yangila,
    onError,
  })
  const sinov = useMutation({
    mutationFn: async () =>
      SoliqService.soliqSinovKiruvchi({
        body: {
          sotuvchi_nomi: sv.nomi,
          sotuvchi_stir: sv.stir,
          raqam: sv.raqam,
          sana: bugun(),
          jami: sv.jami,
          qqs_foiz: "12",
        },
      }),
    onSuccess: async () => {
      setXato("")
      setSv({ nomi: "", stir: "", raqam: "", jami: "" })
      await ol.mutateAsync()
    },
    onError,
  })
  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_22rem]">
      {tasdiqOyna}
      <Karta
        title={
          <span className="flex items-center justify-between gap-2">
            Kiruvchi ESF (yetkazib beruvchilardan)
            <LoadingButton
              size="sm"
              variant="outline"
              loading={ol.isPending}
              onClick={() => ol.mutate()}
            >
              Operatordan olish
            </LoadingButton>
          </span>
        }
      >
        <Xato text={xato} />
        <Table>
          <TableHeader>
            <TableRow>
              {[
                "ESF",
                "Raqam · sana",
                "Sotuvchi",
                "Ombor kirimi",
                "QQS",
                "Jami",
                "Holat",
                "",
              ].map((h) => (
                <TableHead key={h}>{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data ?? []).map((e) => (
              <TableRow key={e.id}>
                <TableCell>
                  <button
                    type="button"
                    className="font-mono text-xs text-primary underline"
                    onClick={() => setKorish(e)}
                  >
                    {e.no}
                  </button>
                </TableCell>
                <TableCell>
                  {e.raqam} · {formatDate(e.sana)}
                </TableCell>
                <TableCell>
                  {e.kontragent}
                  <span className="block text-xs text-muted-foreground">
                    STIR {e.kontragent_stir}
                  </span>
                </TableCell>
                <TableCell
                  className={cn("text-xs", !e.stock_doc_no && "text-amber-700")}
                >
                  {e.stock_doc_no ?? "mos kirim topilmadi"}
                </TableCell>
                <TableCell className={num_r}>{formatMoney(e.qqs)}</TableCell>
                <TableCell className={cn(num_r, "font-semibold")}>
                  {formatMoney(e.jami)}
                </TableCell>
                <TableCell>
                  <Holat h={e.holat} />
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {e.holat === "kutilmoqda" && (
                    <>
                      <Button
                        size="sm"
                        onClick={() =>
                          sora({
                            title: "Kiruvchi ESF ni qabul qilasizmi?",
                            description:
                              "Qabul qilingan ESF bo'yicha QQS hisobga olinadi va javob ta'minotchiga yuboriladi.",
                            confirmText: "Qabul qilish",
                            onConfirm: () =>
                              javob.mutate({ id: e.id, qabul: true }),
                          })
                        }
                      >
                        Qabul
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setRad(e)}
                      >
                        Rad
                      </Button>
                    </>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Kiruvchi ESF yo'q</p>
        )}
        <p className="text-xs text-muted-foreground">
          Qabul qilingan ESF dagi QQS QQS to'lovchida hisobga olinadi
          (to'lanadigan QQS kamayadi). Ombor kirimi bilan sotuvchi nomi va summa
          bo'yicha bog'lanadi.
        </p>
      </Karta>
      {k?.esf_operator === "sinov" && (
        <Karta title="Sinov: yetkazib beruvchi ESF yuboradi">
          <p className="text-xs text-muted-foreground">
            Faqat lokal sinov operatorida — haqiqiy operatorda ESF yetkazib
            beruvchidan keladi.
          </p>
          <Maydon
            l="Sotuvchi nomi"
            v={sv.nomi}
            on={(v) => setSv({ ...sv, nomi: v })}
          />
          <div className="grid grid-cols-2 gap-2">
            <Maydon
              l="STIR"
              v={sv.stir}
              on={(v) => setSv({ ...sv, stir: v.replace(/\D/g, "") })}
            />
            <Maydon
              l="Raqam"
              v={sv.raqam}
              on={(v) => setSv({ ...sv, raqam: v })}
            />
          </div>
          <Maydon
            l="Jami (QQS 12 % bilan)"
            v={sv.jami}
            on={(v) => setSv({ ...sv, jami: v.replace(/[^0-9.]/g, "") })}
          />
          <LoadingButton
            loading={sinov.isPending}
            onClick={() => sinov.mutate()}
          >
            Yuborish (sinov)
          </LoadingButton>
        </Karta>
      )}
      <EsfDialog e={korish} onClose={() => setKorish(null)} />
      <Dialog open={rad != null} onOpenChange={(o) => !o && setRad(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rad etish · {rad?.no}</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="Sabab"
            value={sabab}
            onChange={(e) => setSabab(e.target.value)}
          />
          <DialogFooter>
            <LoadingButton
              loading={javob.isPending}
              disabled={!sabab.trim()}
              onClick={() =>
                rad && javob.mutate({ id: rad.id, qabul: false, sabab })
              }
            >
              Rad etish
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ───────────────────────── hisobot ─────────────────────────
function Hisobot() {
  const [oy, setOy] = useState(bugun().slice(0, 7))
  const { data } = useQuery({
    queryKey: ["soliq", "kitob", oy],
    queryFn: async () =>
      (await SoliqService.soliqKitob({ query: { oy } })).data,
  })
  const csv = useMutation({
    mutationFn: async () => {
      const res = await client.instance.get<Blob>(
        `/api/v1/soliq/kitob.csv?oy=${oy}`,
        {
          responseType: "blob",
        },
      )
      const url = URL.createObjectURL(res.data)
      const a = document.createElement("a")
      a.href = url
      a.download = `qqs_kitobi_${oy}.csv`
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 0)
    },
  })
  const o = data?.oy
  const qator = (l: string, v: string | number, cls?: string) => (
    <TableRow key={l} className={cls}>
      <TableCell>{l}</TableCell>
      <TableCell className={num_r}>{formatMoney(v)}</TableCell>
    </TableRow>
  )
  const kitob = (rows: EsfRead[]) => (
    <Table>
      <TableHeader>
        <TableRow>
          {[
            "Sana",
            "ESF / raqam",
            "Kontragent",
            "STIR",
            "QQSsiz",
            "QQS",
            "Jami",
          ].map((h) => (
            <TableHead key={h}>{h}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((e) => (
          <TableRow key={e.id}>
            <TableCell>{formatDate(e.sana)}</TableCell>
            <TableCell className="text-xs">
              {e.no}
              {e.raqam && ` · ${e.raqam}`}
            </TableCell>
            <TableCell>{e.kontragent}</TableCell>
            <TableCell className="font-mono text-xs">
              {e.kontragent_stir}
            </TableCell>
            <TableCell className={num_r}>{formatMoney(e.summa)}</TableCell>
            <TableCell className={num_r}>{formatMoney(e.qqs)}</TableCell>
            <TableCell className={num_r}>{formatMoney(e.jami)}</TableCell>
          </TableRow>
        ))}
        {rows.length === 0 && (
          <TableRow>
            <TableCell colSpan={7} className="text-muted-foreground">
              Yozuv yo'q
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  )
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 print:hidden">
        <Input
          type="month"
          className="w-44"
          value={oy}
          onChange={(e) => e.target.value && setOy(e.target.value)}
        />
        <LoadingButton
          variant="outline"
          loading={csv.isPending}
          onClick={() => csv.mutate()}
        >
          <Download /> QQS kitobi (CSV)
        </LoadingButton>
        <Button variant="outline" onClick={() => window.print()}>
          <Printer /> A4
        </Button>
      </div>
      {o && (
        <Karta
          title={`Soliq · ${o.oy} · ${
            o.rejim === "qqs"
              ? `QQS to'lovchi (${num(o.qqs_foiz)} %)`
              : o.rejim === "aylanma"
                ? `aylanmadan soliq (${num(o.aylanma_foiz)} %)`
                : "rejim sozlanmagan"
          }`}
          className="max-w-2xl"
        >
          <Table>
            <TableBody>
              {qator("Yetkazilgan buyurtmalar", o.buyurtma)}
              {qator("Do'kon sotuvi", o.dokon)}
              {qator("Aylanma (QQS bilan)", o.aylanma, "font-semibold")}
              {o.rejim === "qqs" && (
                <>
                  {qator("Sotuvdagi QQS", o.sotuv_qqs)}
                  {qator(
                    "   shundan ESF yozilmagan sotuvda (jismoniy shaxs yoki hali yozilmagan)",
                    data?.esfsiz_qqs ?? 0,
                  )}
                  {qator(
                    "Xarid QQS (qabul qilingan kiruvchi ESF)",
                    -num(o.xarid_qqs),
                  )}
                  {num(o.tolanadigan_qqs) >= 0
                    ? qator("To'lanadigan QQS", o.tolanadigan_qqs, "font-bold")
                    : qator(
                        "Ortiqcha xarid QQS — keyingi oyga o'tadi",
                        -num(o.tolanadigan_qqs),
                        "font-bold text-emerald-700",
                      )}
                </>
              )}
              {o.rejim === "aylanma" &&
                qator("Aylanmadan soliq", o.aylanma_soliq, "font-bold")}
            </TableBody>
          </Table>
        </Karta>
      )}
      <Karta title="Sotuv kitobi">{kitob(data?.sotuv ?? [])}</Karta>
      <Karta title="Xarid kitobi">{kitob(data?.xarid ?? [])}</Karta>
    </div>
  )
}

// ───────────────────────── sozlamalar ─────────────────────────
function Sozlamalar() {
  const qc = useQueryClient()
  const [xato, setXato] = useState("")
  const [ok, setOk] = useState("")
  const onError = (e: unknown) => {
    setOk("")
    setXato(extractErrorMessage(e as Error))
  }
  const { data: k0 } = useQuery({
    queryKey: ["soliq", "korxona"],
    queryFn: async () => (await SoliqService.soliqKorxona()).data,
  })
  const [k, setK] = useState<typeof k0 | null>(null)
  const kk = k ?? k0
  const { data: rejimlar } = useQuery({
    queryKey: ["soliq", "rejimlar"],
    queryFn: async () => (await SoliqService.soliqRejimlar()).data,
  })
  const [rj, setRj] = useState({
    amal_boshi: `${bugun().slice(0, 7)}-01`,
    rejim: "qqs" as "qqs" | "aylanma",
    qqs_foiz: "12",
    aylanma_foiz: "4",
  })
  const korxona = useMutation({
    mutationFn: async () => kk && SoliqService.soliqKorxonaSaqla({ body: kk }),
    onSuccess: () => {
      setXato("")
      setOk("Korxona rekvizitlari saqlandi")
      setK(null)
      qc.invalidateQueries({ queryKey: ["soliq"] })
    },
    onError,
  })
  const rejim = useMutation({
    mutationFn: async () => SoliqService.soliqRejimQosh({ body: rj }),
    onSuccess: () => {
      setXato("")
      setOk("Rejim yozildi")
      qc.invalidateQueries({ queryKey: ["soliq"] })
    },
    onError,
  })
  const set =
    (key: string, raqam = false) =>
    (v: string) =>
      kk && setK({ ...kk, [key]: raqam ? v.replace(/\D/g, "") : v })
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      <div className="flex flex-col gap-3">
        <Xato text={xato} />
        {ok && (
          <div className="rounded border border-emerald-300 bg-emerald-50 p-2 text-sm text-emerald-900">
            {ok}
          </div>
        )}
        <Karta title="Soliq rejimi (sanadan boshlab, tarix saqlanadi)">
          <p className="text-xs text-muted-foreground">
            QQS to'lovchi yoki aylanmadan soliq to'lovchi — har korxona o'zi
            tanlaydi. Rejim yil o'rtasida o'zgarsa yangi qator yozing: o'tgan
            oylar eski rejim bo'yicha qoladi. Stavkani buxgalter tasdiqlaydi.
          </p>
          <div className="grid grid-cols-4 items-end gap-2">
            <div className="text-xs text-muted-foreground uppercase">
              Sanadan
              <Input
                type="date"
                className="mt-1"
                value={rj.amal_boshi}
                onChange={(e) => setRj({ ...rj, amal_boshi: e.target.value })}
              />
            </div>
            <div className="flex gap-1">
              {(["qqs", "aylanma"] as const).map((r) => (
                <Button
                  key={r}
                  size="sm"
                  variant={rj.rejim === r ? "default" : "outline"}
                  onClick={() => setRj({ ...rj, rejim: r })}
                >
                  {r === "qqs" ? "QQS" : "Aylanma"}
                </Button>
              ))}
            </div>
            <Maydon
              l="QQS, %"
              v={rj.qqs_foiz}
              on={(v) => setRj({ ...rj, qqs_foiz: v })}
            />
            <Maydon
              l="Aylanma, %"
              v={rj.aylanma_foiz}
              on={(v) => setRj({ ...rj, aylanma_foiz: v })}
            />
          </div>
          <LoadingButton
            className="self-start"
            loading={rejim.isPending}
            onClick={() => rejim.mutate()}
          >
            Rejimni yozish
          </LoadingButton>
          {(rejimlar ?? []).map((r) => (
            <div
              key={r.id}
              className="flex justify-between border-b py-1 text-sm"
            >
              <span>{formatDate(r.amal_boshi)} dan</span>
              <b>
                {r.rejim === "qqs"
                  ? `QQS to'lovchi · ${num(r.qqs_foiz)} %`
                  : `Aylanmadan soliq · ${num(r.aylanma_foiz)} %`}
              </b>
            </div>
          ))}
          {rejimlar?.length === 0 && (
            <p className="text-sm text-amber-700">
              Rejim hali yozilmagan — ESF yozilmaydi
            </p>
          )}
        </Karta>
        <MxikKarta onError={onError} />
      </div>
      {kk && (
        <Karta title="Korxona rekvizitlari">
          <div className="grid grid-cols-2 gap-2">
            <Maydon
              l="Nomi"
              v={kk.nomi ?? ""}
              on={set("nomi")}
              className="col-span-2"
            />
            <Maydon l="STIR (9)" v={kk.stir ?? ""} on={set("stir", true)} />
            <Maydon l="QQS kodi" v={kk.qqs_kod ?? ""} on={set("qqs_kod")} />
            <Maydon
              l="Manzil"
              v={kk.manzil ?? ""}
              on={set("manzil")}
              className="col-span-2"
            />
            <Maydon
              l="Bank"
              v={kk.bank ?? ""}
              on={set("bank")}
              className="col-span-2"
            />
            <Maydon l="MFO (5)" v={kk.mfo ?? ""} on={set("mfo", true)} />
            <Maydon
              l="Hisob raqami (20)"
              v={kk.hisob_raqam ?? ""}
              on={set("hisob_raqam", true)}
            />
            <Maydon l="Rahbar" v={kk.direktor ?? ""} on={set("direktor")} />
            <Maydon
              l="Bosh buxgalter"
              v={kk.buxgalter ?? ""}
              on={set("buxgalter")}
            />
            <Maydon
              l="Buyurtma ESF qatori nomi"
              v={kk.buyurtma_nomi ?? ""}
              on={set("buyurtma_nomi")}
              className="col-span-2"
            />
            <Maydon
              l="Buyurtma MXIK (17)"
              v={kk.buyurtma_mxik ?? ""}
              on={set("buyurtma_mxik", true)}
            />
            <Maydon
              l="Birlik kodi"
              v={kk.buyurtma_birlik ?? ""}
              on={set("buyurtma_birlik")}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            ESF operatori: {kk.esf_operator} (lokal sinov). Haqiqiy operator
            uchun API kaliti va E-IMZO kerak.
          </p>
          <LoadingButton
            className="self-start"
            loading={korxona.isPending}
            onClick={() => korxona.mutate()}
          >
            Saqlash
          </LoadingButton>
        </Karta>
      )}
    </div>
  )
}

function MxikKarta({ onError }: { onError: (e: unknown) => void }) {
  const qc = useQueryClient()
  const [q, setQ] = useState("")
  const { data } = useQuery({
    queryKey: ["catalog", "soliq", q],
    queryFn: async () =>
      (
        await CatalogService.readCatalogItems({
          query: { search: q || null, limit: 15 },
        })
      ).data,
  })
  const saqla = useMutation({
    mutationFn: async (v: {
      id: number
      mxik: string
      birlik_kod: string
      qqs_turi: "standart" | "nol" | "ozod"
    }) => SoliqService.soliqMxikSaqla({ path: { item_id: v.id }, body: v }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["catalog", "soliq"] }),
    onError,
  })
  return (
    <Karta title="Katalog: MXIK va QQS turi">
      <p className="text-xs text-muted-foreground">
        MXIK siz pozitsiya ESF ga kirmaydi. QQS turi: standart (rejim stavkasi),
        0 % yoki ozod.
      </p>
      <Input
        placeholder="Pozitsiya qidirish"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {(data?.data ?? []).map((it) => (
        <div
          key={it.id}
          className="grid grid-cols-[1fr_11rem_4rem_6rem] items-center gap-2 text-sm"
        >
          <span className="truncate" title={it.name}>
            <span className="font-mono text-xs text-muted-foreground">
              {it.code}
            </span>{" "}
            {it.name}
          </span>
          <Input
            key={`m${it.mxik}`}
            className="num h-8"
            placeholder="MXIK (17)"
            defaultValue={it.mxik ?? ""}
            onBlur={(e) =>
              e.target.value !== (it.mxik ?? "") &&
              saqla.mutate({
                id: it.id,
                mxik: e.target.value.replace(/\D/g, ""),
                birlik_kod: it.birlik_kod ?? "",
                qqs_turi: (it.qqs_turi ?? "standart") as "standart",
              })
            }
          />
          <Input
            key={`b${it.birlik_kod}`}
            className="h-8"
            placeholder="birlik"
            defaultValue={it.birlik_kod ?? ""}
            onBlur={(e) =>
              e.target.value !== (it.birlik_kod ?? "") &&
              saqla.mutate({
                id: it.id,
                mxik: it.mxik ?? "",
                birlik_kod: e.target.value,
                qqs_turi: (it.qqs_turi ?? "standart") as "standart",
              })
            }
          />
          <select
            className="h-8 rounded border bg-background px-1 text-xs"
            value={it.qqs_turi ?? "standart"}
            onChange={(e) =>
              saqla.mutate({
                id: it.id,
                mxik: it.mxik ?? "",
                birlik_kod: it.birlik_kod ?? "",
                qqs_turi: e.target.value as "standart",
              })
            }
          >
            <option value="standart">standart</option>
            <option value="nol">0 %</option>
            <option value="ozod">ozod</option>
          </select>
        </div>
      ))}
    </Karta>
  )
}
