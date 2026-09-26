import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import {
  Activity,
  BarChart3,
  Boxes,
  ClipboardList,
  Factory,
  Gauge,
  Hammer,
  Home,
  IdCard,
  Layers,
  MonitorCog,
  ScrollText,
  SlidersHorizontal,
  TriangleAlert,
  Tv,
  UserRound,
  Wrench,
} from "lucide-react"
import type { UserRead } from "@/client"
import { DefectsService, SystemService } from "@/client"
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
  isManager,
  isProductionStaff,
  isWarehouseOnly,
  isWarehouseStaff,
} from "@/lib/mes"
import { getOrderStatusCountsQueryOptions } from "@/queries/mes"
import { type Item, Main } from "./Main"
import { User } from "./User"

// Rolga qarab navigatsiya (rollar-modullar matritsasi).
// Huquq predikatlari route guard'lari bilan BIR XIL manbadan (lib/mes) —
// menyuda ko'rinib, ochilganda qaytarib yuboradigan sahifa bo'lmasligi uchun.
// _layout.tsx mobil sarlavhalari ham SHU ro'yxatdan olinadi.
//: Katalog harflarining ekrandagi nomi va ikonkasi (`docs/14` §1)
const KATEGORIYA_NOM = { M: "Material", F: "Furnitura", X: "Xizmat" } as const
const KATEGORIYA_IKONKA = { M: Layers, F: Wrench, X: Hammer } as const

export const NAV_ITEMS: (Item & {
  show: (user: UserRead | null | undefined) => boolean
})[] = [
  // Mahsulot omborchisining boshqaruv paneli yo'q: u `_layout` guard'ida
  // to'g'ri omborga yo'naltiriladi, menyuda esa bo'sh havola qolmasin
  {
    icon: Home,
    title: "Boshqaruv paneli",
    path: "/",
    show: (u) => !isWarehouseOnly(u),
  },
  {
    icon: ClipboardList,
    title: "Buyurtmalar",
    path: "/orders",
    show: isProductionStaff,
  },
  {
    icon: Boxes,
    title: "Mahsulotlar ombori",
    path: "/warehouse",
    show: isWarehouseStaff,
  },
  // Katalogning asosiy kategoriyalari — kodning BIRINCHI harfi (`docs/14` §1).
  // Sahifa ichida takrorlanmaydi: ilgari o'sha uchtasi sarlavha ostida tab
  // bo'lib ham turardi — bitta tanlov ikki joyda ikki xil ko'rinishda edi.
  // Ombor sahifasini ochadigan HAR rolga ko'rinadi.
  ...(["M", "F", "X"] as const).map((harf) => ({
    icon: KATEGORIYA_IKONKA[harf],
    title: KATEGORIYA_NOM[harf],
    path: "/warehouse",
    search: { katalog: harf },
    nested: true,
    show: isWarehouseStaff,
  })),
  { icon: UserRound, title: "Mijozlar", path: "/clients", show: isManagement },
  { icon: IdCard, title: "Hodimlar", path: "/employees", show: isManagement },
  {
    icon: Factory,
    title: "Ish markazlari",
    path: "/work-centers",
    show: isProductionStaff,
  },
  {
    icon: TriangleAlert,
    title: "Brak",
    path: "/defects",
    show: isManager,
  },
  {
    icon: BarChart3,
    title: "Hisobotlar",
    path: "/reports",
    show: isManagement,
  },
  // TABLO — tsex zalidagi TV ekran
  {
    icon: Tv,
    title: "LIVE Tablo",
    path: "/tablo",
    show: (u) => !isWarehouseOnly(u),
  },
  // Ikkinchi TV ekran: Pico ulangan stanoklarning jonli holati va bugungi OEE si
  {
    icon: Gauge,
    title: "Stanoklar",
    path: "/tablo/stanoklar",
    // Mahsulot omborchisiga tsex ekranlari kerak emas — uning o'rnida
    // katalog kategoriyalari turadi
    show: (u) => !isWarehouseOnly(u),
  },
  {
    // MonitorCog, Printer emas: agent — tsex KOMPYUTERI (chek printeri +
    // stanok skaneri ko'prigi); Prisadka agenti umuman chek chiqarmaydi.
    icon: MonitorCog,
    title: "MES agentlar",
    path: "/agents",
    show: isAdmin,
  },
  { icon: ScrollText, title: "Loglar", path: "/logs", show: isAdmin },
  // Server tezligi: sekin endpointlar, event loop bloklari, chek kechikishi
  {
    icon: Activity,
    title: "Tizim holati",
    path: "/system-health",
    show: isAdmin,
  },
  {
    icon: SlidersHorizontal,
    title: "Tizim sozlamalari",
    path: "/system-settings",
    show: isAdmin,
  },
]

export function AppSidebar() {
  const { currentUser } = useCurrentUser()
  const items = NAV_ITEMS.filter((i) => i.show(currentUser))

  // Reyestr sahifasi ham shu kalit — /orders da TanStack dedupe qiladi; boshqa sahifalarda
  // sidebar yagona obunachi va 30 s pollni o'zi yuritadi (queries/mes.ts).
  const canSeeOrders = items.some((i) => i.path === "/orders")
  const { data: counts } = useQuery({
    ...getOrderStatusCountsQueryOptions(),
    enabled: canSeeOrders,
  })
  // Badge = TOPSHIRISHGA TAYYOR buyurtmalar (tsex tugatgan, manager topshirishi
  // kerak) — inbox belgisi kabi: amalga undaydi, 0 bo'lsa yo'q. Ilgari «faol
  // buyurtmalar soni» (57) turardi — hech qanday amalga undamasdi va reestrdagi
  // «Hammasi» bilan chalkashardi.
  const ready = counts?.completed ?? 0

  // Brak belgisi: menejer hali ko'rmagan braklar — inbox mantig'i, 0 bo'lsa chiqmaydi
  const canSeeDefects = items.some((i) => i.path === "/defects")
  const { data: defects } = useQuery({
    queryKey: ["defects", "pending-count"],
    queryFn: async () =>
      (await DefectsService.readPendingDefectCount()).data.count,
    refetchInterval: 60_000,
    enabled: canSeeDefects,
  })

  // Tizim holati belgisi: oxirgi 15 daqiqada muammo bo'lsa admin sahifani ochmasdan
  // ko'radi. Hukm backendda (`services/system_health.py`) — sahifa bilan bir manba.
  const canSeeHealth = items.some((i) => i.path === "/system-health")
  const { data: health } = useQuery({
    queryKey: ["system", "status"],
    queryFn: async () => (await SystemService.readSystemStatus()).data,
    refetchInterval: 60_000,
    enabled: canSeeHealth,
  })
  const alarm =
    health && (health.level === "bad" || health.level === "warn")
      ? {
          alert: health.level,
          alertTitle: `Oxirgi ${health.minutes} daqiqa: ${health.findings[0]?.text ?? ""}${
            health.findings.length > 1
              ? ` (yana ${health.findings.length - 1} ta)`
              : ""
          }`,
        }
      : {}

  const withBadges = items.map((i) =>
    i.path === "/orders"
      ? {
          ...i,
          badge: ready,
          badgeTitle: "Topshirishga tayyor — tsex tugatgan buyurtmalar",
        }
      : i.path === "/defects"
        ? {
            ...i,
            badge: defects ?? 0,
            badgeTitle: "Tasdiq kutayotgan brak",
          }
        : i.path === "/system-health"
          ? { ...i, ...alarm }
          : i,
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
