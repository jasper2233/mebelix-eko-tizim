import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  BarChart3,
  ClipboardList,
  Factory,
  History,
  Home,
  IdCard,
  Layers,
  Printer,
  Tv,
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
import { getOrderStatusCountsQueryOptions } from "@/queries/mes"
import { type Item, Main } from "./Main"
import { ShopStatus } from "./ShopStatus"
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
    items.push({ icon: IdCard, title: "Hodimlar", path: "/employees" })
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
  items.push({ icon: Tv, title: "LIVE Tablo", path: "/tablo" })
  if (admin || role === "director") {
    items.push({
      icon: History,
      title: "Tranzaksiyalar",
      path: "/transactions",
    })
  }
  if (admin) {
    items.push({ icon: Users, title: "Foydalanuvchilar", path: "/admin" })
    items.push({ icon: Printer, title: "Printer agentlar", path: "/printers" })
  }
  return items
}

// Terminal holatlar: yakunlangan ish sanoqqa kirmaydi
const TERMINAL_STATUSES = ["delivered", "cancelled"]

export function AppSidebar() {
  const { currentUser } = useCurrentUser()
  const items = navItems(currentUser?.role, Boolean(currentUser?.is_superuser))

  // Reyestr sahifasi ham AYNAN shu kalitni ishlatadi — TanStack dedupe qiladi,
  // ya'ni sidebar qo'shimcha so'rov qo'shmaydi.
  const canSeeOrders = items.some((i) => i.path === "/orders")
  const { data: counts } = useQuery({
    ...getOrderStatusCountsQueryOptions(),
    enabled: canSeeOrders,
  })
  const activeOrders = Object.entries(counts ?? {})
    .filter(([status]) => !TERMINAL_STATUSES.includes(status))
    .reduce((sum, [, n]) => sum + n, 0)

  const withBadges = items.map((i) =>
    i.path === "/orders" ? { ...i, badge: activeOrders } : i,
  )

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-4 group-data-[collapsible=icon]:px-2">
        <div className="flex items-center gap-2.5 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:gap-3">
          {/* Yig'ilgan rejimda faqat YOZUV yashirinadi, belgi qoladi. Avval
              `hidden` butun havolaga qo'yilgani uchun icon rejimida logo ham,
              bosh sahifaga havola ham yo'qolib, panel nomsiz qolardi. */}
          <Link to="/" className="flex min-w-0 items-center gap-2.5">
            <img
              src="/assets/logo/icon-gold.png"
              alt="MebeliX — bosh sahifa"
              className="h-8 w-auto shrink-0"
            />
            <span className="text-lg font-bold tracking-tight text-white group-data-[collapsible=icon]:hidden">
              MebeliX
            </span>
          </Link>
          <SidebarTrigger className="ml-auto text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:ml-0" />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <Main items={withBadges} />
        <ShopStatus />
      </SidebarContent>
      <SidebarFooter>
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
