import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"

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
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4 md:hidden">
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
          {sectionTitle && <span className="font-medium">{sectionTitle}</span>}
        </header>
        <main className="flex-1 p-6 md:p-8">
          {/* Kenglik chegarasi: busiz 2560px monitorda kontent ~2280px ga
              yoyilib, jadval ustunlari orasi o'qib bo'lmas darajada uzoqlashardi.
              1568px va undan tor ekranlarda hech narsa o'zgarmaydi. */}
          <div className="mx-auto w-full max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
