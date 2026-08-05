import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  BarChart3,
  ClipboardList,
  Factory,
  Home,
  IdCard,
  Layers,
  Printer,
  ScrollText,
  Tv,
  UserRound,
  Users,
} from "lucide-react"
import type { UserRead } from "@/client"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import {
  isAdmin,
  isManagement,
  isProductionStaff,
  isSuperuser,
  TERMINAL_STATUSES,
} from "@/lib/mes"
import { getOrderStatusCountsQueryOptions } from "@/queries/mes"
import { type Item, Main } from "./Main"
import { User } from "./User"

// Rolga qarab navigatsiya (TZ 3.7 rollar-modullar matritsasi).
// Huquq predikatlari route guard'lari bilan BIR XIL manbadan (lib/mes) —
// menyuda ko'rinib, ochilganda qaytarib yuboradigan sahifa bo'lmasligi uchun.
// _layout.tsx mobil sarlavhalari ham SHU ro'yxatdan olinadi.
export const NAV_ITEMS: (Item & {
  show: (user: UserRead | null | undefined) => boolean
})[] = [
  { icon: Home, title: "Boshqaruv paneli", path: "/", show: () => true },
  {
    icon: ClipboardList,
    title: "Buyurtmalar",
    path: "/orders",
    show: isProductionStaff,
  },
  { icon: UserRound, title: "Mijozlar", path: "/clients", show: isManagement },
  { icon: IdCard, title: "Hodimlar", path: "/employees", show: isManagement },
  {
    icon: Factory,
    title: "Stanoklar",
    path: "/machines",
    show: isProductionStaff,
  },
  {
    icon: Layers,
    title: "Materiallar",
    path: "/materials",
    show: isProductionStaff,
  },
  {
    icon: BarChart3,
    title: "Hisobotlar",
    path: "/reports",
    show: isManagement,
  },
  { icon: Tv, title: "LIVE Tablo", path: "/tablo", show: () => true },
  // Foydalanuvchilar ro'yxati barcha telefon raqamlarni ochadi — backend uni
  // faqat superuser'ga beradi, shuning uchun menyu ham shu shartda
  { icon: Users, title: "Foydalanuvchilar", path: "/admin", show: isSuperuser },
  {
    icon: Printer,
    title: "Printer agentlar",
    path: "/printers",
    show: isAdmin,
  },
  { icon: ScrollText, title: "Loglar", path: "/logs", show: isAdmin },
]

export function AppSidebar() {
  const { currentUser } = useCurrentUser()
  const items = NAV_ITEMS.filter((i) => i.show(currentUser))

  // Reyestr sahifasi ham AYNAN shu kalitni ishlatadi — TanStack dedupe qiladi,
  // ya'ni sidebar qo'shimcha so'rov qo'shmaydi.
  const canSeeOrders = items.some((i) => i.path === "/orders")
  const { data: counts } = useQuery({
    ...getOrderStatusCountsQueryOptions(),
    enabled: canSeeOrders,
  })
  const activeOrders = Object.entries(counts ?? {})
    .filter(
      ([status]) => !(TERMINAL_STATUSES as readonly string[]).includes(status),
    )
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
      </SidebarContent>
      <SidebarFooter>
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}
