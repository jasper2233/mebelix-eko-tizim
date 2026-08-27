import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"

import { MX_PATH, MX_VIEWBOX } from "@/components/Common/BrandLoader"
import { AppSidebar, NAV_ITEMS } from "@/components/Sidebar/AppSidebar"
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
    if (me.role === "terminal" || OPERATOR_ROLES.includes(me.role as never))
      throw redirect({ to: "/terminal" })
    if (me.role === "tablo") throw redirect({ to: "/tablo" })
  },
})

function Layout() {
  const pathname = useRouterState().location.pathname
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
            TO'LIQ ko'rinadi (qirqilmaydi): MX oyoqlari uchli — o'rtasidan
            kesilsa "singan" bo'lib o'qilardi. */}
        <svg
          viewBox={MX_VIEWBOX}
          aria-hidden="true"
          className="pointer-events-none fixed bottom-6 right-8 z-0 w-[26rem] text-primary opacity-[0.05] select-none"
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
            <Outlet />
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
