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
  Search,
  SquareStack,
  X,
} from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { BazisModel, BazisPanel } from "./model"
import { hasOpenState, matchPanel } from "./model"
import { createScene, type SceneApi } from "./scene"

/** Holat almashuvi bir necha kadrda — sakrab emas. */
const HOLAT_MS = 460
const EXPLODE_MAX = 0.55

/** Modelning uchta ko'rinish holati. Ular BIR-BIRINI istisno qiladi (ochiq
 * eshikli ajratilgan ko'rinish ma'nosiz), shuning uchun boshqaruv — uchta
 * alohida tugma emas, segmentli tanlov: joriy holat doim ko'rinib turadi va
 * istalganiga BITTA bosishda o'tiladi.
 *
 * «Ochiq» — fayldagi HAQIQIY harakat: bazischi Bazisda ilgak tomonini va
 * ochilish burchagini belgilaydi, MES uni faqat o'ynatadi. Yig'uvchiga aynan
 * shu kerak — eshik qaysi tomonga ochilishi ilgakni qaysi chetga qo'yishni
 * aytadi. «Ajratilgan» esa sun'iy: ichkaridagi, hech qaysi eshik ortida
 * turmagan detallarni ko'rsatadi. */
const HOLATLAR = [
  { kod: "yopiq", nom: "Yopiq", Ikon: DoorClosed },
  { kod: "ochiq", nom: "Ochiq", Ikon: DoorOpen },
  { kod: "ajratilgan", nom: "Ajratilgan", Ikon: SquareStack },
] as const

type Holat = (typeof HOLATLAR)[number]["kod"]

const MAX_NATIJA = 6

const olcham = (p: BazisPanel) => `${p.s[0]} × ${p.s[1]} × ${p.t} mm`

function PanelCard({
  panel,
  mats,
  count,
  onClose,
}: {
  panel: BazisPanel
  mats: string[]
  /** Shu kodli nusxalar soni — bir xil detal ikki eshikka ketishi odatiy hol */
  count: number
  onClose: () => void
}) {
  return (
    <div className="pointer-events-auto rounded-2xl border border-border bg-card p-4 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="font-mono font-semibold text-lg leading-tight">
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
          aria-label="Yopish"
        >
          <X />
        </Button>
      </div>
      <dl className="mt-3 space-y-1.5 text-sm">
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 text-muted-foreground">O'lchami</dt>
          <dd className="font-medium tabular-nums">{olcham(panel)}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-24 shrink-0 text-muted-foreground">Material</dt>
          <dd className="font-medium">{mats[panel.m] || "—"}</dd>
        </div>
      </dl>
    </div>
  )
}

export function ModelViewer({ model }: { model: BazisModel }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const apiRef = useRef<SceneApi | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [query, setQuery] = useState("")
  const [holat, setHolat] = useState<Holat>("yopiq")
  /** Birinchi render: model YIG'ILGAN holatda turibdi, animatsiya kerak emas */
  const birinchi = useRef(true)
  /** Animatsiya qayerdan davom etishini bilish uchun — holat o'rtada almashsa
   * ham sakramasin (ochiq -> ajratilgan). */
  const joriy = useRef({ ochiq: 0, explode: 0 })

  // Ochiladigan detali yo'q modelda «Ochiq» segmenti ko'rsatilmaydi: o'chiq
  // tugma hech qachon yonmasa — u shunchaki shovqin (22 namunadan 2 tasi).
  const segmentlar = useMemo(
    () =>
      hasOpenState(model)
        ? HOLATLAR
        : HOLATLAR.filter((h) => h.kod !== "ochiq"),
    [model],
  )

  useEffect(() => {
    if (!canvasRef.current) return
    const api = createScene(canvasRef.current, (hit) =>
      setSelected(hit ? [hit.index] : []),
    )
    apiRef.current = api
    return () => {
      apiRef.current = null
      api.dispose()
    }
  }, [])

  useEffect(() => {
    apiRef.current?.load(model)
    setSelected([])
    setQuery("")
    setHolat("yopiq")
    joriy.current = { ochiq: 0, explode: 0 }
  }, [model])

  /** Bir xil kodli nusxalar BITTA qatorga yig'iladi: chap va o'ng eshik bir
   * xil detal, ro'yxatda esa ikki marta chiqib xatodek ko'rinardi. */
  const natijalar = useMemo(() => {
    if (!query.trim()) return null
    const guruh = new Map<string, { panel: BazisPanel; indexes: number[] }>()
    model.panels.forEach((panel, index) => {
      if (!matchPanel(panel, query)) return
      const key = `${panel.id}|${panel.n}|${panel.s.join("x")}`
      const bor = guruh.get(key)
      if (bor) bor.indexes.push(index)
      else guruh.set(key, { panel, indexes: [index] })
    })
    return [...guruh.values()]
  }, [model, query])

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

  // Holat almashuvi — bir necha kadrda, sakrab emas
  useEffect(() => {
    const api = apiRef.current
    if (!api) return
    if (birinchi.current) {
      // Busiz sahifa ochilganda model bir lahza OCHIQ chiqib, keyin
      // "yig'ilib" ko'rinardi — hech kim so'ramagan intro.
      birinchi.current = false
      return
    }
    const dan = { ...joriy.current }
    const ga = {
      ochiq: holat === "ochiq" ? 1 : 0,
      explode: holat === "ajratilgan" ? EXPLODE_MAX : 0,
    }
    const bosh = performance.now()
    let frame = 0
    const qadam = () => {
      const t = Math.min(1, (performance.now() - bosh) / HOLAT_MS)
      // easeOutCubic: harakat oxirida sekinlashadi, ko'z kuzatib ulguradi
      const k = 1 - (1 - t) ** 3
      joriy.current = {
        ochiq: dan.ochiq + (ga.ochiq - dan.ochiq) * k,
        explode: dan.explode + (ga.explode - dan.explode) * k,
      }
      api.setPose(joriy.current.ochiq, joriy.current.explode)
      if (t < 1) frame = requestAnimationFrame(qadam)
    }
    qadam()
    return () => cancelAnimationFrame(frame)
  }, [holat])

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

      <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-3">
        <div className="flex items-start justify-end gap-2">
          <div className="pointer-events-auto flex items-center gap-0.5 rounded-full border border-border bg-card/95 p-1 shadow-md">
            {segmentlar.map(({ kod, nom, Ikon }) => {
              const faol = holat === kod
              return (
                <button
                  key={kod}
                  type="button"
                  onClick={() => setHolat(kod)}
                  aria-pressed={faol}
                  className={`flex h-11 items-center gap-1.5 rounded-full px-3 font-medium text-xs transition-colors ${
                    faol
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  }`}
                >
                  <Ikon className="size-4 shrink-0" />
                  {nom}
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

        <div className="mx-auto flex w-full max-w-md flex-col gap-2">
          {selected.length > 0 && (
            <PanelCard
              panel={model.panels[selected[0]]}
              mats={model.mats}
              count={selected.length}
              onClose={() => setSelected([])}
            />
          )}

          {natijalar && natijalar.length > 0 && selected.length === 0 && (
            <div className="pointer-events-auto overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
              {natijalar.slice(0, MAX_NATIJA).map(({ panel, indexes }) => (
                <button
                  type="button"
                  key={`${panel.id}-${indexes[0]}`}
                  onClick={() => {
                    setSelected(indexes)
                    // Ro'yxatdan tanlanganda kamerani olib boramiz: detal
                    // ichkarida bo'lsa "qayerda?" savoli javobsiz qolardi.
                    apiRef.current?.focusOn(indexes[0])
                  }}
                  className="flex w-full items-baseline gap-3 border-border border-b px-4 py-2.5 text-left last:border-0 hover:bg-accent"
                >
                  <span className="font-mono font-medium">
                    {panel.id || "—"}
                  </span>
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

          <div className="pointer-events-auto relative">
            <Search className="-translate-y-1/2 absolute top-1/2 left-3 size-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setSelected([])
              }}
              inputMode="search"
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
