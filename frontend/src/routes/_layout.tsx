import { useQueryClient } from "@tanstack/react-query"
import {
  CatchBoundary,
  createFileRoute,
  type ErrorComponentProps,
  Outlet,
  redirect,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router"
import { useEffect } from "react"
import { toast } from "sonner"

import { MX_PATH, MX_VIEWBOX } from "@/components/Common/BrandLoader"
import { CommandPalette } from "@/components/Common/CommandPalette"
import { BuyurtmaKartaOyna } from "@/components/Moliya/BuyurtmaKarta"
import { MxKroyQaytish } from "@/components/Orders/KroyButton"
import { AppSidebar, NAV_ITEMS } from "@/components/Sidebar/AppSidebar"
import { Button } from "@/components/ui/button"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { useIdleLogout } from "@/hooks/useIdleLogout"
import { useMesWs } from "@/hooks/useMesWs"
import { requireAuth } from "@/lib/guards"
import { isKassaOnly, isWarehouseOnly, OPERATOR_ROLES } from "@/lib/mes"

// Mobil sarlavhalar sidebar menyusi bilan BITTA manbadan (NAV_ITEMS) —
// "/settings" menyuda yo'q (foydalanuvchi dropdown'ida), alohida qo'shiladi.
const sectionTitles: Record<string, string> = {
  // Ombor kategoriyalari guruh ICHIDA (`children`) — sarlavha ota bandniki
  ...Object.fromEntries(NAV_ITEMS.map((i) => [i.path, i.title])),
  "/settings": "Sozlamalar",
}

//: Mahsulot omborchisiga ochiq yo'llar — katalog, undan ochiladigan sotuv listi va o'z
//: sozlamalari (parolini o'zi almashtiradi; «Sozlamalar» havolasi hammaga ko'rinadi)
const OMBOR_YOLLARI = ["/warehouse", "/sotuv", "/settings"]

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async ({ location }) => {
    const me = await requireAuth()
    // Qurilma akkauntlari va operatorlar admin panelga kirmaydi — o'z ekraniga
    if (me.role === "terminal" || OPERATOR_ROLES.includes(me.role))
      throw redirect({ to: "/terminal" })
    if (me.role === "tablo") throw redirect({ to: "/tablo" })
    // Mahsulot omborchisining tsex boshqaruv paneli yo'q — u o'z OMBOR panelida
    // boshlaydi (`/warehouse/panel`, 2026-10-18: ilgari nomenklatura ochilardi va
    // omborchi har safar panelni o'zi izlardi). Aks holda kirgan joyi bo'm-bo'sh
    // ekran bo'lardi. Yo'nalish FAQAT uning O'Z sahifalaridan TASHQARIDA: ular ham
    // shu layout ichida, ya'ni shartsiz yo'naltirish cheksiz halqa berardi
    // (`/terminal` va `/tablo` da bunday emas — ular layoutdan tashqarida).
    if (
      isWarehouseOnly(me) &&
      !OMBOR_YOLLARI.some((p) => location.pathname.startsWith(p))
    )
      throw redirect({ to: "/warehouse/panel" })
    // Kassir ham xuddi shunday: uning ekrani faqat kassa (EKO TZ §7)
    if (
      isKassaOnly(me) &&
      !["/kassa", "/settings"].some((p) => location.pathname.startsWith(p))
    )
      throw redirect({ to: "/kassa" })
    // Moliyachining ishi — Moliya; ishlab chiqarish paneli uning uchun bo'sh (faqat menejer/texnolog/direktor)
    if (me.role === "moliyachi" && location.pathname === "/")
      throw redirect({ to: "/moliya", search: { b: "bosh" } })
  },
})

// Qobiq ICHIDAGI chegara: marshrutning o'z `errorComponent`i sidebar+header'ni ham almashtiradi;
// `<Outlet/>` atrofidagi chegara faqat main kontentini almashtiradi, navigatsiya qoladi.
function PageError({ error, reset }: ErrorComponentProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <span className="text-4xl font-bold">Xato</span>
      <p className="text-muted-foreground">
        Sahifani ko'rsatishda xatolik yuz berdi.
      </p>
      {error.message && (
        <p className="max-w-prose text-sm text-muted-foreground/70">
          {error.message}
        </p>
      )}
      <Button onClick={reset}>Qayta urinish</Button>
    </div>
  )
}

function Layout() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  // Reset kaliti — resolvedLocation: `location` navigatsiya boshlanishidayoq almashadi, chegara
  // eski (crash qilgan) match bilan qayta render bo'lib «Xato» yangi sahifada ham qolardi.
  const resolvedPath = useRouterState({
    select: (s) => s.resolvedLocation?.pathname ?? "",
  })
  const sectionTitle = sectionTitles[pathname]

  // Harakatsizlikdan keyin login sahifasiga (chegara — Tizim sozlamalarida)
  useIdleLogout()

  // Mahsulotlar ombori ichida (docs/14 §9): F2 — sotuv, F3 — sexga kirim, F4 — kirim — har ombor sahifasida,
  // shartnoma va tasdiqlangan hujjat ko'rinishida ham (saqlanmagan ish brauzerda turadi)
  const navigateHot = useNavigate()
  useEffect(() => {
    if (!pathname.startsWith("/warehouse")) return
    const onKey = (e: KeyboardEvent) => {
      const turi = ({ F2: "chiqim", F3: "sex", F4: "kirim" } as const)[
        e.key as "F2" | "F3" | "F4"
      ]
      if (!turi) return
      e.preventDefault()
      navigateHot({ to: "/warehouse/doc", search: { turi } })
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [pathname, navigateHot])

  // Jonli xabar (butun admin qobig'i uchun): tsex buyurtmani tugatganda manager
  // qaysi sahifada bo'lmasin toast + «Ochish». Har qanday `order.*` hodisasida
  // buyurtma keshlari (reestr, holat sonlari → sidebar badge) darhol yangilanadi —
  // 30 s pollni kutmasdan. Toast o'tkinchi, badge doimiy — ikkalasi birga.
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  useMesWs((event) => {
    if (!event.type.startsWith("order.")) return
    queryClient.invalidateQueries({ queryKey: ["orders"] })
    if (event.type !== "order.completed") return
    const orderId = String(event.payload.order_id ?? "")
    const number = String(event.payload.order_number ?? "")
    toast.success(`${number} tayyor — topshirishga tayyorlang`, {
      duration: 15_000,
      action: {
        label: "Ochish",
        onClick: () =>
          navigate({ to: "/orders/$orderId", params: { orderId } }),
      },
    })
  })

  return (
    <SidebarProvider>
      <AppSidebar />
      <CommandPalette />
      <BuyurtmaKartaOyna />
      <MxKroyQaytish />
      <SidebarInset>
        {/* Brend suv belgisi — o'ng past burchak. 28-iyulda (29e790b) olib
            tashlangan edi: absolute varianti overflow-hidden o'ram talab qilib
            sticky panellarni o'ldirardi. FIXED bilan o'ram kerak emas: scrollda
            burchakda qoladi, hech narsaga tegmaydi. Kontent (header/main)
            relative — suv belgisi ustidan bo'yaladi; kartalar bg'i uni o'zi
            yopadi, faqat sahifaning nafas joylarida 4.5% da ko'rinadi.
            PNG emas VEKTOR (BrandLoader'dagi potrace-path) — katta o'lchamda o'tkir.
            BLEED — ataylab: belgi sahifadan "tashqariga davom etayotgandek"
            his beradi, to'liq ichida tursa stiker bo'lib qolardi. Kesish
            NUQTASI sozlangan: M qanotlari va markaziy cho'qqi butun, faqat
            oyoq UCHLARI pastdan, X qanoti o'ngdan chiqadi — shtrix o'rtasidan
            kesilmaydi ("singan" o'qilmasin). */}
        <svg
          viewBox={MX_VIEWBOX}
          aria-hidden="true"
          className="pointer-events-none fixed -bottom-18 -right-24 z-0 w-[40rem] text-primary opacity-[0.05] select-none"
        >
          <path d={MX_PATH} fill="currentColor" />
        </svg>
        <header className="relative z-10 flex h-12 shrink-0 items-center gap-2 border-b px-4 md:hidden">
          {/* Telefonda 40 px nishon: `size-7` (28 px) barmoq uchun kichik edi */}
          <SidebarTrigger className="-ml-1 size-10 text-muted-foreground [&_svg]:size-5" />
          {sectionTitle && <span className="font-medium">{sectionTitle}</span>}
        </header>
        <main className="relative z-10 flex-1 p-6 md:p-8">
          {/* Kenglik chegarasi: busiz 2560px monitorda kontent ~2280px ga
              yoyilib, jadval ustunlari orasi o'qib bo'lmas darajada uzoqlashardi.
              1800px tanlangan: 1600 bo'lganda 1920px monitorda menyuni yig'ish
              kontentga BIR PIKSEL ham qo'shmasdi (1920−256−64 = 1600, ya'ni
              ochiq holatda ham chegaraga tegib turardi) — yig'ish faqat bo'sh
              joyni qayta taqsimlardi. 1800 bilan 1920px ekranda yig'ish ~200px
              beradi, 2560px da esa yoyilish baribir to'xtatiladi. */}
          <div className="mx-auto w-full max-w-[1800px]">
            <CatchBoundary
              getResetKey={() => resolvedPath}
              errorComponent={PageError}
            >
              <Outlet />
            </CatchBoundary>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
