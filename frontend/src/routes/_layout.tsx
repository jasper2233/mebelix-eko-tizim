import {
  CatchBoundary,
  createFileRoute,
  type ErrorComponentProps,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"

import { MX_PATH, MX_VIEWBOX } from "@/components/Common/BrandLoader"
import { AppSidebar, NAV_ITEMS } from "@/components/Sidebar/AppSidebar"
import { Button } from "@/components/ui/button"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { requireAuth } from "@/lib/guards"
import { OPERATOR_ROLES } from "@/lib/mes"

// Mobil sarlavhalar sidebar menyusi bilan BITTA manbadan (NAV_ITEMS) —
// "/settings" menyuda yo'q (foydalanuvchi dropdown'ida), alohida qo'shiladi.
const sectionTitles: Record<string, string> = {
  ...Object.fromEntries(NAV_ITEMS.map((i) => [i.path, i.title])),
  "/settings": "Sozlamalar",
}

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    const me = await requireAuth()
    // Qurilma akkauntlari va operatorlar admin panelga kirmaydi — o'z ekraniga (TZ 3.4/3.5)
    if (me.role === "terminal" || OPERATOR_ROLES.includes(me.role))
      throw redirect({ to: "/terminal" })
    if (me.role === "tablo") throw redirect({ to: "/tablo" })
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

  return (
    <SidebarProvider>
      <AppSidebar />
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
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
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
