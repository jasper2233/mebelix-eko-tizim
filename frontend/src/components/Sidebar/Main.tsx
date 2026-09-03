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
  /** Yonida ko'rinadigan jonli son (0 yoki undefined bo'lsa chiqmaydi) */
  badge?: number
  /** Son nimani sanashi (hover'da) */
  badgeTitle?: string
  /** `success` — yashil (amal kutayotgan narsa: topshirishga tayyor buyurtmalar) */
  badgeTone?: "gold" | "success"
}

interface MainProps {
  items: Item[]
}

export function Main({ items }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar()
  const currentPath = useRouterState({ select: (s) => s.location.pathname })

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
            const isActive =
              item.path === "/"
                ? currentPath === "/"
                : currentPath === item.path ||
                  currentPath.startsWith(`${item.path}/`)

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  tooltip={item.title}
                  isActive={isActive}
                  // Oltin chiziq pseudo-element sifatida: `inset` soya tugmaning
                  // rounded-lg burchaklari ortida qirqilib, deyarli ko'rinmasdi.
                  // Ikonka ham oltinga o'tadi — yig'ilgan railda yagona belgi shu.
                  className={cn(
                    "relative",
                    "data-[active=true]:before:absolute data-[active=true]:before:inset-y-1 data-[active=true]:before:left-0 data-[active=true]:before:w-[3px] data-[active=true]:before:rounded-full data-[active=true]:before:bg-sidebar-primary",
                    "data-[active=true]:[&>svg]:text-sidebar-primary",
                  )}
                  asChild
                >
                  <RouterLink to={item.path} onClick={handleMenuClick}>
                    <item.icon />
                    <span>{item.title}</span>
                  </RouterLink>
                </SidebarMenuButton>
                {item.badge ? (
                  <SidebarMenuBadge
                    className={
                      item.badgeTone === "success"
                        ? "rounded-full bg-emerald-500/20 font-bold text-emerald-300"
                        : "text-sidebar-primary"
                    }
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
