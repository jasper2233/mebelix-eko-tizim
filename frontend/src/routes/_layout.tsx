import {
  createFileRoute,
  Outlet,
  redirect,
  useRouterState,
} from "@tanstack/react-router"

import { UsersService } from "@/client"
import { Footer } from "@/components/Common/Footer"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

const sectionTitles: Record<string, string> = {
  "/": "Boshqaruv paneli",
  "/items": "Elementlar",
  "/admin": "Admin",
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
          className="pointer-events-none absolute -right-16 -bottom-16 w-[28rem] opacity-[0.05] select-none"
        />
        <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-3 border-b bg-background px-4">
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
          {sectionTitle && (
            <>
              <Separator orientation="vertical" className="!h-4" />
              <span className="font-medium">{sectionTitle}</span>
            </>
          )}
        </header>
        <main className="flex-1 p-6 md:p-8">
          <Outlet />
        </main>
        <Footer />
      </SidebarInset>
    </SidebarProvider>
  )
}

export default Layout
