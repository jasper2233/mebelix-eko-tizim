// TABLO (TZ 9): tsex zalidagi TV ekran — buyurtmalar × bosqichlar jonli matritsasi.
// Rejimlar: HAJM / SONI / FOIZ. Kontekst-aware: tablo user ish markazi ustuni ajratiladi.

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react"

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

/** "2 kun kechikdi" / "BUGUN" / "3 kun qoldi" — javobning O'ZI.
 *
 * Devor ekranida sana raqami foydasiz: odam uni bugungi kundan ayirishi kerak
 * bo'ladi. Muddat esa TABLO ning eng muhim signali — u hisoblab berilishi kerak.
 */
function deadlineCountdown(value?: string | null): string {
  if (!value) return "—"
  const target = new Date(value)
  const today = new Date()
  target.setHours(0, 0, 0, 0)
  today.setHours(0, 0, 0, 0)
  const days = Math.round((target.getTime() - today.getTime()) / 86_400_000)
  if (days < 0) return `${-days} kun kechikdi`
  if (days === 0) return "BUGUN"
  return `${days} kun qoldi`
}

/** Devor ekrani uchun o'lcham shkalasi — REJIMGA bog'liq.
 *
 * Toshishni ekran emas, ikkita narsa belgilaydi: yorliq uzunligi va ustun
 * ulushi. FOIZ da yorliq "99%" (~3em) — katta bo'lishi mumkin; HAJM/SONI da
 * "128 / 340" (~6em) — kichikroq bo'lishi SHART.
 *
 * Ilgari katak `text-4xl` (36px) qotirilgan edi. PRODDA O'LCHANDI (1745px,
 * HAJM rejimi): `5.7 / 27.4 m²` ustunga sig'may uch qatorga o'ralardi va
 * qator 66px o'rniga 144px bo'lardi — ekranga 9 emas, 4 buyurtma sig'ardi.
 *
 * Shkala IKKALA ildizga beriladi: matritsa ham, detal ro'yxati (drill) ham
 * bir xil `TabloCell` ni ishlatadi, drill esa alohida ildiz qaytaradi.
 */
function tabloScale(mode: Mode): React.CSSProperties {
  return {
    "--t-cell":
      mode === "foiz"
        ? "clamp(1.4rem, 2.2vw, 3.5rem)"
        : "clamp(0.85rem, 1.2vw, 2.25rem)",
    "--t-order": "clamp(1rem, 1.45vw, 2.75rem)",
    "--t-head": "clamp(0.7rem, 0.8vw, 1.6rem)",
    "--t-meta": "clamp(0.65rem, 0.72vw, 1.4rem)",
    "--t-badge": "clamp(0.55rem, 0.6vw, 1.1rem)",
  } as React.CSSProperties
}

/** Ma'lumot yoshi: "12s" / "3d" — devor ekranida raqam qisqa bo'lishi kerak */
function ageLabel(sec: number): string {
  return sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}d`
}

const MODES: Mode[] = ["hajm", "soni", "foiz"]
const MODE_KEY = "tablo-mode"

/** Sig'magan buyurtmalarni sahifalarga bo'lib, avtomat aylantiradi.
 *
 * Devordagi TV da sichqoncha ham, klaviatura ham yo'q — `overflow-auto` bor
 * bo'lsa ham hech kim varaqlamaydi. Prodda o'lchandi: 6 buyurtmadan keyin
 * qolgani ko'rinmay qolardi, 40 tada jadval ekrandan 7 barobar uzun edi.
 *
 * REJIM aylantirilmaydi, faqat SAHIFA: operator ekranga qaraganda nima
 * ko'rayotganini bilishi kerak, kerakli rejim qaytishini kutmasligi kerak.
 */
function usePagedRows<T>(rows: T[], enabled: boolean) {
  const bodyRef = useRef<HTMLTableSectionElement>(null)
  const [perPage, setPerPage] = useState(rows.length || 1)
  const [page, setPage] = useState(0)

  // Nechta sig'ishini O'LCHAYMIZ: qator balandligi shriftga, shrift esa ekran
  // kengligiga bog'liq — qotirilgan son 4K da ham, noutbukda ham xato bo'lardi.
  // ResizeObserver ekran o'lchami VA rejim almashuvini birdek ushlaydi
  // (rejim shriftni, shrift qator balandligini o'zgartiradi).
  useLayoutEffect(() => {
    const body = bodyRef.current
    const scroller = body?.closest("main")
    if (!body || !scroller) return
    const measure = () => {
      const trs = [...body.querySelectorAll("tr")]
      if (trs.length < 2) return setPerPage(rows.length || 1)
      const jami = trs[0].getBoundingClientRect().height
      const qator = trs[1].getBoundingClientRect().height
      const head =
        body.previousElementSibling?.getBoundingClientRect().height ?? 0
      const pad = getComputedStyle(scroller)
      const joy =
        scroller.clientHeight -
        Number.parseFloat(pad.paddingTop) -
        Number.parseFloat(pad.paddingBottom) -
        head -
        jami
      setPerPage(Math.max(1, Math.floor(joy / Math.max(qator, 1))))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(body)
    ro.observe(scroller)
    return () => ro.disconnect()
  }, [rows.length])

  // Sahifa QAYTA TIKLANMAYDI: matritsa har 5 soniyada yangilanadi, har
  // yangilanishda 1-sahifaga sakrasa hech kim oxirgi sahifani ko'rmasdi.
  const pages = Math.max(1, Math.ceil(rows.length / perPage))
  useEffect(() => {
    if (!enabled || pages < 2) return
    const id = setInterval(() => setPage((p) => (p + 1) % pages), 15_000)
    return () => clearInterval(id)
  }, [enabled, pages])

  const safe = Math.min(page, pages - 1)
  return {
    bodyRef,
    visible:
      pages > 1 ? rows.slice(safe * perPage, safe * perPage + perPage) : rows,
    page: safe,
    pages,
  }
}

/** Jonlilik ko'rsatkichi — yashil nuqtaning O'ZI yetarli emas.
 *
 * Nuqta soket ochiqligini isbotlaydi, RAQAMLAR yangiligini emas: soket
 * ulangan, lekin hodisa kelmasa va so'rov yiqilsa, ekran eski raqamlarni
 * ko'rsatib turaveradi — nuqta esa xotirjam yashil qolardi. Shuning uchun
 * ma'lumot YOSHI ko'rsatiladi va u har soniyada tikillaydi: bir qarashda
 * jonli ekani ko'rinadi, qotib qolsa raqam o'sib ketadi.
 *
 * Soat SHU komponent ichida: bo'lmasa har soniyada butun matritsa (40 qator
 * x 9 katak) qayta chizilardi.
 */
function LiveBadge({
  online,
  updatedAt,
}: {
  online: boolean
  updatedAt: number
}) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  const age = updatedAt ? Math.max(0, Math.round((now - updatedAt) / 1000)) : 0
  // So'rov 60 soniyada bir takrorlanadi — 90 dan oshsa yangilanish yiqilgan
  const stale = updatedAt > 0 && age > 90
  const live = online && !stale
  return (
    <span
      className={cn(
        "flex items-center gap-2 whitespace-nowrap rounded-sm px-3 py-1.5 font-bold tabular-nums",
        live ? "bg-secondary" : "bg-red-100 text-red-700",
      )}
      style={{ fontSize: "var(--t-head)" }}
    >
      {/* Tepkilayotgan halqa: harakat = jonli. Qotib qolgan yashil nuqta
          ham xuddi shunday ko'rinardi, ya'ni hech narsa isbotlamasdi. */}
      <span className="relative flex size-3 shrink-0">
        {live && (
          <span
            /* Harakat o'chirilgan bo'lsa halqa yo'qoladi — jonlilikni
               soniya hisoblagichi baribir isbotlab turadi */
            className="absolute inline-flex size-full animate-ping rounded-full bg-green-500 opacity-75 motion-reduce:hidden"
          />
        )}
        <span
          className={cn(
            "relative inline-flex size-3 rounded-full",
            live ? "bg-green-500" : "bg-red-500",
          )}
        />
      </span>
      {!online
        ? "ULANMADI"
        : stale
          ? `ESKI · ${ageLabel(age)}`
          : `JONLI · ${ageLabel(age)}`}
    </span>
  )
}

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
  const { data, isLoading, dataUpdatedAt } = useQuery(
    getTabloMatrixQueryOptions(),
  )
  // Sig'magan buyurtmalar sahifalanadi; drill ochiq bo'lsa aylanish to'xtaydi
  const paged = usePagedRows(data?.orders ?? [], drill === null)
  const closeDrill = useCallback(() => setDrill(null), [])

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
    return <TabloOrderDrill orderId={drill} onBack={closeDrill} mode={mode} />

  return (
    <div
      className="flex h-dvh flex-col bg-surface text-foreground"
      style={tabloScale(mode)}
    >
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
        {/* Aylanish JIM bo'lmasin: operator ekran o'zgarganda nima bo'lganini
            bilishi kerak, aks holda buyurtmasi "yo'qolgan"day tuyulardi */}
        {paged.pages > 1 && (
          <span
            className="num rounded-sm bg-secondary px-3 py-1.5 font-bold tabular-nums"
            style={{ fontSize: "var(--t-head)" }}
          >
            {paged.page + 1} / {paged.pages}
          </span>
        )}
        <LiveBadge online={online} updatedAt={dataUpdatedAt} />
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
          /* `table-fixed` + aniq ulushlar: kenglik MAZMUNGA bog'liq bo'lmasin.
             Ilgari ustunlar mazmunga qarab 87px dan 187px gacha sakrardi. */
          <table className="w-full table-fixed border-separate border-spacing-2">
            <colgroup>
              <col className="w-[15%]" />
              <col className="w-[10%]" />
              {data?.posts.map((p) => (
                <col
                  key={p.id}
                  style={{ width: `${75 / (data.posts.length || 1)}%` }}
                />
              ))}
            </colgroup>
            <thead>
              <tr
                className="uppercase tracking-wider text-muted-foreground"
                style={{ fontSize: "var(--t-head)" }}
              >
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
                      <span className="block whitespace-nowrap">{p.code}</span>
                      {/* Birlik USTUN xossasi: har katakda takrorlanishi
                          kenglikni bekorga oshirib, matnni o'ratardi */}
                      {mode === "hajm" && (
                        <span
                          className="block whitespace-nowrap font-normal normal-case tracking-normal opacity-60"
                          style={{ fontSize: "var(--t-meta)" }}
                        >
                          {UNIT_LABELS[p.unit] ?? p.unit}
                        </span>
                      )}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody ref={paged.bodyRef}>
              {data && data.orders.length > 0 && (
                <tr>
                  <td
                    className="rounded-l-lg bg-primary px-3 py-3 font-black uppercase tracking-wider text-primary-foreground"
                    style={{ fontSize: "var(--t-head)" }}
                  >
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
                    // Devor ekranida kasr shovqin: 27.4 va 27 bir xil ma'no
                    // beradi, kasr esa yorliqni uzaytirib o'ralishga olib kelardi
                    const label =
                      mode === "hajm"
                        ? `${Math.round(vDone)} / ${Math.round(vTotal)}`
                        : mode === "soni"
                          ? `${done} / ${total}`
                          : !total
                            ? "—"
                            : done >= total
                              ? "100%"
                              : `${Math.min(99, Math.floor((done / total) * 100))}%`
                    return (
                      <td
                        key={p.id}
                        className="num whitespace-nowrap bg-primary px-2 py-3 text-center font-black tabular-nums text-primary-foreground"
                        // Yig'indi butun tsex bo'yicha qo'shiladi — 5 xonali
                        // bo'lishi mumkin, shuning uchun bir pog'ona kichik
                        style={{ fontSize: "var(--t-head)" }}
                      >
                        {total ? label : "—"}
                      </td>
                    )
                  })}
                </tr>
              )}
              {paged.visible.map((o, idx) => (
                <tr
                  key={o.id}
                  onClick={() => setDrill(o.id)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") setDrill(o.id)
                  }}
                  className="cursor-pointer hover:bg-accent"
                >
                  {/* MATN ustuni — bu yerda qisqartirish O'RINLI: loyiha nomi
                      ixtiyoriy uzunlikda bo'ladi. Raqam kataklarida esa
                      qisqartirish TAQIQ — kesilgan son yolg'on ma'lumot. */}
                  <td className="truncate rounded-l-lg bg-card px-3 py-3 shadow-sm">
                    <span
                      className="num mr-2 text-muted-foreground"
                      style={{ fontSize: "var(--t-meta)" }}
                    >
                      {idx + 1}
                    </span>
                    <span
                      className="font-bold"
                      style={{ fontSize: "var(--t-order)" }}
                    >
                      {o.number}
                    </span>
                    {o.name && (
                      <span
                        className="ml-2 hidden text-muted-foreground xl:inline"
                        style={{ fontSize: "var(--t-meta)" }}
                      >
                        {o.name}
                      </span>
                    )}
                  </td>
                  {/* Muddat toni signal: hammasi amber bo'lsa amber hech narsa anglatmaydi */}
                  <td
                    style={{ fontSize: "var(--t-order)" }}
                    className={cn(
                      "whitespace-nowrap px-3 py-3 font-bold",
                      deadlineTone(o.deadline) === "overdue"
                        ? "bg-red-100 text-red-800"
                        : deadlineTone(o.deadline) === "today"
                          ? "bg-amber-100 text-amber-800"
                          : "text-muted-foreground",
                    )}
                  >
                    {/* Devor ekranida "19.08.2026" hech narsa demaydi — odam
                        boshida sanani bugungi kundan ayirishi kerak bo'lardi.
                        Javobning O'ZI yoziladi, sana ostida dalil bo'lib qoladi. */}
                    <span className="block leading-tight">
                      {deadlineCountdown(o.deadline)}
                    </span>
                    <span
                      className="num block font-semibold tabular-nums opacity-55"
                      style={{ fontSize: "var(--t-badge)" }}
                    >
                      {formatDate(o.deadline)}
                    </span>
                  </td>
                  {(() => {
                    // Qat'iy tartib (STRICT_STAGE_ORDER): ROVER boshlanmasa
                    // STOLYARKA ham boshlanolmaydi. Ya'ni ishlanmagan HAR post
                    // "BOSHLANMADI" deb qichqirsa, bitta fakt uch marta
                    // aytiladi va operator qaysi biri O'ZINIKI ekanini
                    // ajratolmaydi. Faqat BIRINCHISI harakat talab qiladi.
                    const posts = data?.posts ?? []
                    const blocker = posts.find((p) => {
                      const st = o.stages[p.code]
                      return st?.total && st.done < st.total
                    })
                    return posts.map((p) => (
                      <TabloCell
                        key={p.id}
                        stage={o.stages[p.code]}
                        mode={mode}
                        dim={Boolean(contextPostId && p.id !== contextPostId)}
                        deadline={o.deadline}
                        blocker={blocker?.id === p.id}
                      />
                    ))
                  })()}
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
  mode,
  dim,
  deadline,
  blocker = false,
}: {
  stage?: {
    done: number
    total: number
    volume_total: number
    volume_done: number
  }
  mode: Mode
  dim: boolean
  deadline?: string | null
  // Marshrutdagi BIRINCHI tugallanmagan post — harakat aynan shu yerda kerak
  blocker?: boolean
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
      <td
        className="bg-card px-2 py-3 text-center text-muted-foreground shadow-sm"
        style={{ fontSize: "var(--t-cell)" }}
      >
        —
      </td>
    )
  }
  // Chiziq RAQAM bilan bir xil o'lchovda bo'lishi shart. Ilgari u har doim
  // SONI nisbatini ko'rsatardi, HAJM rejimida esa raqam HAJM nisbatini —
  // prodda o'lchandi: ARRA da chiziq 10/63 = 15.9%, raqam 5.7/27.4 = 20.8%.
  // Ya'ni operator ikki xil javob ko'rardi.
  const ratio =
    mode === "hajm" && stage.volume_total > 0
      ? stage.volume_done / stage.volume_total
      : stage.done / stage.total
  const pct = Math.min(100, Math.max(0, ratio * 100))
  const complete = stage.done >= stage.total
  // Qizil FAQAT harakat talab qiladigan joyda: marshrutdagi birinchi
  // tugallanmagan post. Undan keyingilari kutmoqda — bu normal holat, va
  // ularni ham qizil qilish yagona signalni uch marta takrorlab, aynan
  // qayerga borish kerakligini yashirardi.
  const overdue =
    blocker &&
    !complete &&
    deadlineTone(deadline) === "overdue" &&
    stage.done === 0
  // To'siqdan keyingi ishlanmagan postlar — susaytiriladi, qichqirmaydi
  const waiting = !blocker && !complete && stage.done === 0

  let label: string
  // Birlik ustun sarlavhasida, kasr esa devor ekranida shovqin.
  // FOIZ: bu shox faqat TUGALLANMAGAN katakda ko'rinadi (tugallangani ✓
  // chizadi), shuning uchun 99.6% ni 100% ga yaxlitlash mumkin emas —
  // operator kartani bajarilgan deb o'qib, oxirgi detalni tashlab ketardi.
  if (mode === "hajm")
    label = `${Math.round(stage.volume_done)} / ${Math.round(stage.volume_total)}`
  else if (mode === "soni") label = `${stage.done} / ${stage.total}`
  else label = `${Math.min(99, Math.floor((stage.done / stage.total) * 100))}%`

  return (
    <td
      className={cn(
        "relative overflow-hidden rounded-sm px-2 pb-4 pt-3 text-center align-middle",
        complete
          ? "bg-green-100"
          : overdue
            ? "bg-red-50 ring-2 ring-inset ring-red-600"
            : "bg-card shadow-sm",
        flash && "animate-cell-flash",
      )}
    >
      {/* Kontekst rejimida faqat progress to'ldirgichi susayadi — raqam to'liq
          kontrastda qoladi, aks holda 4 metrdan o'qib bo'lmasdi. */}
      {!complete && (
        <span
          // Ilgari bu butun katakni 22% shaffoflikda bo'yardigan "wash" edi —
          // 5 metrdan umuman ko'rinmasdi, ya'ni eng oson o'qiladigan signal
          // (bajarilgan ulush) behuda ketardi. Endi pastda to'yingan rangli
          // rels: raqam bilan raqobatlashmaydi, uzoqdan esa darhol o'qiladi.
          // Rang MA'NO bo'yicha bo'linadi: post rangi USTUN SARLAVHASIDA
          // (kimligi), ma'lumot maydonida esa faqat HOLAT (qizil — to'siq,
          // yashil — tugagan). Rels "qancha" deydi, "qaysi post" emas — buni
          // ustun allaqachon aytgan. Post rangida bo'lsa har qatorda to'qqizta
          // rangli chiziq paydo bo'lib, ranglar ma'nosini yo'qotardi.
          // `transition-all` emas: faqat kenglik o'zgaradi.
          className="absolute bottom-0 left-0 h-2.5 rounded-full bg-primary transition-[width] duration-700"
          style={{ width: `${pct}%`, opacity: dim ? 0.3 : 0.85 }}
        />
      )}
      <span
        style={{ fontSize: "var(--t-cell)" }}
        className={cn(
          "num relative block whitespace-nowrap font-black tabular-nums",
          complete
            ? "text-green-700"
            : overdue
              ? "text-red-700"
              : dim || waiting
                ? "text-muted-foreground"
                : "",
        )}
      >
        {complete ? "✓" : label}
      </span>
      {overdue && (
        <span
          className="relative block whitespace-nowrap font-bold text-red-700"
          style={{ fontSize: "var(--t-badge)" }}
        >
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
    queryFn: async () =>
      (await TabloService.readTabloOrder({ path: { order_id: orderId } })).data,
    refetchInterval: 30_000,
  })
  // Ustunlar matritsa postlaridan (order_index tartibida) — qotirilgan ro'yxat
  // OVAL kabi yangi postni ko'rsatmay qolardi
  const { data: matrix } = useQuery(getTabloMatrixQueryOptions())
  // FAQAT shu buyurtma marshrutidagi postlar. Matritsada to'qqiztasi ham
  // kerak (buyurtmalar har xil), lekin drill — BITTA buyurtma va uning
  // marshruti ma'lum: prodda o'lchandi, 9 ustundan 2 tasi (OVAL, UPAKOVKA)
  // 43 qatorning hammasida bo'sh turardi va yarim ekranni yeb yotardi.
  // Esc — detal ko'rinishidan chiqishning kutilgan yo'li
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onBack()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onBack])

  const parts = data?.parts ?? []
  const drillPosts = (matrix?.posts ?? [])
    .map((p) => p.code)
    // Detallar kelgunicha hammasi turadi: bo'sh ro'yxatdan to'liq ro'yxatga
    // sakrash ustunlarni ko'z oldida siljitardi
    .filter(
      (code) =>
        !parts.length || parts.some((x) => (x.stages[code]?.total ?? 0) > 0),
    )
  return (
    // Shkala BU ildizga ham kerak: drill matritsadan OLDIN qaytadi, ya'ni
    // ichidagi `TabloCell` matritsa ildizini ko'rmaydi. Busiz `var(--t-cell)`
    // aniqlanmay, katak raqami merosdagi 16px ga tushib qolardi.
    <div
      className="flex h-dvh flex-col bg-surface text-foreground"
      style={tabloScale(mode)}
    >
      <header className="flex items-center gap-4 border-b border-border bg-card px-5 py-3 shadow-sm">
        {/* Qaytish havolasi tizimdagi boshqa sahifalar bilan bir xil naqsh:
            ArrowLeft + BORADIGAN JOY nomi, sarlavhadan oldin, chap tepada
            (`orders/$orderId` da "← Buyurtmalar"). Ilgari bu terminal
            naqshi edi — pastki chap burchakda to'ldirilgan "ORQAGA" tugmasi:
            monoblok uchun to'g'ri, devor ekrani uchun esa eng kam qaraladigan
            burchak, va tizimda boshqa hech qayerda uchramaydi. */}
        <button
          type="button"
          onClick={onBack}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-sm font-semibold text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          style={{ fontSize: "var(--t-order)" }}
        >
          <ArrowLeft className="size-6" /> Tablo
        </button>
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
        {/* Matritsadagi bilan bir xil sabab: kenglik mazmunga bog'liq bo'lmasin.
            Prodda o'lchandi — ustunlar 83px dan 175px gacha sakrardi, ya'ni
            "TMO" ustuni "STOLYARKA" dan ikki baravar tor edi. */}
        <table className="w-full table-fixed border-separate border-spacing-2">
          <colgroup>
            <col className="w-[22%]" />
            <col className="w-[8%]" />
            {drillPosts.map((c) => (
              <col
                key={c}
                style={{ width: `${70 / (drillPosts.length || 1)}%` }}
              />
            ))}
          </colgroup>
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
                    mode={mode === "hajm" ? "soni" : mode}
                    dim={false}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  )
}
