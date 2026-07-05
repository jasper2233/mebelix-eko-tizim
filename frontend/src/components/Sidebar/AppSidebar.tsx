import { Link } from "@tanstack/react-router"
import { Briefcase, Home, Users } from "lucide-react"

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

const baseItems: Item[] = [
  { icon: Home, title: "Boshqaruv paneli", path: "/" },
  { icon: Briefcase, title: "Elementlar", path: "/items" },
]

export function AppSidebar() {
  const { currentUser } = useCurrentUser()

  const items = currentUser?.is_superuser
    ? [...baseItems, { icon: Users, title: "Foydalanuvchilar", path: "/admin" }]
    : baseItems

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
