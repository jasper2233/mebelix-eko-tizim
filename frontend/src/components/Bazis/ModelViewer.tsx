/** 3D ko'ruvchi: sahna + yig'uvchi uchun boshqaruv.
 *
 * Asosiy foydalanuvchi — qo'lida detal ushlab turgan usta, telefon yoki
 * planshet bilan. Shuning uchun uchta amal ekranda doim ochiq turadi:
 * qidirish, ko'rinishni tanlash va ko'rinishni tiklash.
 */

import {
  DoorClosed,
  DoorOpen,
  RotateCcw,
  Ruler,
  Search,
  SquareDashed,
  SquareStack,
  X,
} from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { BazisModel, BazisPanel, Modul, Moslik } from "./model"
import {
  fasadlar,
  harakatBirligi,
  harakatElementlari,
  hasOpenState,
  matchPanel,
  materialKorinishi,
  modulKodi,
  modullar,
} from "./model"
import { createScene, type SceneApi } from "./scene"

/** «Ajratilgan» holatdagi surilish (mahsulot o'lchamiga nisbatan) */
const EXPLODE_MAX = 0.55

/** Modelning to'rtta ko'rinish holati. Ular BIR-BIRINI istisno qiladi (ochiq
 * eshikli ajratilgan ko'rinish ma'nosiz), shuning uchun boshqaruv — alohida
 * tugmalar emas, segmentli tanlov: joriy holat doim ko'rinib turadi va
 * istalganiga BITTA bosishda o'tiladi.
 *
 * «Ochiq» — fayldagi HAQIQIY harakat: bazischi Bazisda ilgak tomonini va
 * ochilish burchagini belgilaydi, MES uni faqat o'ynatadi. Yig'uvchiga aynan
 * shu kerak — eshik qaysi tomonga ochilishi ilgakni qaysi chetga qo'yishni
 * aytadi. «Ichki» — eshik yopiq, fasadlar esa faqat konturi bilan: usta
 * korpus ichini (javon, tortma qutisi, relslar) fasad qayerda turishi bilan
 * BIRGA ko'radi. DetalQR fasadni butunlay o'chiradi — unda eshik qaysi
 * bo'shliqni yopishi yo'qolib ketadi. «Ajratilgan» esa sun'iy: ichkaridagi,
 * hech qaysi eshik ortida turmagan detallarni ko'rsatadi.
 *
 * Holat HAMMA birlikka tegishli; bitta eshikni esa kartochkadan ochib-yopish
 * mumkin — ustaning savoli odatda bitta eshik haqida ("bu qayoqqa ochiladi,
 * ilgak qaysi chetga?"). */
const HOLATLAR = [
  { kod: "yopiq", nom: "Yopiq", Ikon: DoorClosed },
  { kod: "ochiq", nom: "Ochiq", Ikon: DoorOpen },
  { kod: "ichki", nom: "Ichki", Ikon: SquareDashed },
  { kod: "ajratilgan", nom: "Ajratilgan", Ikon: SquareStack },
] as const

type Holat = (typeof HOLATLAR)[number]["kod"]

const MAX_NATIJA = 6

/** «O'lchamlar» tugmasining holati — keyingi ochilishda ham shunday. Xotira
 * yopiq bo'lishi mumkin (maxfiy oyna) — unda shunchaki o'chiq boshlanadi. */
const OLCHAM_KALIT = "mx3d-olcham"
const olchamEsda = () => {
  try {
    return localStorage.getItem(OLCHAM_KALIT) === "1"
  } catch {
    return false
  }
}

/** Kodi, nomi va o'lchami bir xil panellar — BITTA detalning nusxalari (chap
 * va o'ng eshik). Qidiruv ro'yxati ham, 3D da bosish ham shu kalit bilan
 * yig'adi: ilgari bosilganda faqat bittasi yonardi, ro'yxatda esa `×2` turardi. */
const nusxaKaliti = (p: BazisPanel) => `${p.id}|${p.n}|${p.s.join("x")}`

/** Kod tartibi raqam sifatida: `03_002` -> `03_006` -> `03_010`. Ilgari
 * natijalar fayl tartibida chiqardi. */
const kodTartibi = new Intl.Collator("en", { numeric: true })

/** Qalinligi 0 — plita emas, fasad ustidagi shaffof `zamena material` qatlami
 * (460 faylda 41 305 paneldan 3 482 tasi). `× 0 mm` o'lcham emas, xatodek o'qilardi. */
const olcham = (p: BazisPanel) =>
  p.t > 0 ? `${p.s[0]} × ${p.s[1]} × ${p.t} mm` : `${p.s[0]} × ${p.s[1]} mm`

type Guruh = { panel: BazisPanel; indexes: number[]; moslik: Moslik }

const bor = (b: number | null): b is number => b !== null

function PanelCard({
  panel,
  mats,
  modul,
  count,
  ochiq,
  onOchish,
  onClose,
}: {
  panel: BazisPanel
  mats: string[]
  /** Detal turgan shkaf (blok) — mahsulotda bir nechta bo'lsa */
  modul: Modul | undefined
  /** Shu kodli nusxalar soni — bir xil detal ikki eshikka ketishi odatiy hol */
  count: number
  /** Detal (nusxalari bilan) ochiqmi; harakatlanmaydigan detalda `null` */
  ochiq: boolean | null
  onOchish: () => void
  onClose: () => void
}) {
  return (
    <div className="pointer-events-auto rounded-2xl border border-border bg-card p-4 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="num font-semibold text-lg leading-tight">
              {panel.id || "kodsiz detal"}
            </span>
            {count > 1 && (
              <span className="rounded-full bg-secondary px-2 py-0.5 font-medium text-2xs">
                {count} nusxa
              </span>
            )}
          </div>
          <div className="truncate text-muted-foreground text-sm">
            {panel.n}
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Kartochkani yopish"
        >
          <X />
        </Button>
      </div>
      <dl className="mt-3 space-y-1.5 text-sm">
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 text-muted-foreground">O'lchami</dt>
          <dd className="font-medium tabular-nums">{olcham(panel)}</dd>
        </div>
        {/* Qaysi shkafda: usta shkafni o'rnatayotganda detal emas, shkaf
            o'lchami kerak; 3D da qo'shnilari ham shu shkafni ko'rsatadi */}
        {modul && (
          <div className="flex gap-2">
            <dt className="w-24 shrink-0 text-muted-foreground">Moduli</dt>
            <dd className="font-medium tabular-nums">
              №{modul.kod} · {modul.olcham.join(" × ")} mm
            </dd>
          </div>
        )}
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 text-muted-foreground">Material</dt>
          {/* To'liq nomi `title` da — texnologga kerak bo'lsa */}
          <dd className="font-medium" title={mats[panel.m]}>
            {materialKorinishi(mats[panel.m] ?? "") || "—"}
          </dd>
        </div>
      </dl>
      {ochiq !== null && (
        <Button
          variant="secondary"
          className="mt-3 h-11 w-full"
          onClick={onOchish}
        >
          {ochiq ? <DoorClosed /> : <DoorOpen />}
          {ochiq ? "Yopish" : "Ochish"}
        </Button>
      )}
    </div>
  )
}

export function ModelViewer({ model }: { model: BazisModel }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const apiRef = useRef<SceneApi | null>(null)
  /** Sahna bir marta yaratiladi, bosish esa JORIY modelning nusxalarini yig'adi */
  const modelRef = useRef(model)
  /** Kanvas ustidagi pastki qatlam (kartochka yoki natijalar) */
  const ustRef = useRef<HTMLDivElement>(null)
  /** Tanlangan detal o'lchamining yorliqlari — sahna ularni har kadrda O'ZI
   * joylaydi: Reactda har kadr holat yangilash telefonda kadrni yeydi */
  const qatlamRef = useRef<HTMLDivElement>(null)
  /** Boshqaruv qatlami, uning tepa qatori va pastki ustuni — yorliq zonasi uchun */
  const boshqaruvRef = useRef<HTMLDivElement>(null)
  const tepaRef = useRef<HTMLDivElement>(null)
  const pastRef = useRef<HTMLDivElement>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [query, setQuery] = useState("")
  const [holat, setHolat] = useState<Holat>("yopiq")
  const [olchamlar, setOlchamlar] = useState(olchamEsda)
  /** Kartochkadan holatga TESKARI qo'yilgan birliklar: «Yopiq» da ochilgan,
   * «Ochiq» da yopilgan eshiklar. Holat almashsa tozalanadi. */
  const [almashgan, setAlmashgan] = useState<ReadonlySet<number>>(new Set())

  // Model almashsa holat SHU renderda tiklanadi, effektda emas: aks holda
  // `setPose` effekti eski «Ochiq» bilan yangi modelni bir marta ochib yuborardi.
  const [oldingiModel, setOldingiModel] = useState(model)
  if (model !== oldingiModel) {
    setOldingiModel(model)
    setSelected([])
    setQuery("")
    setHolat("yopiq")
    setAlmashgan(new Set())
  }

  // Ochiladigan detali yo'q modelda «Ochiq», fasadi yo'q modelda «Ichki»
  // segmenti ko'rsatilmaydi: hech narsani o'zgartirmaydigan tugma — shovqin
  // (22 namunadan 2 tasi).
  const segmentlar = useMemo(() => {
    const ochiq = hasOpenState(model)
    const ichki = fasadlar(model).size > 0
    return HOLATLAR.filter(
      (h) => (h.kod !== "ochiq" || ochiq) && (h.kod !== "ichki" || ichki),
    )
  }, [model])

  useEffect(() => {
    if (!canvasRef.current) return
    const api = createScene(
      canvasRef.current,
      (hit) => {
        if (!hit) return setSelected([])
        const kalit = nusxaKaliti(hit.panel)
        const nusxalar: number[] = []
        modelRef.current.panels.forEach((p, i) => {
          if (nusxaKaliti(p) === kalit) nusxalar.push(i)
        })
        setSelected(nusxalar)
      },
      qatlamRef.current ?? undefined,
    )
    apiRef.current = api
    // Pastdagi kartochka yoki ro'yxat modelni to'smasin: kadr markazi bo'sh
    // joyga suriladi (`scene.ts: setPastkiBand`).
    const ust = ustRef.current
    const kuzat = new ResizeObserver(() =>
      api.setPastkiBand(ust?.offsetHeight ?? 0),
    )
    if (ust) kuzat.observe(ust)
    // O'lcham yorlig'i tushmaydigan joy — ekrandagi HAQIQIY o'lchamdan: tugmalar
    // qatori va pastki panel (kartochka + qidiruv + chekka). Ilgari faqat
    // kartochka hisobga olinib, yorliq qidiruv maydoni ostida qolardi, chizig'i
    // esa ko'rinib turardi (landshaftda 19 dan 11 tasi).
    const [boshqaruv, tepa, past] = [
      boshqaruvRef.current,
      tepaRef.current,
      pastRef.current,
    ]
    const zona = new ResizeObserver(() => {
      if (!boshqaruv || !tepa || !past) return
      api.setYorliqZona(
        tepa.offsetTop + tepa.offsetHeight + 6,
        boshqaruv.clientHeight - past.offsetTop + 6,
      )
    })
    for (const el of [boshqaruv, tepa, past]) if (el) zona.observe(el)
    return () => {
      kuzat.disconnect()
      zona.disconnect()
      apiRef.current = null
      api.dispose()
    }
  }, [])

  useEffect(() => {
    modelRef.current = model
    apiRef.current?.load(model)
  }, [model])

  const modulXarita = useMemo(() => modullar(model), [model])

  const birliklar = useMemo(
    () => new Set(harakatElementlari(model).map(harakatBirligi).filter(bor)),
    [model],
  )
  const ochiqBirliklar = useMemo(
    () =>
      holat === "ochiq"
        ? new Set([...birliklar].filter((b) => !almashgan.has(b)))
        : almashgan,
    [holat, almashgan, birliklar],
  )

  // Harakatni sahna o'ynatadi (kaskad, `scene.ts: setPose`) — bu yerda faqat
  // maqsad. Birinchi renderda hech narsa o'zgarmaydi: model yopiq yuklanadi.
  useEffect(() => {
    apiRef.current?.setPose(
      ochiqBirliklar,
      holat === "ajratilgan" ? EXPLODE_MAX : 0,
    )
  }, [ochiqBirliklar, holat])

  useEffect(() => {
    apiRef.current?.setIchki(holat === "ichki")
  }, [holat])

  /** Tanlangan detal(lar)ning harakat birliklari. Nusxalar (chap va o'ng
   * eshik) — har xil birlik, kartochka esa ikkalasini BIRGA ochadi. */
  const tanlanganBirliklar = useMemo(
    () => [
      ...new Set(
        selected.map((i) => harakatBirligi(model.panels[i], i)).filter(bor),
      ),
    ],
    [selected, model],
  )
  const tanlanganOchiq = tanlanganBirliklar.length
    ? tanlanganBirliklar.every((b) => ochiqBirliklar.has(b))
    : null
  const tanlanganniOch = () => {
    const ochilsin = !tanlanganOchiq
    setAlmashgan((eski) => {
      const yangi = new Set(eski)
      for (const b of tanlanganBirliklar) {
        if (ochilsin !== (holat === "ochiq")) yangi.add(b)
        else yangi.delete(b)
      }
      return yangi
    })
  }

  /** Bir xil kodli nusxalar BITTA qatorga yig'iladi: chap va o'ng eshik bir
   * xil detal, ro'yxatda esa ikki marta chiqib xatodek ko'rinardi. Kod AYNAN
   * topilsa faqat o'sha ko'rsatiladi — usta "bu detal qayerga?" deb so'raydi,
   * javob bitta joy bo'lishi kerak; aks holda aniqrog'i yuqorida, keyin kod
   * tartibida (kodsizlari oxirida). */
  const natijalar = useMemo(() => {
    if (!query.trim()) return null
    const guruh = new Map<string, Guruh>()
    model.panels.forEach((panel, index) => {
      const moslik = matchPanel(panel, query, model.code)
      if (!moslik) return
      const key = nusxaKaliti(panel)
      const bor = guruh.get(key)
      if (bor) bor.indexes.push(index)
      else guruh.set(key, { panel, indexes: [index], moslik })
    })
    const hammasi = [...guruh.values()].sort(
      (a, b) =>
        b.moslik - a.moslik ||
        Number(!a.panel.id) - Number(!b.panel.id) ||
        kodTartibi.compare(a.panel.id, b.panel.id),
    )
    const aniq = hammasi.filter((g) => g.moslik === 2)
    return aniq.length ? aniq : hammasi
  }, [model, query])

  /** Ro'yxatdan yoki Enter bilan tanlash kamerani detalga OLIB BORADI: detal
   * ichkarida bo'lsa "qayerda?" savoli javobsiz qolardi. 3D da bosilganda
   * esa kamera qimirlamaydi — detal allaqachon ko'z oldida. */
  const tanla = (indexes: number[]) => {
    setSelected(indexes)
    apiRef.current?.focusOn(indexes)
  }

  useEffect(() => {
    apiRef.current?.setOlchamlar(olchamlar)
    try {
      localStorage.setItem(OLCHAM_KALIT, olchamlar ? "1" : "0")
    } catch {
      // eslab qolinmaydi — xolos
    }
  }, [olchamlar])

  useEffect(() => {
    apiRef.current?.setFound(
      new Set(natijalar?.flatMap((r) => r.indexes) ?? []),
    )
  }, [natijalar])

  useEffect(() => {
    apiRef.current?.setSelected(selected)
    // Tanlov yopilganda orbit markazi o'sha detalda qolib ketardi va
    // aylantirish g'alati tuyulardi — mahsulot markaziga qaytaramiz.
    if (!selected.length) apiRef.current?.nishonniQaytar()
  }, [selected])

  return (
    <div
      className="relative min-h-0 flex-1"
      // Studiya foni: markazda yorug', chetga qarab quyuqlashadi. WebGL'da
      // emas, CSS'da — gradient brauzerda tekin chiziladi va kanvas
      // shaffof qolgani uchun mahsulot fonda "o'tirib" ko'rinadi.
      style={{
        background:
          "radial-gradient(115% 85% at 50% 22%, #ffffff 0%, #eef2f7 52%, #dbe3ee 100%)",
      }}
    >
      <canvas ref={canvasRef} className="block h-full w-full touch-none" />
      {/* Kanvas ustida, boshqaruvlar OSTIDA; bosishni o'tkazib yuboradi —
          yorliq ustida bosilsa ham detal tanlanadi. Raqamlar kartochkada ham
          bor, ya'ni ekran o'quvchiga takror kerak emas. */}
      <div
        ref={qatlamRef}
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      />

      <div
        ref={boshqaruvRef}
        className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3"
      >
        <div ref={tepaRef} className="flex items-start justify-end gap-2">
          <div className="pointer-events-auto flex items-center gap-0.5 rounded-full border border-border bg-card/95 p-1 shadow-md">
            {segmentlar.map(({ kod, nom, Ikon }) => {
              const faol = holat === kod
              return (
                <button
                  key={kod}
                  type="button"
                  onClick={() => {
                    setHolat(kod)
                    setAlmashgan(new Set())
                  }}
                  aria-pressed={faol}
                  title={nom}
                  className={`flex h-11 min-w-11 items-center justify-center gap-1.5 rounded-full px-3 font-medium text-xs transition-colors ${
                    faol
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  }`}
                >
                  <Ikon className="size-4 shrink-0" />
                  {/* Tor ekranda faqat JORIY holatning nomi: to'rtta nom
                      qalqib chiqqanda 360 px da qator sig'masdi. Qolganlari
                      ekran o'quvchi va `title` uchun baribir bor. */}
                  <span className={faol ? undefined : "sr-only sm:not-sr-only"}>
                    {nom}
                  </span>
                </button>
              )
            })}
          </div>
          <Button
            variant="secondary"
            size="icon"
            className="pointer-events-auto size-11 shrink-0 shadow-md"
            onClick={() => apiRef.current?.resetView()}
            aria-label="Ko'rinishni tiklash"
            title="Ko'rinishni tiklash"
          >
            <RotateCcw />
          </Button>
        </div>

        <div
          ref={pastRef}
          className="mx-auto flex w-full max-w-md flex-col gap-2"
        >
          {/* Kartochka yoki natijalar — balandligi sahnaga beriladi (`ustRef`) */}
          <div ref={ustRef} className="flex flex-col gap-2 empty:hidden">
            {selected.length > 0 && (
              <PanelCard
                panel={model.panels[selected[0]]}
                mats={model.mats}
                modul={modulXarita.get(
                  modulKodi(model.panels[selected[0]]) ?? "",
                )}
                count={selected.length}
                ochiq={tanlanganOchiq}
                onOchish={tanlanganniOch}
                onClose={() => setSelected([])}
              />
            )}

            {natijalar && natijalar.length > 0 && selected.length === 0 && (
              // Balandlik chegaralangan: telefonda ro'yxat ekranning ~55% ini
              // egallab, topilgan detallarni o'zi yopib qo'yardi.
              <div className="pointer-events-auto max-h-[min(19rem,34dvh)] overflow-y-auto rounded-2xl border border-border bg-card shadow-lg">
                {natijalar.slice(0, MAX_NATIJA).map(({ panel, indexes }, i) => (
                  <button
                    type="button"
                    key={`${panel.id}-${indexes[0]}`}
                    onClick={() => tanla(indexes)}
                    // Birinchi qator ajralib turadi: Enter aynan uni tanlaydi
                    className={`flex w-full items-baseline gap-3 border-border border-b px-4 py-2.5 text-left last:border-0 hover:bg-accent ${
                      i === 0 ? "bg-accent/60" : ""
                    }`}
                  >
                    <span className="num font-medium">{panel.id || "—"}</span>
                    {indexes.length > 1 && (
                      <span className="shrink-0 text-muted-foreground text-2xs">
                        ×{indexes.length}
                      </span>
                    )}
                    <span className="truncate text-muted-foreground text-sm">
                      {panel.n}
                    </span>
                    <span className="ml-auto shrink-0 text-muted-foreground text-2xs tabular-nums">
                      {olcham(panel)}
                    </span>
                  </button>
                ))}
                {natijalar.length > MAX_NATIJA && (
                  <div className="px-4 py-2 text-center text-muted-foreground text-2xs">
                    va yana {natijalar.length - MAX_NATIJA} ta
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <search className="pointer-events-auto min-w-0 flex-1">
              <form
                className="relative"
                onSubmit={(e) => {
                  e.preventDefault()
                  // Enter — birinchi natija: skaner kodni Enter bilan yuboradi,
                  // telefonda esa klaviaturadagi «Qidirish». Klaviatura yopiladi —
                  // aks holda u modelning yarmini to'sib turardi.
                  const birinchi = natijalar?.[0]
                  if (!birinchi) return
                  tanla(birinchi.indexes)
                  e.currentTarget.querySelector("input")?.blur()
                }}
              >
                <Search className="-translate-y-1/2 absolute top-1/2 left-3 size-4 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value)
                    setSelected([])
                  }}
                  onKeyDown={(e) => {
                    if (e.key !== "Escape") return
                    setQuery("")
                    setSelected([])
                  }}
                  inputMode="search"
                  enterKeyHint="search"
                  autoComplete="off"
                  spellCheck={false}
                  aria-label="Detal kodi yoki nomi"
                  placeholder="Detal kodi yoki nomi"
                  className="h-12 rounded-2xl bg-card pr-10 pl-9 shadow-lg"
                />
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery("")}
                    aria-label="Tozalash"
                    className="-translate-y-1/2 absolute top-1/2 right-2 rounded-full p-2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="size-4" />
                  </button>
                )}
              </form>
            </search>
            {/* O'lchamlar — qidiruv YONIDA, bosh barmoq yetadigan joyda. Tepa
              qatorda joy yo'q: 360 px da u to'la. Standart holatda O'CHIQ:
              doim yoqilgan o'lchamlar (DetalQR) telefonda ustma-ust tushadi;
              tanlangan detalning eni va bo'yi esa tugmasiz ham chiziladi. */}
            <Button
              variant={olchamlar ? "default" : "secondary"}
              size="icon"
              className="pointer-events-auto size-12 shrink-0 rounded-2xl shadow-lg"
              onClick={() => setOlchamlar((v) => !v)}
              aria-pressed={olchamlar}
              aria-label="O'lchamlar"
              title="O'lchamlar (mm)"
            >
              <Ruler />
            </Button>
          </div>
          {natijalar?.length === 0 && (
            <div className="pointer-events-auto rounded-xl bg-card/95 px-4 py-2 text-center text-muted-foreground text-sm shadow">
              Bunday detal topilmadi
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
