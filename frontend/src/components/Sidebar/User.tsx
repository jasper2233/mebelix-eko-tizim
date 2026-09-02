import { Link as RouterLink } from "@tanstack/react-router"
import { ChevronsUpDown, LogOut, Settings } from "lucide-react"
import type { UserRead } from "@/client"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { useAuth } from "@/hooks/useAuth"
import { getInitials } from "@/utils"

interface UserInfoProps {
  fullName?: string | null
  phone?: string | null
}

function UserInfo({ fullName, phone }: UserInfoProps) {
  return (
    <div className="flex w-full min-w-0 items-center gap-2.5">
      <Avatar className="size-8 shrink-0">
        <AvatarFallback className="bg-sidebar-primary font-semibold text-sidebar-primary-foreground">
          {getInitials(fullName || "Foydalanuvchi")}
        </AvatarFallback>
      </Avatar>
      {/* Yig'ilgan rejimda tugma 32px ga qisqaradi — matn ustuni yashirilmasa
          avatar o'sha qutidan toshib chiqib, `ml-auto` chevron uning ustiga
          tushardi. Portal ichidagi dropdown nusxasiga bu qoida tegmaydi
          (sidebar `group`i ajdod emas), ya'ni menyuda ism ko'rinaveradi. */}
      <div className="flex min-w-0 flex-col items-start group-data-[collapsible=icon]:hidden">
        <p className="w-full truncate text-sm font-medium">{fullName}</p>
        <p className="w-full truncate text-xs opacity-70">{phone}</p>
      </div>
    </div>
  )
}

export function User({ user }: { user?: UserRead | null }) {
  const { logout } = useAuth()
  const { isMobile, setOpenMobile } = useSidebar()

  if (!user) return null

  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <UserInfo fullName={user.name} phone={user.phone} />
              <ChevronsUpDown className="ml-auto size-4 opacity-70 group-data-[collapsible=icon]:hidden" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <UserInfo fullName={user.name} phone={user.phone} />
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {/* `asChild` — Radix `role="menuitem"` va roving-focus proplarini
                anchor'ning o'ziga qo'yadi; teskari joylashuvda `role="menu"`
                ichida rolsiz `<a>` qolib, klaviatura navigatsiyasi buzilardi. */}
            <DropdownMenuItem asChild>
              <RouterLink to="/settings" onClick={handleMenuClick}>
                <Settings />
                Sozlamalar
              </RouterLink>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={logout}>
              <LogOut />
              Chiqish
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
