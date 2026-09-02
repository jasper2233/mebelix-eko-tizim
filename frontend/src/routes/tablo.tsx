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
import { BrandLoader } from "@/components/Common/BrandLoader"
import { useMesWs } from "@/hooks/useMesWs"
import { requireAuth } from "@/lib/guards"
import { deadlineTone, POST_COLORS, PRIORITY_EDGE } from "@/lib/mes"
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
function deadlineCountdown(value?: string | null): [string, string] {
  if (!value) return ["—", ""]
  const target = new Date(value)
  const today = new Date()
  target.setHours(0, 0, 0, 0)
  today.setHours(0, 0, 0, 0)
  const days = Math.round((target.getTime() - today.getTime()) / 86_400_000)
  if (days === 0) return ["BUGUN", ""]
  // Raqam va so'z AJRATILADI: bitta satrda "2 kun kechikdi" tor ustunga
  // sig'masdi va qisqartirilganda "2 kun ke…" bo'lib ma'nosini yo'qotardi.
  // Ikki satrda hech qachon kesilmaydi va ierarxiya ham to'g'ri chiqadi:
  // raqam — ma'lumot, so'z — yorliq.
  return [`${days < 0 ? -days : days} kun`, days < 0 ? "KECHIKDI" : "QOLDI"]
}

/** To'xtash belgisi: `null` — normal, aks holda yozuv.
 *
 * Hisobni server beradi (`idle_days`) va u TSEX ISHLAGAN kunlarni sanaydi:
 * soatlik chegara har kecha butun taxtani yoqardi (smena 18:30-18:40 da
 * tugaydi), kalendar kuni esa dam olishdan keyingi ertalab.
 */
function stallLabel(idle?: number | null): string | null {
  // RAQAMSIZ: qatorda allaqachon "N KUN" bor (muddat ustunida), va ikkinchi
  // kun hisobi qanday yozilmasin muddat deb o'qiladi.
  if (idle == null) return "BOSHLANMAGAN"
  return idle >= 2 ? "QIMIRLAMADI" : null
}

/** Devor ekrani uchun o'lcham shkalasi.
 *
 * Katak shriftini O'QISH istagi emas, USTUN KENGLIGI cheklaydi: jadvaldagi eng
 * uzun yorliq ("1010/1274") ustunga sig'ishi shart, aks holda ikki qatorga
 * o'ralib qator balandligini buzadi. Shu sabab yorliqlardan bo'shliq olib
 * tashlangan (" / " -> "/") — ikki belgi, ya'ni ~18% shrift.
 *
 * Ilgari katak `text-4xl` (36px) qotirilgan edi. PRODDA O'LCHANDI (1745px,
 * HAJM rejimi): `5.7 / 27.4 m²` ustunga sig'may uch qatorga o'ralardi va
 * qator 66px o'rniga 144px bo'lardi — ekranga 9 emas, 4 buyurtma sig'ardi.
 *
 * Shkala IKKALA ildizga beriladi: matritsa ham, detal ro'yxati (drill) ham
 * bir xil `TabloCell` ni ishlatadi, drill esa alohida ildiz qaytaradi.
 */
function tabloScale(): React.CSSProperties {
  return {
    // BITTA o'lcham, rejimdan qat'i nazar: FOIZ da 2.2vw bo'lganda qator
    // 60px dan 85px ga chiqib butun taxta qayta oqardi (o'lchandi). Tugma
    // o'lchov birligini almashtiradi, maketni emas.
    "--t-cell": "clamp(1rem, 1.45vw, 2.6rem)",
    "--t-order": "calc(clamp(1.1rem, 1.7vw, 3rem) * var(--t-fit, 1))",
    "--t-head": "clamp(0.8rem, 1vw, 2rem)",
    "--t-meta": "calc(clamp(0.75rem, 1vw, 1.7rem) * var(--t-fit, 1))",
    "--t-badge": "calc(clamp(0.65rem, 0.8vw, 1.4rem) * var(--t-fit, 1))",
    // Fon FAQAT tabloda quyuqroq — qatorlar ORASIDAGI oraliq 5 metrdan chiziq
    // bo'lib ko'rinishi uchun. O'lchandi: `#f4f6f9` da oq qator bilan kontrast
    // 1.08:1 (ko'rinmaydi), `#dde3eb` da 1.29:1 (zo'rg'a), `#bcc7d5` da 1.71:1.
    // Qator endi yaxlit slab bo'lgani uchun struktura AYNAN shu oraliqlar bilan
    // beriladi — ular ko'rinmasa taxta bitta oq maydonga aylanadi.
    "--surface": "#bcc7d5",
  } as React.CSSProperties
}

/** Ma'lumot yoshi: "12s" / "3d" — devor ekranida raqam qisqa bo'lishi kerak */
function ageLabel(sec: number): string {
  return sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}d`
}

const MODES: Mode[] = ["hajm", "soni", "foiz"]
const MODE_KEY = "tablo-mode"

/** Hamma qator bitta sahifaga sig'sin: sig'masa shrift kichrayadi.
 *
 * Prodda o'lchandi: 6 buyurtmadan keyin qolgani ko'rinmay qolardi, 40 tada
 * jadval ekrandan 7 barobar uzun edi. Ilgari sahifalarga bo'lib aylantirilardi
 * — o'z buyurtmangizni ko'rish uchun navbat kutish kerak edi.
 *
 * Siqish endi faqat KICHIK toshish uchun: `useIdleAutoScroll` katta toshishni
 * aylantirib qoplaydi. 0.62 da 55" TV da buyurtma raqamining bosh harfi 7.9 mm
 * bo'lib ~1.6 m dan o'qilardi — taxta esa 5 m uchun osilgan.
 */
const MIN_FIT = 0.85

function useFitScale<T>(rows: T[]) {
  const bodyRef = useRef<HTMLTableSectionElement>(null)
  const [fit, setFit] = useState(1)

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
      if (trs.length < 2) return setFit(1)
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
      // Qator balandligi shriftga chiziqli bog'liq emas (padding qo'shiladi),
      // shuning uchun joriy `fit` ni hisobga olib nisbatni topamiz va bir qadam
      // qo'yamiz — ResizeObserver keyingi o'lchovda uni aniqlashtiradi.
      const kerak = qator * rows.length
      if (kerak <= 0 || joy <= 0) return
      setFit((oldingi) =>
        Math.min(1, Math.max(MIN_FIT, (oldingi * joy) / kerak)),
      )
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(body)
    ro.observe(scroller)
    return () => ro.disconnect()
  }, [rows.length])

  return { bodyRef, fit }
}

/** Jonlilik ko'rsatkichi — yashil nuqtaning O'ZI yetarli emas.
 *
 * Nuqta soket ochiqligini isbotlaydi, RAQAMLAR yangiligini emas: soket
 * ulangan, lekin hodisa kelmasa va so'rov yiqilsa, ekran eski raqamlarni
 * ko'rsatib turaveradi — nuqta esa xotirjam yashil qolardi. Shuning uchun
 * ma'lumot YOSHI o'lchanadi: normal holatda jonlilikni tepkilayotgan halqa
 * ko'rsatadi, yangilanish yiqilsa (90 s dan oshsa) yosh raqam bo'lib chiqadi.
 *
 * Soat SHU komponent ichida va 15 soniyada uriladi: bo'lmasa har tikda butun
 * matritsa (40 qator x 9 katak) qayta chizilardi.
 */
/** Sig'magan qatorlarni O'ZI aylantiradi — odam tegsa to'xtaydi.
 *
 * Devordagi TV va stol ustidagi PC bitta sahifani ochadi. Ajratish uchun kiosk
 * bayrog'i kerak emas: TV da kiritish qurilmasi yo'q, ya'ni u hech qachon
 * to'xtamaydi, stolda esa birinchi tegishda to'xtaydi. WCAG 2.2 SC 2.2.2 ham
 * o'zi boshlanadigan harakatni to'xtatish yo'lini talab qiladi.
 *
 * Sakrab-turib aylanadi: uzluksiz harakatda ko'z matnni ta'qib qilishga majbur
 * bo'ladi va o'qib bo'lmaydi. Faqat MIN_FIT da ham sig'magan qoldiq uchun.
 */
const DWELL_MS = 9_000
const IDLE_MS = 10_000

function useIdleAutoScroll() {
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    let lastInput = 0
    const bump = () => {
      lastInput = Date.now()
    }
    // `pointermove` ATAYLAB yo'q: o'z aylantirishimiz kursor ostidagi elementni
    // almashtiradi va ba'zi dvijoklarda uni chiqaradi — taxta o'zini o'zi
    // to'xtatib qo'yardi. Bosish, g'ildirak, klavish va teginish haqiqiy
    // niyatni baribir ushlaydi; sichqonchani shunchaki surish esa ushlamaydi.
    const events = ["pointerdown", "keydown", "wheel", "touchstart"] as const
    for (const ev of events)
      window.addEventListener(ev, bump, { passive: true })

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const id = setInterval(() => {
      if (Date.now() - lastInput < IDLE_MS) return
      // Tugun HAR tikda o'qiladi: drill ochilib yopilganda butun matritsa
      // daraxti qayta yaratiladi va effekt boshida ushlangan eski `<main>`
      // uzilib qolardi — taxta boshqa aylanmasdi.
      const el = ref.current
      if (!el) return
      const max = el.scrollHeight - el.clientHeight
      if (max <= 1) return // sig'ib turibdi — qimirlatmaymiz
      // "keyingi qadam oshadi" EMAS, "allaqachon oxirida": birinchisi oxirgi
      // to'liqmas ekranni tashlab ketardi (brauzerda o'lchandi).
      const oxirida = el.scrollTop >= max - 1
      // Qadam 90%: aynan bitta ekran bo'lsa chegaraga to'g'ri kelgan qator
      // har qadamda ham yarim qolardi (40 tadan 8- va 23-, o'lchandi).
      el.scrollTo({
        top: oxirida ? 0 : Math.min(max, el.scrollTop + el.clientHeight * 0.9),
        behavior: reduce ? "auto" : "smooth",
      })
    }, DWELL_MS)

    return () => {
      clearInterval(id)
      for (const ev of events) window.removeEventListener(ev, bump)
    }
    // Bir marta o'rnatiladi: har tikda `scrollHeight`/`clientHeight` DOM dan
    // o'qiladi, ya'ni qatorlar soni yoki ekran o'lchami o'zgarsa o'zi moslashadi.
  }, [])

  return ref
}

function LiveBadge({
  online,
  updatedAt,
}: {
  online: boolean
  updatedAt: number
}) {
  // 15 soniyada, har soniyada emas: bu yerda o'lchanadigan yagona narsa —
  // yangilanish yiqildimi (90 s chegara). 1 s li taymer ekranda to'xtovsiz
  // o'sadigan raqam hosil qilib, sekundomer bo'lib ko'rinardi.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 15_000)
    return () => clearInterval(id)
  }, [])
  const age = updatedAt ? Math.max(0, Math.round((now - updatedAt) / 1000)) : 0
  // So'rov 60 soniyada bir takrorlanadi — 90 dan oshsa yangilanish yiqilgan
  const stale = updatedAt > 0 && age > 90
  // `updatedAt === 0` — so'rov hali BIR MARTA ham muvaffaqiyat bilan
  // tugamagan (sovuq start + API yiqilgan). Busiz WS ulangani yetardi va
  // ekran bo'sh jadval ustida "JONLI" deb turardi.
  const live = online && !stale && updatedAt > 0
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
      {/* Raqam FAQAT nosozlikda: normal holatda jonlilikni tepkilayotgan
          halqa ko'rsatadi, "3d" esa muammo qanchalik eskiligini aytadi. */}
      {!online
        ? "ULANMADI"
        : !updatedAt
          ? "MA'LUMOT YO'Q"
          : stale
            ? `ESKI · ${ageLabel(age)}`
            : "JONLI"}
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
  const { data, isLoading, isError, dataUpdatedAt } = useQuery(
    getTabloMatrixQueryOptions(),
  )
  const fitted = useFitScale(data?.orders ?? [])
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
  // MIN_FIT da ham sig'magan qatorlar uchun: TV o'zi aylantiradi,
  // stolda esa birinchi tegishda to'xtaydi.
  const autoScroll = useIdleAutoScroll()

  if (drill !== null)
    return <TabloOrderDrill orderId={drill} onBack={closeDrill} mode={mode} />

  return (
    <div
      className="flex h-dvh flex-col bg-surface text-foreground"
      // `--t-fit` FAQAT matritsa ildizida: drill ro'yxati alohida ildiz va u
      // sahifaga sig'dirilmaydi (uni odam yaqindan ko'radi, varaqlay oladi).
      style={{ ...tabloScale(), "--t-fit": fitted.fit } as React.CSSProperties}
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
          {MODES.map((m) => (
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

      <main ref={autoScroll} className="min-h-0 flex-1 overflow-auto p-4">
        {isLoading ? (
          <BrandLoader
            size={120}
            className="p-16 text-[#d9b34a]"
            label="Yuklanmoqda"
          />
        ) : isError && !data ? (
          /* Drill ekranidagi bilan bir xil sabab: bo'sh jadval "aktiv
             buyurtma yo'q" degan YOLG'ON aytadi. Devorda hech kim tugma
             bosmaydi — 60 s polling (refetchIntervalInBackground) o'zi qayta
             uradi, shuning uchun matn kutishga chorlaydi. */
          <p className="p-16 text-center text-4xl font-bold text-muted-foreground">
            MA'LUMOT OLINMADI. Ulanish tiklanganda ekran o'zi yangilanadi.
          </p>
        ) : (
          /* `table-fixed` + aniq ulushlar: kenglik MAZMUNGA bog'liq bo'lmasin.
             Ilgari ustunlar mazmunga qarab 87px dan 187px gacha sakrardi.

             Gorizontal oraliq 0: qator yaxlit slab, kataklar uning ichidagi
             zonalar. 8px gorizontal oraliqda taxta foni qator ICHIDAN ko'rinib,
             bitta buyurtma to'qqiz alohida kartochkaga bo'linib ketardi. */
          <table className="w-full table-fixed border-separate border-spacing-x-0 border-spacing-y-2">
            <colgroup>
              <col className="w-[14%]" />
              <col className="w-[13%]" />
              {data?.posts.map((p) => (
                <col
                  key={p.id}
                  style={{ width: `${73 / (data.posts.length || 1)}%` }}
                />
              ))}
            </colgroup>
            <thead>
              <tr
                className="uppercase tracking-wider text-muted-foreground"
                style={{ fontSize: "var(--t-head)" }}
              >
                <th className="sticky top-0 z-10 bg-surface px-2 text-left">
                  Buyurtma
                </th>
                <th className="sticky top-0 z-10 bg-surface px-2 text-left">
                  Muddat
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
            <tbody ref={fitted.bodyRef}>
              {data && data.orders.length > 0 && (
                <tr>
                  <td
                    className="rounded-l-lg bg-primary px-3 py-3 font-black uppercase tracking-wider text-primary-foreground"
                    style={{ fontSize: "var(--t-head)" }}
                  >
                    {/* Nechta buyurtma jamlanganini AYTISH kerak: usiz "363 / 437"
                        qancha ish ustidan olingani noma'lum qoladi, va qatorlar
                        ekranga sig'may kesilganda buni sanab ham bo'lmaydi. */}
                    {/* "buyurtma" so'zi ortiqcha: ustun sarlavhasi allaqachon
                        BUYURTMA deb turibdi va qator o'zi jami ekani ko'rinib
                        turibdi. Devor ekranida har ortiqcha so'z joy yeydi. */}
                    Jami · {data.orders.length}
                  </td>
                  {/* Har post ustuni o'z yakunini beradi, muddat ustuni esa bo'sh
                      turardi. Bu yerda yakun — nechtasi kechikkani: taxtaning
                      butun maqsadi shu savol. Format qatordagi katak bilan bir xil
                      (raqam + so'z), ya'ni ko'z bir xil joydan o'qiydi. */}
                  {(() => {
                    const kech = data.orders.filter(
                      (o) => deadlineTone(o.deadline) === "overdue",
                    ).length
                    const bugun = data.orders.filter(
                      (o) => deadlineTone(o.deadline) === "today",
                    ).length
                    // "7 / KECHIKKAN" qatordagi "2 / KECHIKDI" bilan bir xil
                    // shaklda edi, u yerda esa raqam KUNNI anglatadi — ya'ni
                    // jami ham "7 kun kechikkan" deb o'qilardi. Taxtaning o'z
                    // grammatikasi X/Y: JAMI qatoridagi qolgan hamma katak
                    // shunday, demak "7/19" ikkilanishsiz "19 tadan 7 tasi".
                    const [son, soz] = kech
                      ? [`${kech}/${data.orders.length}`, "KECHIKKAN"]
                      : bugun
                        ? [`${bugun}/${data.orders.length}`, "BUGUN"]
                        : ["", ""]
                    return (
                      <td
                        className={cn(
                          "px-3 py-3 text-center font-black",
                          kech
                            ? "bg-red-600 text-white"
                            : "bg-primary/90 text-primary-foreground",
                        )}
                      >
                        {son ? (
                          <>
                            <span
                              className="num block leading-tight tabular-nums"
                              style={{ fontSize: "var(--t-order)" }}
                            >
                              {son}
                            </span>
                            <span
                              className="block uppercase leading-tight tracking-wider"
                              style={{ fontSize: "var(--t-badge)" }}
                            >
                              {soz}
                            </span>
                          </>
                        ) : (
                          <span style={{ fontSize: "var(--t-head)" }}>—</span>
                        )}
                      </td>
                    )
                  })()}
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
                        ? `${Math.round(vDone)}/${Math.round(vTotal)}`
                        : mode === "soni"
                          ? `${done}/${total}`
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
              {(data?.orders ?? []).map((o) => {
                const stall = stallLabel(o.idle_days)
                return (
                  <tr
                    key={o.id}
                    onClick={() => setDrill(o.id)}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") setDrill(o.id)
                    }}
                    className="cursor-pointer bg-card hover:bg-accent"
                  >
                    {/* MATN ustuni — bu yerda qisqartirish O'RINLI: loyiha nomi
                      ixtiyoriy uzunlikda bo'ladi. Raqam kataklarida esa
                      qisqartirish TAQIQ — kesilgan son yolg'on ma'lumot.

                      Raqam va loyiha nomi USTMA-UST. Yonma-yon turganda ikkalasi
                      bitta satrga sig'masdi (o'lchandi: 261px matn 244px katakda)
                      va `truncate` ham yordam bermasdi — u `<td>` da ishlamaydi,
                      chunki `display: table-cell` da `text-overflow` qo'llanmaydi.
                      Ustma-ust bo'lganda raqam butun kenglikni oladi, nom esa
                      o'z satrida qisqaradi. Muddat katagi ham shu naqshda.
                      Qator raqami (1, 2, 3...) olib tashlandi: qatorning o'rni
                      ko'rinib turibdi, raqam faqat joy egallardi. */}
                    {/* Prioritet qatorning CHAP QIRRASIDA. Ilgari u umuman
                        ko'rinmasdi — taxta unga qarab saralanardi-yu, "nega bu
                        qator birinchi?" savoli javobsiz qolardi. Burchakdagi
                        badge bo'lmaydi: ~10px matn ~1 metrdan o'qiladi, taxta
                        esa 5 metr uchun. Tasma gorizontal joy olmaydi va uzoqdan
                        rang lentasi bo'lib o'qiladi — shoshilinchlar qayerda
                        tugashi bir qarashda ko'rinadi. */}
                    <td
                      className={cn(
                        "rounded-l-md px-3 py-3",
                        // To'rttala prioritet rangi — buyurtma formasi va
                        // reestr bilan bir xil (PRIORITY_EDGE). Tsex talabi:
                        // taxtada faqat shoshilinch emas, hammasi ko'rinsin.
                        PRIORITY_EDGE[o.priority] ?? "border-l-transparent",
                      )}
                      style={{
                        borderLeftWidth: "10px",
                        borderLeftStyle: "solid",
                      }}
                    >
                      {/* Raqam BUTUN satrni oladi. Belgi bilan yonma-yon
                          qo'yilganda "B-2026-036" -> "B-..." bo'lib kesilardi,
                          ya'ni buyurtmaning O'ZINI aniqlab bo'lmasdi. */}
                      <span
                        className="block truncate font-bold leading-tight"
                        style={{ fontSize: "var(--t-order)" }}
                      >
                        {o.number}
                      </span>
                      {/* Belgi loyiha nomi bilan bitta satrda: ikkinchi satr
                          ikkilamchi ma'lumot uchun, va nom qisqarsa ham
                          buyurtma raqami butun qoladi.

                          Slate, qizil EMAS: muddat ustuni qizilni egallagan va
                          "kechikdi" bilan "to'xtagan" boshqa-boshqa faktlar.
                          Muddatsiz buyurtma ham to'xtab qolishi mumkin — prodda
                          shundaysi bor (4301_Komol, 463 skandan keyin jim). */}
                      {/* Teg bo'lsa nom O'RNIGA chiqadi: 1920px da nomga 119-160px
                          kerak, teg bilan yonma-yon 97px qoladi (o'lchandi).
                          Ustunni kengaytirish ham yaramaydi — "1010/1274" post
                          ustuniga sig'may qoladi. */}
                      <span className="flex items-baseline justify-between gap-2 overflow-hidden">
                        {!stall && o.name && (
                          <span
                            className="truncate text-muted-foreground"
                            style={{ fontSize: "var(--t-meta)" }}
                          >
                            {o.name}
                          </span>
                        )}
                        {stall && (
                          <span
                            className="shrink-0 whitespace-nowrap rounded-sm bg-slate-700 px-1.5 py-0.5 font-black uppercase tracking-wider text-white"
                            style={{ fontSize: "var(--t-badge)" }}
                          >
                            {stall}
                          </span>
                        )}
                      </span>
                    </td>
                    {/* Muddat toni signal: hammasi amber bo'lsa amber hech narsa anglatmaydi */}
                    <td
                      className={cn(
                        "px-3 py-3 text-center font-bold",
                        // Pastel tint (#ffe2e2) devordan "teg" bo'lib o'qilardi,
                        // trevoga emas. Kontrasti yaxshi edi (6.85), muammo
                        // ENERGIYADA: 5 metrdan ochiq pushti oq bilan qo'shilib
                        // ketadi. To'yingan blok esa qatorni ushlab qoladi.
                        deadlineTone(o.deadline) === "overdue"
                          ? "bg-red-600 text-white"
                          : deadlineTone(o.deadline) === "today"
                            ? "bg-amber-400 text-amber-950"
                            : "text-muted-foreground",
                      )}
                    >
                      {/* Devor ekranida "19.08.2026" hech narsa demaydi — odam
                        boshida sanani bugungi kundan ayirishi kerak bo'lardi.
                        Shuning uchun javobning O'ZI yoziladi: "3 kun / QOLDI".
                        Xom sana UMUMAN chizilmaydi — devordan uni hech kim
                        ko'chirib olmaydi, aniq sana kerak bo'lsa reestrda bor. */}
                      {(() => {
                        const [son, soz] = deadlineCountdown(o.deadline)
                        return (
                          <>
                            <span
                              className="num block leading-tight tabular-nums"
                              style={{ fontSize: "var(--t-order)" }}
                            >
                              {son}
                            </span>
                            {soz && (
                              <span
                                className="block font-bold uppercase leading-tight tracking-wider"
                                style={{ fontSize: "var(--t-badge)" }}
                              >
                                {soz}
                              </span>
                            )}
                          </>
                        )
                      })()}
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
                      return posts.map((p, i) => (
                        <TabloCell
                          last={i === posts.length - 1}
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
                )
              })}
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
  last = false,
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
  /** Qatordagi OXIRGI katak — slabning o'ng chekkasini yumaloqlaydi. */
  last?: boolean
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
        // Marshrutda YO'Q post. Chiziq raqam bilan bir xil kattalikda bo'lsa,
        // ish YO'QLIGI ish BORLIGI kabi baqiradi — taxtaning asosiy tekstursi
        // bo'sh kataklar bo'lib qoladi (bugun 9 ustundan 3 tasi butunlay bo'sh).
        className="border-l border-border/60 px-2 py-3 text-center text-muted-foreground/50"
        style={{ fontSize: "var(--t-meta)" }}
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
    label = `${Math.round(stage.volume_done)}/${Math.round(stage.volume_total)}`
  else if (mode === "soni") label = `${stage.done}/${stage.total}`
  else label = `${Math.min(99, Math.floor((stage.done / stage.total) * 100))}%`

  return (
    <td
      className={cn(
        // Kartochka EMAS, zona: kartochka — qatorning O'ZI. Ilgari bitta qatorda
        // uch xil grammatika bor edi (buyurtma 10px radius, muddat 0, katak 6px)
        // va oq katak taxta foni bilan atigi 1.29:1 kontrast berardi, ya'ni
        // "kartochka" chegarasi 5 metrdan umuman ko'rinmasdi.
        "relative overflow-hidden whitespace-nowrap border-l border-border/60 px-2 py-3 text-center align-middle",
        last && "rounded-r-md",
        complete
          ? "bg-green-200/70"
          : overdue
            ? "bg-red-100 ring-2 ring-inset ring-red-600"
            : "bg-card",
        flash && "animate-cell-flash",
      )}
    >
      {/* Kontekst rejimida katak butunlay `opacity-40` bo'lmaydi — oq fonda
          kontrast 1.85:1 ga tushib, 4 metrdan o'qib bo'lmasdi. Susayish ikki
          xil: to'ldirgich shaffoflashadi, raqam esa RANG bilan (muted). */}
      {/* BUTUN KATAK to'ladi — "data bar in cell" naqshi (Excel data bars,
          Grafana jadval paneli). Devor ekranida MAYDON eng oson o'qiladigan
          signal: 5 metrdan 12% bilan 18% ni ajratish uchun ingichka chiziq
          yetmaydi, to'ldirilgan yuza esa darhol ko'rinadi.

          Ilgari ham shunday edi va men uni pastki relsga almashtirgan edim —
          xato tashxis: ayb GEOMETRIYADA emas, RANGDA edi. Eski to'ldirish
          post rangining 22% i bo'lgan (och pushti, och yashil) — oq ustida
          deyarli ko'rinmasdi. Endi rang holat rangi (navy), post rangi esa
          ustun sarlavhasida qoladi.

          Alohida chegara chizig'i YO'Q: bo'yalgan va oq joy orasidagi o'tish
          o'zi aniq chegara beradi. Qo'shilgan 4px chiziq esa raqam ustidan
          o'tardi — maketda ko'rindi: "38%" da 8 ni, "52%" da 2 ni, "8 / 47"
          da chiziqchani kesardi. Raqam markazda turgani uchun bu tasodif
          emas, foizning katta oralig'ida sodir bo'lardi.

          Tiniqlik haqiqiy o'lchamdagi maketda 14/18/22/26/32% da tanlandi:
          32% da raqam ostiga qalin band tushadi, 14% da yuza zaif.

          HAMMA katakda emas, faqat ISH KETAYOTGANIDA. Nisbat faqat qisman
          bajarilgan qadamda ma'noga ega: 0% — "boshlanmadi", 100% — "tugadi",
          ikkalasi ham TOIFA, o'lchov emas, va ularni raqamning o'zi (yoki
          yashil ✓) allaqachon aytgan. Har katakda chizilsa, 9 post x 6
          buyurtma = 54 ta bezak bo'lib, hech biri ajralib turmasdi.

          Bundan tashqari 0% da chegara chizig'i katakning CHAP chetida
          qolib, ~3% dek ko'rinardi — ya'ni boshlanmagan ishni boshlangandek
          ko'rsatardi. */}
      {!complete && stage.done > 0 && (
        <span
          className="absolute inset-y-0 left-0 transition-[width] duration-700"
          style={{
            width: `${pct}%`,
            // YASHIL: `--primary` 22% `#d1d7df` berardi, ya'ni kulrang =
            // "o'chirilgan". Tugagan holat yashil, demak to'ldirish o'sha
            // rang sari boradi va to'lganda aynan shunga aylanadi.
            background:
              "color-mix(in srgb, var(--color-green-500) 22%, transparent)",
            opacity: dim ? 0.35 : 1,
          }}
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
  const { data, isLoading, isError } = useQuery({
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
  // Muddat/holat AYNI so'rovdan: `matrix` bu yerda `drillPosts` uchun
  // allaqachon yuklangan va TanStack uni dedupe qiladi, ya'ni kontekst
  // tekin keladi — backendga yangi maydon ham, yangi so'rov ham kerak emas.
  // Buyurtma TMO dan o'tib taxtadan tushgan bo'lsa `row` yo'q: kontekst
  // ko'rinmaydi, qolgan hamma narsa ishlayveradi.
  const row = matrix?.orders.find((o) => o.id === orderId)
  const stall = row ? stallLabel(row.idle_days) : null
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
      style={tabloScale()}
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
        <span className="text-4xl font-black">{data?.number ?? "…"}</span>
        <span className="text-2xl text-muted-foreground">
          {data?.name ?? ""}
        </span>
        {/* Bosilgan qator muddatni ko'rsatib turgan edi, ichkarida esa u
            yo'qolardi — "bu kechikkanmi?" savoli javobsiz qolardi. */}
        {row &&
          (() => {
            const [son, soz] = deadlineCountdown(row.deadline)
            if (son === "—") return null
            return (
              <span
                className={cn(
                  "rounded-sm px-3 py-1 text-2xl font-black uppercase tracking-wider",
                  deadlineTone(row.deadline) === "overdue"
                    ? "bg-red-600 text-white"
                    : deadlineTone(row.deadline) === "today"
                      ? "bg-amber-400 text-amber-950"
                      : "text-muted-foreground",
                )}
              >
                {son} {soz}
              </span>
            )
          })()}
        {stall && (
          <span className="rounded-sm bg-slate-700 px-3 py-1 text-2xl font-black uppercase tracking-wider text-white">
            {stall}
          </span>
        )}
        <span className="ml-auto text-xl font-bold uppercase tracking-widest text-muted-foreground">
          {/* Hujayralar bilan bir xil rejim (hajm drill'da soni'ga tushadi) */}
          {mode === "foiz" ? "Foiz nazorati" : "Soni nazorati"}
        </span>
      </header>
      <main className="min-h-0 flex-1 overflow-auto p-4">
        {/* Matritsadagi bilan bir xil sabab: kenglik mazmunga bog'liq bo'lmasin.
            Prodda o'lchandi — ustunlar 83px dan 175px gacha sakrardi, ya'ni
            "TMO" ustuni "STOLYARKA" dan ikki baravar tor edi. */}
        {/* Matritsa bilan BIR XIL grammatika: qator — yagona slab, gorizontal
            oraliq 0. Aks holda `TabloCell` chizadigan `border-l` 8px bo'shliq
            ichida osilib qolardi va bitta detal to'qqiz alohida kartochkaga
            bo'linib ketardi. */}
        {isLoading ? (
          <BrandLoader
            size={120}
            className="p-16 text-[#d9b34a]"
            label="Yuklanmoqda"
          />
        ) : isError ? (
          /* Devor ekrani: bo'sh sarlavha + bo'sh jadval o'rniga sabab.
             Chiqish yo'li sarlavhadagi "Tablo" havolasi (va Esc) — bu yerga
             ikkinchi tugma qo'shilmaydi. */
          <p className="p-16 text-center text-3xl font-bold text-muted-foreground">
            Buyurtma yuklanmadi. Qaytadan urinib ko'ring yoki «Tablo» ga
            qayting.
          </p>
        ) : (
          <table className="w-full table-fixed border-separate border-spacing-x-0 border-spacing-y-2">
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
              {/* Bosilgan qatordagi post yig'indilari ichkarida yo'qolardi:
                158 detalli buyurtmada "ARRA umuman qanday?" degan savolga
                javob berish uchun orqaga qaytish kerak edi. Matritsadagi
                JAMI qatori bilan bir xil shakl. */}
              {parts.length > 0 && (
                <tr className="bg-card">
                  <td
                    className="rounded-l-md bg-primary px-3 py-3 font-black uppercase tracking-wider text-primary-foreground"
                    style={{ fontSize: "var(--t-head)" }}
                  >
                    Jami · {parts.length} detal
                  </td>
                  <td className="num border-l border-border/60 bg-primary/90 px-2 py-3 text-center text-3xl font-black text-primary-foreground">
                    {parts.reduce((a, p) => a + p.count, 0)}
                  </td>
                  {drillPosts.map((c, i) => {
                    let done = 0
                    let total = 0
                    for (const p of parts) {
                      const st = p.stages[c]
                      if (!st) continue
                      done += st.done
                      total += st.total
                    }
                    return (
                      <td
                        key={c}
                        className={cn(
                          "border-l border-border/60 bg-primary/90 px-2 py-3 text-center font-black text-primary-foreground",
                          i === drillPosts.length - 1 && "rounded-r-md",
                        )}
                        style={{ fontSize: "var(--t-cell)" }}
                      >
                        {/* 99 ga cheklash FAQAT tugallanmagan katakda: JAMI
                          qatorida ✓ chizilmaydi, ya'ni to'liq bajarilgan post
                          "99%" bo'lib qotib qolardi. Matritsadagi JAMI bilan
                          bir xil qoida. */}
                        {!total
                          ? "—"
                          : mode !== "foiz"
                            ? `${done}/${total}`
                            : done >= total
                              ? "100%"
                              : `${Math.min(99, Math.floor((done / total) * 100))}%`}
                      </td>
                    )
                  })}
                </tr>
              )}
              {data?.parts.map((p) => (
                <tr key={p.part_id} className="bg-card">
                  <td className="rounded-l-md px-3 py-3">
                    <b className="num text-3xl">{p.code}</b>{" "}
                    <span className="text-xl text-muted-foreground">
                      {p.name}
                    </span>
                  </td>
                  <td className="num border-l border-border/60 px-2 py-3 text-center text-3xl font-bold">
                    {p.count}
                  </td>
                  {drillPosts.map((c, i) => (
                    <TabloCell
                      key={c}
                      last={i === drillPosts.length - 1}
                      stage={p.stages[c]}
                      mode={mode === "hajm" ? "soni" : mode}
                      dim={false}
                    />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </div>
  )
}
