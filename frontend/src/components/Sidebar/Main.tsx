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
  /** Ogohlantirish belgisi (Tizim holati): son emas — "shu yerda muammo bor" */
  alert?: "warn" | "bad"
  /** Belgi nima haqida (hover'da va ekran o'quvchisiga) */
  alertTitle?: string
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
                    title={item.alertTitle}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                    {item.alert && (
                      <>
                        <span className="sr-only">
                          {" "}
                          —{" "}
                          {item.alert === "bad"
                            ? "muammo bor"
                            : "e'tibor bering"}
                        </span>
                        {/* Yig'ilgan railda badge yashiriladi — ikonka ustidagi nuqta qoladi */}
                        <span
                          aria-hidden
                          className={cn(
                            "absolute top-1 left-6 hidden size-2 rounded-full ring-2 ring-sidebar group-data-[collapsible=icon]:block",
                            item.alert === "bad"
                              ? "bg-red-500"
                              : "bg-amber-400",
                          )}
                        />
                      </>
                    )}
                  </RouterLink>
                </SidebarMenuButton>
                {/* Yashil: badge = amal kutayotgan narsa (topshirishga tayyor
                    buyurtmalar, tasdiq kutayotgan brak) */}
                {item.badge ? (
                  <SidebarMenuBadge
                    className="rounded-full bg-emerald-500/20 font-bold text-emerald-300"
                    title={item.badgeTitle}
                  >
                    {item.badge}
                  </SidebarMenuBadge>
                ) : null}
                {/* Ogohlantirish: qizil/sariq doira va "!" — rang yagona belgi emas,
                    matni `alertTitle` da; ekran o'quvchisi havola ichidagi sr-only ni o'qiydi */}
                {item.alert ? (
                  <SidebarMenuBadge
                    aria-hidden
                    className={cn(
                      "rounded-full font-bold",
                      item.alert === "bad"
                        ? "bg-red-500/25 text-red-200"
                        : "bg-amber-400/25 text-amber-200",
                    )}
                  >
                    !
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
