import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import type { LucideIcon } from "lucide-react"

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"

export type Item = {
  icon: LucideIcon
  title: string
  path: string
  /** Manzil qidiruv qismi — bitta sahifaning bir nechta ko'rinishi uchun
   *  (mahsulot omborining kategoriyalari). Berilsa, band FAQAT o'sha qidiruv
   *  bilan faol bo'ladi: aks holda uchala kategoriya birdan yonib turardi. */
  search?: Record<string, string>
  /** Ichki band — kichikroq va chekinma bilan chiziladi */
  nested?: boolean
  /** Yonida ko'rinadigan jonli son (0 yoki undefined bo'lsa chiqmaydi) */
  badge?: number
  /** Son nimani sanashi (hover'da) */
  badgeTitle?: string
}

interface MainProps {
  items: Item[]
}

export function Main({ items }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar()
  const currentPath = useRouterState({ select: (s) => s.location.pathname })
  const currentSearch = useRouterState({
    select: (s) => s.location.search as Record<string, unknown>,
  })

  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  return (
    <SidebarGroup>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => {
            // Ichki sahifada ham ota band yonib tursin (/orders/123 -> "Buyurtmalar").
            // Ildiz alohida: aks holda hamma yo'l "/" bilan boshlanib
            // "Boshqaruv paneli" doim faol ko'rinardi.
            const pathMos =
              item.path === "/"
                ? currentPath === "/"
                : currentPath === item.path ||
                  currentPath.startsWith(`${item.path}/`)
            // Qidiruvli band: qiymatlari ham mos kelsa faol. Qidiruvsiz band
            // esa o'z sahifasining HAR qanday ko'rinishida faol qoladi.
            const isActive =
              pathMos &&
              (!item.search ||
                Object.entries(item.search).every(
                  ([k, v]) => currentSearch[k] === v,
                ))

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  tooltip={item.title}
                  isActive={isActive}
                  // Telefonda 48 px (`lg`): 32 px band barmoq uchun kichik —
                  // Apple 44 / Google 48 minimum; desktopda sichqoncha, 32 qoladi
                  size={isMobile ? "lg" : "default"}
                  // Oltin chiziq pseudo-element sifatida: `inset` soya tugmaning
                  // rounded-lg burchaklari ortida qirqilib, deyarli ko'rinmasdi.
                  // Ikonka ham oltinga o'tadi — yig'ilgan railda yagona belgi shu.
                  className={cn(
                    "relative",
                    item.nested && "h-8 pl-7 text-sm",
                    "data-[active=true]:before:absolute data-[active=true]:before:inset-y-1 data-[active=true]:before:left-0 data-[active=true]:before:w-[3px] data-[active=true]:before:rounded-full data-[active=true]:before:bg-sidebar-primary",
                    "data-[active=true]:[&>svg]:text-sidebar-primary",
                  )}
                  asChild
                >
                  <RouterLink
                    to={item.path}
                    search={item.search}
                    onClick={handleMenuClick}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                  </RouterLink>
                </SidebarMenuButton>
                {/* Yashil: badge = amal kutayotgan narsa (topshirishga tayyor
                    buyurtmalar) — hozircha yagona badge, umumlashtirilmagan */}
                {item.badge ? (
                  <SidebarMenuBadge
                    className="rounded-full bg-emerald-500/20 font-bold text-emerald-300"
                    title={item.badgeTitle}
                  >
                    {item.badge}
                  </SidebarMenuBadge>
                ) : null}
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
