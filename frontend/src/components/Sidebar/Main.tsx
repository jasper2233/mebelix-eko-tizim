import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import { ChevronRight, type LucideIcon } from "lucide-react"
import {
  type MouseEvent,
  type ReactNode,
  useEffect,
  useId,
  useState,
} from "react"

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

type Search = Record<string, unknown>

/** Guruh ichidagi band (mahsulot omborining kategoriyalari) */
export type SubItem = {
  icon: LucideIcon
  title: string
  path: string
  /** Havolaning qidiruv qismi (`?katalog=M`) */
  search?: Record<string, string>
  /** Qaysi manzilda faol: bitta sahifaning bir nechta ko'rinishi — ota ham, kategoriyalar
   *  ham `/warehouse`; qidiruvni sahifa qanday o'qisa shunday solishtiriladi */
  match: (search: Search) => boolean
}

export type Item = {
  icon: LucideIcon
  title: string
  path: string
  /** Bo'limlar — ota sahifa ichida bo'lganda ostida ko'rinadi (`NavGroup`) */
  children?: SubItem[]
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

// Oltin chiziq pseudo-element sifatida: `inset` soya tugmaning rounded-lg burchaklari
// ortida qirqilib, deyarli ko'rinmasdi. Ikonka ham oltinga o'tadi — yig'ilgan railda
// yagona belgi shu.
const ACTIVE_BAR =
  "relative data-[active=true]:before:absolute data-[active=true]:before:inset-y-1 data-[active=true]:before:left-0 data-[active=true]:before:w-[3px] data-[active=true]:before:rounded-full data-[active=true]:before:bg-sidebar-primary data-[active=true]:[&>svg]:text-sidebar-primary"

/** Ichki sahifada ham ota band yonib tursin (/orders/123 -> "Buyurtmalar"). Ildiz alohida:
 *  aks holda hamma yo'l "/" bilan boshlanib "Boshqaruv paneli" doim faol ko'rinardi. */
function pathMatches(path: string, current: string): boolean {
  return path === "/"
    ? current === "/"
    : current === path || current.startsWith(`${path}/`)
}

export function Main({ items }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar()
  const currentPath = useRouterState({ select: (s) => s.location.pathname })
  const currentSearch = useRouterState({
    select: (s) => s.location.search as Search,
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
          {items.map((item) =>
            item.children ? (
              <NavGroup
                key={item.title}
                item={item}
                subItems={item.children}
                inside={pathMatches(item.path, currentPath)}
                currentSearch={currentSearch}
                onNavigate={handleMenuClick}
              />
            ) : (
              <SidebarMenuItem key={item.title}>
                <NavLink
                  item={item}
                  isActive={pathMatches(item.path, currentPath)}
                  onNavigate={handleMenuClick}
                />
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
            ),
          )}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

function NavLink({
  item,
  isActive,
  onNavigate,
  trailing,
  expanded,
  controls,
}: {
  item: Item
  isActive: boolean
  /** `preventDefault()` qilinsa sahifaga o'tilmaydi (bo'limli bandni yopish) */
  onNavigate: (e: MouseEvent<HTMLAnchorElement>) => void
  /** Qator oxiridagi belgi (bo'limli bandning strelkasi) */
  trailing?: ReactNode
  /** Bo'limli band: bo'limlar ochiqmi (`aria-expanded`) va ular qaysi ro'yxat */
  expanded?: boolean
  controls?: string
}) {
  const { isMobile } = useSidebar()
  return (
    <SidebarMenuButton
      tooltip={item.title}
      isActive={isActive}
      // Telefonda 48 px (`lg`): 32 px band barmoq uchun kichik —
      // Apple 44 / Google 48 minimum; desktopda sichqoncha, 32 qoladi
      size={isMobile ? "lg" : "default"}
      className={ACTIVE_BAR}
      asChild
    >
      <RouterLink
        to={item.path}
        onClick={onNavigate}
        title={item.alertTitle}
        aria-expanded={expanded}
        aria-controls={controls}
      >
        <item.icon />
        <span>{item.title}</span>
        {item.alert && (
          <>
            <span className="sr-only">
              {" "}
              — {item.alert === "bad" ? "muammo bor" : "e'tibor bering"}
            </span>
            {/* Yig'ilgan railda badge yashiriladi — ikonka ustidagi nuqta qoladi */}
            <span
              aria-hidden
              className={cn(
                "absolute top-1 left-6 hidden size-2 rounded-full ring-2 ring-sidebar group-data-[collapsible=icon]:block",
                item.alert === "bad" ? "bg-red-500" : "bg-amber-400",
              )}
            />
          </>
        )}
        {trailing}
      </RouterLink>
    </SidebarMenuButton>
  )
}

/** Bo'limli band (Mahsulotlar ombori -> Material / Furnitura / Xizmat).
 *
 *  Bitta qoida: YOPIQ bandni bosish — omborni (butun katalogni) ochadi va bo'limlarni
 *  ko'rsatadi; OCHIQ bandni bosish — bo'limlarni yopadi, sahifa o'zgarmaydi (`preventDefault`,
 *  TanStack Link shunda o'tmaydi). Butun katalogga qaytish ham shu: yopib, qayta ochish —
 *  alohida «Hammasi» bandi kerak emas. Ombordan chiqilganda bo'limlar o'zi yopiladi, kirilganda
 *  (boshqa havola bilan ham) o'zi ochiladi — boshqa sahifada menyu qisqa turadi (shadcn
 *  sidebar-07 `defaultOpen={item.isActive}`, Primer NavList). Faol: bo'lim tanlangan bo'lsa —
 *  o'sha; butun katalog yoki bo'limlar yopiq bo'lsa — ota; bir vaqtda bitta. Telefonda ota
 *  bosilganda menyu yopilmaydi (bo'limlar ko'rinsin / yopilgani ko'rinsin), bo'lim bosilganda
 *  yopiladi. Yig'ilgan railda bo'limlar yo'q — ota oddiy havola (48 px ustunda joy yo'q). */
function NavGroup({
  item,
  subItems,
  inside,
  currentSearch,
  onNavigate,
}: {
  item: Item
  subItems: SubItem[]
  inside: boolean
  currentSearch: Search
  onNavigate: () => void
}) {
  const { isMobile, state } = useSidebar()
  const rail = state === "collapsed" && !isMobile
  const [open, setOpen] = useState(inside)
  const listId = useId()
  useEffect(() => {
    setOpen(inside)
  }, [inside])
  const current = inside
    ? subItems.find((sub) => sub.match(currentSearch))
    : undefined

  if (rail) {
    return (
      <SidebarMenuItem>
        <NavLink item={item} isActive={inside} onNavigate={onNavigate} />
      </SidebarMenuItem>
    )
  }

  return (
    <SidebarMenuItem>
      <NavLink
        item={item}
        isActive={inside && (!open || !current)}
        expanded={open}
        controls={open ? listId : undefined}
        onNavigate={(e) => {
          if (open) {
            e.preventDefault()
            setOpen(false)
          } else {
            setOpen(true)
          }
        }}
        trailing={
          <ChevronRight
            aria-hidden
            className={cn(
              "ml-auto transition-transform duration-150 motion-reduce:transition-none",
              open && "rotate-90",
            )}
          />
        }
      />
      {open && (
        <SidebarMenu id={listId} aria-label={item.title} className="mt-1">
          {subItems.map((sub) => (
            <SidebarMenuItem key={sub.title}>
              <SidebarMenuButton
                tooltip={sub.title}
                isActive={sub === current}
                // Ichki band kichikroq va chekinma bilan; telefonda baribir 44 px
                className={cn(
                  ACTIVE_BAR,
                  isMobile ? "h-11 pl-7" : "h-8 pl-7 text-sm",
                )}
                asChild
              >
                <RouterLink
                  to={sub.path}
                  search={sub.search ?? {}}
                  onClick={onNavigate}
                >
                  <sub.icon />
                  <span>{sub.title}</span>
                </RouterLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      )}
    </SidebarMenuItem>
  )
}
