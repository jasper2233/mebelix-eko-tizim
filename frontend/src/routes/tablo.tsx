// TABLO (TZ 9): tsex zalidagi TV ekran — buyurtmalar × bosqichlar jonli matritsasi.
// Rejimlar: HAJM / SONI / FOIZ. Kontekst-aware: tablo user ish markazi ustuni ajratiladi.

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import { TabloService } from "@/client"
import { useMesWs } from "@/hooks/useMesWs"
import { requireAuth } from "@/lib/guards"
import { deadlineTone, formatDate, POST_COLORS } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  getMachinesQueryOptions,
  getTabloMatrixQueryOptions,
} from "@/queries/mes"
import { getCurrentUserQueryOptions } from "@/queries/users"

export const Route = createFileRoute("/tablo")({
  component: TabloPage,
  head: () => ({ meta: [{ title: "TABLO | MebeliX" }] }),
  beforeLoad: async () => {
    await requireAuth()
  },
})

type Mode = "hajm" | "soni" | "foiz"

const UNIT_LABELS: Record<string, string> = {
  m2: "m²",
  meter: "m",
  piece: "dona",
}

const MODES: Mode[] = ["hajm", "soni", "foiz"]
const MODE_KEY = "tablo-mode"

function TabloPage() {
  const queryClient = useQueryClient()
  // Rejim saqlanadi: tsexda tanlangan ko'rinish sahifa yangilanganda ham
  // (deploy reload, TV qayta yoqilishi) o'zgarmasin.
  const [mode, setMode] = useState<Mode>(() => {
    const saved = localStorage.getItem(MODE_KEY) as Mode | null
    return saved && MODES.includes(saved) ? saved : "foiz"
  })
  const [drill, setDrill] = useState<number | null>(null)

  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode)
  }, [mode])

  const { data: me } = useQuery(getCurrentUserQueryOptions())
  const { data: machines } = useQuery({
    ...getMachinesQueryOptions(),
    enabled: me?.role === "tablo",
  })
  const { data, isLoading } = useQuery(getTabloMatrixQueryOptions())

  const { online } = useMesWs(
    useCallback(
      (event) => {
        if (event.type.startsWith("scan.") || event.type.startsWith("order.")) {
          queryClient.invalidateQueries({ queryKey: ["tablo"] })
        }
      },
      [queryClient],
    ),
  )

  // WS uzilib qayta ulanganda oradagi hodisalar o'tkazib yuborilgan bo'ladi —
  // 60s pollingni kutmasdan darhol to'liq yangilanadi.
  const wasOnline = useRef(online)
  useEffect(() => {
    if (online && !wasOnline.current) {
      queryClient.invalidateQueries({ queryKey: ["tablo"] })
    }
    wasOnline.current = online
  }, [online, queryClient])

  // Sahifani qayta yuklash MA'LUMOT yangiligi uchun EMAS — buni WS push va
  // 60s polling (getTabloMatrixQueryOptions) ta'minlaydi. Yagona vazifasi:
  // deploydan keyin yangi bundle'ni olish, chunki devordagi TV hech qachon
  // qo'lda yangilanmaydi. Avval 5 daqiqada bir edi: har safar oq ekran
  // chaqnab, ochilgan detal ro'yxati yopilib, tanlangan rejim ham "foiz" ga
  // qaytib ketardi. Endi soatiga bir marta va faqat hech kim detal
  // ro'yxatini ochmagan paytda.
  useEffect(() => {
    if (drill !== null) return
    const reload = setTimeout(() => window.location.reload(), 60 * 60_000)
    return () => clearTimeout(reload)
  }, [drill])

  const myMachine = machines?.find((m) => m.id === me?.machine_id)
  const contextPostId = myMachine?.post_id ?? null

  if (drill !== null)
    return (
      <TabloOrderDrill
        orderId={drill}
        onBack={() => setDrill(null)}
        mode={mode}
      />
    )

  return (
    <div className="flex h-dvh flex-col bg-surface text-foreground">
      <header className="flex items-center gap-4 border-b border-border bg-card px-5 py-2 shadow-sm">
        {/* Brend sidebar va login bilan bitta manbadan — to'liq logo.
            Sarlavha devordagi ekranda faqat chrome: balandligi matritsadan
            olingan joy, shuning uchun logo h-12 dan oshmaydi. */}
        <img
          src="/assets/logo/logo-gold.png"
          alt="MebeliX"
          className="h-12 w-auto shrink-0"
        />
        {myMachine && (
          <span className="rounded-sm bg-secondary px-3 py-1.5 text-xl font-bold">
            JORIY NUQTA: {myMachine.name}
          </span>
        )}
        <div className="mx-auto flex gap-2">
          {(["hajm", "soni", "foiz"] as Mode[]).map((m) => (
            <button
              type="button"
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "rounded-sm px-4 py-2 text-xl font-black uppercase outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 active:scale-95",
                mode === m
                  ? "bg-(--brand-gold) text-foreground"
                  : "bg-secondary hover:bg-accent",
              )}
            >
              {m}
            </button>
          ))}
        </div>
        <span
          className={cn(
            "size-4 rounded-full",
            online ? "bg-green-500" : "bg-red-500",
          )}
        />
        {!online && (
          <span className="text-xl font-bold text-red-600">OFFLINE</span>
        )}
        {/* Panelga qaytish faqat odam foydalanuvchiga: `tablo` roli qurilma
            akkaunti, u boshqa sahifaga kira olmaydi (_layout uni shu yerga
            qaytaradi). Busiz admin sidebar'dagi "LIVE Tablo" dan kelib
            to'liq ekranda qamalib qolardi — faqat brauzer tugmasi qutqarardi.
            Uslub — reestr/anketa/xarita sahifalaridagi qaytish havolasi bilan
            bir xil (muted matn + ArrowLeft), to'ldirilgan chip EMAS: chip
            ko'rinishi rejim tugmalari (HAJM/SONI/FOIZ) bilan bir xil bo'lib,
            chiqish havolasi rejim tanlagichning to'rtinchi bandiday o'qilardi. */}
        {me && me.role !== "tablo" && (
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-sm text-base font-semibold text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          >
            <ArrowLeft className="size-5" /> Boshqaruv paneli
          </Link>
        )}
      </header>

      <main className="min-h-0 flex-1 overflow-auto p-4">
        {isLoading ? (
          <p className="p-8 text-center text-3xl text-muted-foreground">
            Yuklanmoqda...
          </p>
        ) : (
          <table className="w-full border-separate border-spacing-2">
            <thead>
              <tr className="text-2xl uppercase tracking-wider text-muted-foreground">
                <th className="sticky top-0 z-10 bg-surface px-2 text-left">
                  № / Buyurtma
                </th>
                <th className="sticky top-0 z-10 bg-surface px-2 text-left">
                  Topshirish sanasi
                </th>
                {data?.posts.map((p) => {
                  // Kontekst rejimida boshqa ustunlar RANG bilan susayadi, opacity bilan emas —
                  // opacity-40 oq fonda kontrastni 1.85:1 ga tushirib, uzoqdan o'qib bo'lmas qilardi.
                  const dim = Boolean(contextPostId && p.id !== contextPostId)
                  return (
                    <th
                      key={p.id}
                      className={cn(
                        "sticky top-0 z-10 bg-surface px-2 pb-1 text-center",
                        dim && "text-muted-foreground",
                      )}
                      style={dim ? undefined : { color: POST_COLORS[p.code] }}
                    >
                      {p.code}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {data && data.orders.length > 0 && (
                <tr>
                  <td className="rounded-l-lg bg-primary px-3 py-3 text-2xl font-black uppercase tracking-wider text-primary-foreground">
                    Jami
                  </td>
                  <td className="bg-primary/90" />
                  {data.posts.map((p) => {
                    let done = 0
                    let total = 0
                    let vDone = 0
                    let vTotal = 0
                    for (const o of data.orders) {
                      const st = o.stages[p.code]
                      if (!st) continue
                      done += st.done
                      total += st.total
                      vDone += st.volume_done
                      vTotal += st.volume_total
                    }
                    const unit = UNIT_LABELS[p.unit] ?? p.unit
                    const label =
                      mode === "hajm"
                        ? `${round1(vDone)} / ${round1(vTotal)} ${unit}`
                        : mode === "soni"
                          ? `${done} / ${total}`
                          : total
                            ? `${Math.round((done / total) * 1000) / 10}%`
                            : "—"
                    return (
                      <td
                        key={p.id}
                        className="num bg-primary px-2 py-3 text-center text-2xl font-black text-primary-foreground"
                      >
                        {total ? label : "—"}
                      </td>
                    )
                  })}
                </tr>
              )}
              {data?.orders.map((o, idx) => (
                <tr
                  key={o.id}
                  onClick={() => setDrill(o.id)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") setDrill(o.id)
                  }}
                  className="cursor-pointer hover:bg-accent"
                >
                  <td className="rounded-l-lg bg-card px-3 py-3 shadow-sm">
                    <span className="num mr-2 text-xl text-muted-foreground">
                      {idx + 1}
                    </span>
                    <span className="text-3xl font-bold">{o.number}</span>
                    {o.name && (
                      <span className="ml-2 hidden text-xl text-muted-foreground xl:inline">
                        {o.name}
                      </span>
                    )}
                  </td>
                  {/* Muddat toni signal: hammasi amber bo'lsa amber hech narsa anglatmaydi */}
                  <td
                    className={cn(
                      "num px-3 py-3 text-2xl font-semibold",
                      deadlineTone(o.deadline) === "overdue"
                        ? "bg-red-100 text-red-800"
                        : deadlineTone(o.deadline) === "today"
                          ? "bg-amber-100 text-amber-800"
                          : "text-muted-foreground",
                    )}
                  >
                    {formatDate(o.deadline)}
                  </td>
                  {data.posts.map((p) => (
                    <TabloCell
                      key={p.id}
                      stage={o.stages[p.code]}
                      unit={UNIT_LABELS[p.unit] ?? p.unit}
                      mode={mode}
                      dim={Boolean(contextPostId && p.id !== contextPostId)}
                      color={POST_COLORS[p.code]}
                      deadline={o.deadline}
                    />
                  ))}
                </tr>
              ))}
              {!data?.orders.length && (
                <tr>
                  <td
                    colSpan={2 + (data?.posts.length ?? 0)}
                    className="p-12 text-center text-3xl text-muted-foreground"
                  >
                    Aktiv buyurtmalar yo'q
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </main>
    </div>
  )
}

function TabloCell({
  stage,
  unit,
  mode,
  dim,
  color,
  deadline,
}: {
  stage?: {
    done: number
    total: number
    volume_total: number
    volume_done: number
  }
  unit: string
  mode: Mode
  dim: boolean
  color?: string
  deadline?: string | null
}) {
  // Skan kelib qiymat oshganda katak bir marta yashil uriladi (kamayishda —
  // skan bekor qilinganda — urilmaydi: bu tuzatish, yutuq emas).
  const done = stage?.done ?? 0
  const prevDone = useRef(done)
  const [flash, setFlash] = useState(false)
  useEffect(() => {
    const grew = done > prevDone.current
    prevDone.current = done
    if (!grew) return
    setFlash(true)
    const t = setTimeout(() => setFlash(false), 900)
    return () => clearTimeout(t)
  }, [done])

  if (!stage?.total) {
    return (
      <td className="bg-card px-2 py-3 text-center text-2xl text-muted-foreground shadow-sm">
        —
      </td>
    )
  }
  const pct = Math.round((stage.done / stage.total) * 1000) / 10
  const complete = stage.done >= stage.total
  const overdue =
    !complete && deadlineTone(deadline) === "overdue" && stage.done === 0

  let label: string
  if (mode === "hajm")
    label = `${round1(stage.volume_done)} / ${round1(stage.volume_total)} ${unit}`
  else if (mode === "soni") label = `${stage.done} / ${stage.total}`
  else label = `${pct}%`

  return (
    <td
      className={cn(
        "relative overflow-hidden rounded-sm px-2 py-3 text-center align-middle",
        complete
          ? "bg-green-100"
          : overdue
            ? "bg-red-100"
            : "bg-card shadow-sm",
        flash && "animate-cell-flash",
      )}
    >
      {/* Kontekst rejimida faqat progress to'ldirgichi susayadi — raqam to'liq
          kontrastda qoladi, aks holda 4 metrdan o'qib bo'lmasdi. */}
      {!complete && (
        <span
          className="absolute inset-y-0 left-0 transition-all duration-1000"
          style={{
            width: `${pct}%`,
            backgroundColor: color
              ? `color-mix(in srgb, ${color} ${dim ? 8 : 22}%, transparent)`
              : "rgba(0,0,0,0.06)",
          }}
        />
      )}
      <span
        className={cn(
          "num relative text-4xl font-black tabular-nums",
          complete
            ? "text-green-700"
            : overdue
              ? "text-red-700"
              : dim
                ? "text-muted-foreground"
                : "",
        )}
      >
        {complete ? "✓" : label}
      </span>
      {overdue && (
        <span className="relative block text-lg font-bold text-red-700">
          BOSHLANMADI
        </span>
      )}
    </td>
  )
}

function TabloOrderDrill({
  orderId,
  onBack,
  mode,
}: {
  orderId: number
  onBack: () => void
  mode: Mode
}) {
  const { data } = useQuery({
    queryKey: ["tablo", "order", orderId],
    queryFn: () => TabloService.readTabloOrder({ orderId }),
    refetchInterval: 30_000,
  })
  // Ustunlar matritsa postlaridan (order_index tartibida) — qotirilgan ro'yxat
  // OVAL kabi yangi postni ko'rsatmay qolardi
  const { data: matrix } = useQuery(getTabloMatrixQueryOptions())
  const drillPosts = matrix?.posts.map((p) => p.code) ?? []
  return (
    <div className="flex h-dvh flex-col bg-surface text-foreground">
      <header className="flex items-center gap-4 border-b border-border bg-card px-5 py-3 shadow-sm">
        <span className="text-4xl font-black">{data?.number ?? ""}</span>
        <span className="text-2xl text-muted-foreground">
          {data?.name ?? ""}
        </span>
        <span className="ml-auto text-xl font-bold uppercase tracking-widest text-muted-foreground">
          {/* Hujayralar bilan bir xil rejim (hajm drill'da soni'ga tushadi) */}
          {mode === "foiz" ? "Foiz nazorati" : "Soni nazorati"}
        </span>
      </header>
      <main className="min-h-0 flex-1 overflow-auto p-4">
        <table className="w-full border-separate border-spacing-2">
          <thead>
            <tr className="text-2xl uppercase tracking-wider text-muted-foreground">
              <th className="sticky top-0 z-10 bg-surface px-2 text-left">
                Detal
              </th>
              <th className="sticky top-0 z-10 bg-surface px-2 text-center">
                Soni
              </th>
              {drillPosts.map((c) => (
                <th
                  key={c}
                  className="sticky top-0 z-10 bg-surface px-2 text-center"
                  style={{ color: POST_COLORS[c] }}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.parts.map((p) => (
              <tr key={p.part_id}>
                <td className="rounded-l-lg bg-card px-3 py-3 shadow-sm">
                  <b className="num text-3xl">{p.code}</b>{" "}
                  <span className="text-xl text-muted-foreground">
                    {p.name}
                  </span>
                </td>
                <td className="num bg-card px-2 py-3 text-center text-3xl font-bold shadow-sm">
                  {p.count}
                </td>
                {drillPosts.map((c) => (
                  <TabloCell
                    key={c}
                    stage={p.stages[c]}
                    unit="dona"
                    mode={mode === "hajm" ? "soni" : mode}
                    dim={false}
                    color={POST_COLORS[c]}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </main>
      <button
        type="button"
        onClick={onBack}
        className="m-4 inline-flex self-start items-center gap-2 rounded-lg bg-secondary px-8 py-4 text-2xl font-black uppercase outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50 active:scale-95"
      >
        <ArrowLeft className="size-7" /> Orqaga
      </button>
    </div>
  )
}

function round1(v: number): number {
  return Math.round(v * 10) / 10
}
