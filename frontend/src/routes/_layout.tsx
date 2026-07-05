import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"

import { UsersService } from "@/client"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

const sectionTitles: Record<string, string> = {
  "/": "Boshqaruv paneli",
  "/items": "Elementlar",
  "/admin": "Foydalanuvchilar",
  "/settings": "Sozlamalar",
}

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    try {
      await UsersService.readUserMe()
    } catch {
      throw redirect({ to: "/login" })
    }
  },
})

function Layout() {
  const pathname = useRouterState().location.pathname
  const sectionTitle = sectionTitles[pathname]

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="relative overflow-hidden">
        <img
          src="/assets/logo/icon-navy.png"
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute -right-20 -bottom-20 w-[36rem] opacity-[0.06] select-none"
        />
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4 md:hidden">
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
          {sectionTitle && <span className="font-medium">{sectionTitle}</span>}
        </header>
        <main className="flex-1 p-6 md:p-8">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

export default Layout
