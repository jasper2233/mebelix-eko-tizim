/** Yig'uvchiga beriladigan OCHIQ sahifa: `/3d/{token}`.
 *
 * `_layout` dan tashqarida, ya'ni tizimga kirish talab qilinmaydi. Havolani
 * texnolog beradi; uni usta ham, mijoz ham ochadi. Sahifada faqat mahsulot
 * geometriyasi bor — mijoz ma'lumoti, narx va ishlab chiqarish holati YO'Q.
 *
 * Asosiy qurilma — telefon va planshet: ekran balandligi `dvh` bo'yicha
 * to'liq band qilinadi, 3D esa qolgan joyni oladi.
 */

import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ChevronLeft, Link2Off, PackageX, TriangleAlert } from "lucide-react"
import { useMemo, useState } from "react"
import { type PublicProduct, PublicService } from "@/client"
import { ModelViewer } from "@/components/Bazis/ModelViewer"
import {
  type BazisModel,
  gabarit,
  MODEL_VERSIYA,
} from "@/components/Bazis/model"
import { BrandLoader } from "@/components/Common/BrandLoader"
import { Button } from "@/components/ui/button"
import { API_BASE } from "@/utils"

export const Route = createFileRoute("/3d/$token")({
  component: PublicModelPage,
  head: () => ({
    meta: [
      { title: "MebeliX — 3D model" },
      // Havola faqat uni olgan odamda bo'lishi kerak
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
})

const thumbUrl = (token: string, code: string) =>
  `${API_BASE}/api/v1/public/3d/${encodeURIComponent(token)}/${encodeURIComponent(code)}/thumb`

function Bosh({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-3 bg-surface p-6 text-center">
      {children}
    </div>
  )
}

function ProductGrid({
  token,
  products,
  onPick,
}: {
  token: string
  products: PublicProduct[]
  onPick: (code: string) => void
}) {
  return (
    // Kenglik CHEKLANGAN va markazda: buyurtmada odatda 1-3 mahsulot bo'ladi,
    // to'rt ustunli to'liq kenglikdagi to'r esa katta ekranda sahifaning
    // uchdan ikkisini bo'sh qoldirardi.
    <div className="flex-1 overflow-y-auto p-4">
      <div className="mx-auto grid max-w-5xl grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((p) => (
          <button
            type="button"
            key={p.code}
            onClick={() => onPick(p.code)}
            // `flex-col`: qatordagi qo'shni karta izoh bilan balandroq bo'lsa, tugma
            // cho'ziladi va kontenti o'rtaga tushib tepada oq chiziq qolardi
            className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card text-left shadow-sm transition-all hover:border-primary/40 hover:shadow-md active:scale-[0.99]"
          >
            {/* Eskizni Bazisning o'zi chizib qo'ygan — unda mebeldan tashqari
                texnika, tutqich va xona ham bor, ya'ni tanish uchun bizning
                3D ko'rinishimizdan ham ma'lumotliroq. Lekin u OCH CAD renderi:
                oq kartada «xira» bo'lib ko'rinardi, shuning uchun yumshoq
                gradient fon ustiga qo'yiladi — tasvir suratdek o'qiladi. */}
            <div
              // Telefonda pastroq: 4/3 da bitta kartochka ekranning yarmidan
              // ko'pini egallab, ikkinchisi ko'rinmay qolardi — oshxona
              // buyurtmasida 8 ta modul bo'lishi mumkin.
              className="aspect-[3/2] w-full sm:aspect-[4/3]"
              style={{
                background:
                  "radial-gradient(90% 80% at 50% 30%, #ffffff 0%, #eef2f7 70%, #e2e8f0 100%)",
              }}
            >
              <img
                src={thumbUrl(token, p.code)}
                alt=""
                loading="lazy"
                className="h-full w-full object-contain p-2"
              />
            </div>
            <div className="w-full flex-1 border-border border-t p-3">
              <div className="truncate font-medium">{p.name}</div>
              {/* Mahsulot KODI — bir buyurtmada bir xil nomli ikki mahsulot
                  bo'ladi («01 Kuxniya» ikkita), ularni faqat kod ajratadi.
                  Ilgari kartada faqat nom va detal soni bor edi. */}
              <div className="mt-0.5 flex items-baseline gap-1.5 text-muted-foreground text-xs">
                <span className="num">{p.code}</span>
                <span aria-hidden>·</span>
                <span className="tabular-nums">{p.panels} detal</span>
              </div>
              {/* Bog'lanmagan modelda chekdagi to'liq Detal ID ishlamaydi — usta
                  buni qidirib ko'rgandan KEYIN emas, tanlashdan oldin bilsin */}
              {!p.linked && (
                <div className="mt-1.5 flex items-start gap-1.5 text-amber-700 text-xs">
                  <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
                  <span>
                    Chekdagi kod bilan qidirib bo'lmaydi — detal nomi bilan
                    qidiring
                  </span>
                </div>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

function PublicModelPage() {
  const { token } = Route.useParams()
  const [code, setCode] = useState<string | null>(null)

  const order = useQuery({
    queryKey: ["public-3d", token],
    queryFn: async () =>
      (await PublicService.readPublicOrder({ path: { token } })).data,
    retry: false,
  })

  const products = order.data?.products ?? []
  // Bitta mahsulotda tanlash ekrani ortiqcha — darhol modelga kiramiz
  const joriy = code ?? (products.length === 1 ? products[0].code : null)

  const model = useQuery({
    queryKey: ["public-3d", token, joriy],
    enabled: joriy !== null,
    // Ochiq sahifa ichida qayta so'ramaymiz. Texnolog modelni qayta yuklasa
    // havola O'ZGARMAYDI, fayl o'sha manzilda yangilanadi — sahifani yangilash
    // kifoya: javob `Cache-Control: no-cache` bilan keladi (public.py).
    staleTime: Number.POSITIVE_INFINITY,
    queryFn: async () =>
      (
        await PublicService.readPublicModel({
          path: { token, code: joriy as string },
        })
      ).data as unknown as BazisModel,
  })
  // Faqat ochilayotgan modelda — boshqa versiyadagisi baribir chizilmaydi
  const olchami = useMemo(() => {
    const m = model.data
    if (!joriy || m?.v !== MODEL_VERSIYA) return null
    const g = gabarit(m)
    return g.some((v) => v > 0) ? g : null
  }, [model.data, joriy])

  if (order.isPending) {
    return (
      <Bosh>
        <BrandLoader />
      </Bosh>
    )
  }

  if (order.isError || !order.data) {
    return (
      <Bosh>
        <Link2Off className="size-10 text-muted-foreground" />
        <div className="font-semibold text-lg">Havola ishlamaydi</div>
        <p className="max-w-xs text-muted-foreground text-sm">
          Havola yopilgan yoki noto'g'ri ko'chirilgan. Buyurtmani bergan
          texnologdan yangi havola so'rang.
        </p>
      </Bosh>
    )
  }

  if (!products.length) {
    return (
      <Bosh>
        <PackageX className="size-10 text-muted-foreground" />
        <div className="font-semibold text-lg">Model hali yuklanmagan</div>
        <p className="max-w-xs text-muted-foreground text-sm">
          {order.data.number} buyurtmasiga 3D model qo'shilmagan.
        </p>
      </Bosh>
    )
  }

  const tanlangan = products.find((p) => p.code === joriy)
  const nomi = tanlangan?.name

  return (
    <div className="flex h-dvh flex-col bg-surface">
      <header className="flex shrink-0 items-center gap-3 border-border border-b bg-card px-3 py-2.5">
        {joriy && products.length > 1 && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCode(null)}
            aria-label="Orqaga"
          >
            <ChevronLeft />
          </Button>
        )}
        {/* Ro'yxatda sarlavha — BUYURTMA, ostida esa nima qilish kerakligi:
            sahifani birinchi marta ochgan usta yoki mijoz uchun raqamning
            o'zi hech narsa demaydi. Mahsulot ichida ikkisi almashadi —
            sarlavha mahsulot nomi, ostida qaysi buyurtma ekani. */}
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold leading-tight">
            {nomi ?? <span className="tabular-nums">{order.data.number}</span>}
          </div>
          {nomi ? (
            <div className="flex min-w-0 gap-1 text-muted-foreground text-xs">
              {/* Tor ekranda faqat buyurtma raqami qisqaradi: o'lcham o'rtasidan
                  kesilsa («3200 × 4…») noto'g'ri raqam o'qilardi (360 px da) */}
              <span className="truncate tabular-nums">{order.data.number}</span>
              {/* Umumiy o'lcham — BOSMASDAN: usta birinchi so'raydigan savol
                  "qancha joy egallaydi". Modelning o'zida chiziq yo'q — u doim
                  ko'rinib turib, detallarni to'sardi. */}
              {olchami && (
                <span
                  className="shrink-0 whitespace-nowrap tabular-nums"
                  title="Eni × bo'yi × chuqurligi"
                >
                  · {olchami.join(" × ")} mm
                </span>
              )}
            </div>
          ) : (
            <div className="truncate text-muted-foreground text-xs">
              Detalni topish uchun mahsulotni tanlang
            </div>
          )}
        </div>
        {/* TO'LIQ logotip, ikonka emas: sahifani MebeliX xodimi emas, usta
            yoki mijoz ochadi va ular MX belgisini tanimaydi — havolani kim
            bergani NOM bilan aytiladi. Tablo sarlavhasida ham aynan shu
            aktiv oq fonda turadi. HAVOLA EMAS: bosilsa mijoz kirish
            ekraniga tushib qolardi. */}
        <img
          src="/assets/logo/logo-navy.png"
          alt="MebeliX"
          className="h-7 w-auto shrink-0 sm:h-8"
        />
      </header>

      {joriy === null ? (
        <ProductGrid token={token} products={products} onPick={setCode} />
      ) : model.isPending ? (
        <div className="flex flex-1 items-center justify-center">
          <BrandLoader />
        </div>
      ) : model.isError || !model.data ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <PackageX className="size-8 text-muted-foreground" />
          <p className="text-muted-foreground text-sm">
            Model ochilmadi. Sahifani yangilang.
          </p>
        </div>
      ) : model.data.v !== MODEL_VERSIYA ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <PackageX className="size-8 text-muted-foreground" />
          <p className="max-w-xs text-muted-foreground text-sm">
            Bu model eskirgan. Texnolog uni MESga qayta yuklasin.
          </p>
        </div>
      ) : (
        <ModelViewer
          model={model.data}
          bogLanmagan={tanlangan ? !tanlangan.linked : false}
        />
      )}
    </div>
  )
}
