import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  BarChart3,
  Boxes,
  ClipboardList,
  Factory,
  Home,
  IdCard,
  Printer,
  ScrollText,
  TriangleAlert,
  Tv,
  UserRound,
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
  isStockOnly,
  isStockStaff,
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
  {
    icon: Home,
    title: "Boshqaruv paneli",
    path: "/",
    show: (u) => !isStockOnly(u),
  },
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
    title: "Ish markazlari",
    path: "/work-centers",
    show: isProductionStaff,
  },
  {
    icon: Boxes,
    title: "Materiallar ombori",
    path: "/stock",
    show: isStockStaff,
  },
  {
    icon: TriangleAlert,
    title: "Brak",
    path: "/defects",
    show: isManagement,
  },
  {
    icon: BarChart3,
    title: "Hisobotlar",
    path: "/reports",
    show: isManagement,
  },
  // TABLO — tsex zalidagi TV ekran. Omborchiga keraksiz: u boshqa
  // binoda, kompyuter oldida ishlaydi
  {
    icon: Tv,
    title: "LIVE Tablo",
    path: "/tablo",
    show: (u) => !isStockOnly(u),
  },
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
        <div className="flex items-center gap-2.5">
          {/* Ochiq rejimda to'liq logo (login ekrani bilan bir xil brend).
              Yig'ilgan rejimda brend butunlay yashiriladi: 48px ustunning
              yagona vazifasi — navigatsiya zichligi, brend esa tab sarlavhasi,
              favicon va login ekranida qoladi. Bosh sahifa havolasi yo'qolmaydi
              — "Boshqaruv paneli" bandi menyuning birinchi qatorida. */}
          <Link
            to="/"
            className="flex min-w-0 items-center group-data-[collapsible=icon]:hidden"
          >
            <img
              src="/assets/logo/logo-gold.png"
              alt="MebeliX — bosh sahifa"
              className="h-9 w-auto"
            />
          </Link>
          <SidebarTrigger className="ml-auto text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:mx-auto" />
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
