import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"

import { ApiError, UsersService } from "@/client"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { OPERATOR_ROLES } from "@/lib/mes"

const sectionTitles: Record<string, string> = {
  "/": "Boshqaruv paneli",
  "/orders": "Buyurtmalar",
  "/clients": "Mijozlar",
  "/employees": "Hodimlar",
  "/machines": "Stanoklar",
  "/materials": "Materiallar",
  "/transactions": "Tranzaksiyalar",
  "/reports": "Hisobotlar",
  "/admin": "Foydalanuvchilar",
  "/printers": "Printer agentlar",
  "/logs": "Loglar",
  "/settings": "Sozlamalar",
}

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    try {
      const me = await UsersService.readUserMe()
      // Qurilma akkauntlari va operatorlar admin panelga kirmaydi — o'z ekraniga (TZ 3.4/3.5)
      if (me.role === "terminal" || OPERATOR_ROLES.includes(me.role as never))
        throw redirect({ to: "/terminal" })
      if (me.role === "tablo") throw redirect({ to: "/tablo" })
    } catch (err) {
      // Faqat 401 login'ga yo'naltiradi — tarmoq uzilishi/5xx da sessiyani o'ldirmaymiz,
      // xato errorComponent'da ko'rinadi.
      if (err instanceof ApiError && err.status === 401) {
        throw redirect({ to: "/login" })
      }
      throw err
    }
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

export default Layout
