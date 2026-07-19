import { Link } from "@tanstack/react-router"
import {
  BarChart3,
  ClipboardList,
  Factory,
  HardHat,
  Home,
  Layers,
  ListChecks,
  MonitorPlay,
  Printer,
  ScrollText,
  UserRound,
  Users,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import useCurrentUser from "@/hooks/useCurrentUser"
import { type Item, Main } from "./Main"
import { User } from "./User"

// Rolga qarab navigatsiya (TZ 3.7 rollar-modullar matritsasi)
function navItems(role: string | undefined, isSuperuser: boolean): Item[] {
  const admin = isSuperuser || role === "admin"
  const items: Item[] = [{ icon: Home, title: "Boshqaruv paneli", path: "/" }]

  if (
    admin ||
    role === "manager" ||
    role === "texnolog" ||
    role === "director"
  ) {
    items.push({ icon: ClipboardList, title: "Buyurtmalar", path: "/orders" })
  }
  if (admin || role === "manager" || role === "director") {
    items.push({ icon: UserRound, title: "Mijozlar", path: "/clients" })
  }
  if (admin || role === "manager" || role === "director") {
    items.push({ icon: HardHat, title: "Hodimlar", path: "/employees" })
  }
  if (
    admin ||
    role === "manager" ||
    role === "texnolog" ||
    role === "director"
  ) {
    items.push({ icon: Factory, title: "Stanoklar", path: "/machines" })
    items.push({ icon: Layers, title: "Materiallar", path: "/materials" })
  }
  if (admin || role === "manager" || role === "director") {
    items.push({ icon: BarChart3, title: "Hisobotlar", path: "/reports" })
  }
  items.push({ icon: MonitorPlay, title: "LIVE Tablo", path: "/tablo" })
  if (admin || role === "director") {
    items.push({
      icon: ListChecks,
      title: "Tranzaksiyalar",
      path: "/transactions",
    })
  }
  if (admin) {
    items.push({ icon: Users, title: "Foydalanuvchilar", path: "/admin" })
    items.push({ icon: Printer, title: "Printer agentlar", path: "/printers" })
    items.push({ icon: ScrollText, title: "Logs", path: "/logs" })
  }
  return items
}

export function AppSidebar() {
  const { currentUser } = useCurrentUser()
  const items = navItems(currentUser?.role, Boolean(currentUser?.is_superuser))

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-4 group-data-[collapsible=icon]:px-2">
        <div className="flex items-center gap-2.5 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:gap-3">
          <Link
            to="/"
            className="flex min-w-0 items-center gap-2.5 group-data-[collapsible=icon]:hidden"
          >
            <img
              src="/assets/logo/icon-gold.png"
              alt="MebeliX"
              className="h-8 w-auto shrink-0"
            />
            <span className="text-lg font-bold tracking-tight text-white">
              MebeliX
            </span>
          </Link>
          <SidebarTrigger className="ml-auto text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:ml-0" />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
