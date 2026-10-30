import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  ClipboardList,
  CornerDownLeft,
  FileText,
  Package,
  Search,
} from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"

import { UsersService } from "@/client"
import { NAV_ITEMS } from "@/components/Sidebar/AppSidebar"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useDebounced } from "@/hooks/useDebounced"
import { BUX_BOLIMLAR, MOLIYA_BOLIMLAR, SOLIQ_BOLIMLAR } from "@/lib/bolimlar"
import { ORDER_STATUS_LABELS } from "@/lib/mes"
import { QIDIRUV_OCHISH as OCHISH } from "@/lib/qidiruv"
import { cn } from "@/lib/utils"
import { getCatalogAllQueryOptions, getOrdersQueryOptions } from "@/queries/mes"

// Umumiy qidiruv (Ctrl+K / ⌘K): sahifa va bo'limlar, buyurtmalar, ombor tovarlari — bitta oynada.
// ERP sharhlarida eng ko'p shikoyat «kerakli joyni topib bo'lmaydi» (chuqur menyu, ko'p klik);
// eng yuqori baholanganlarida (Business Central «Tell me», Odoo, SAP Fiori) shunday yagona qidiruv bor.
// Ro'yxat rolga qarab: menyuda ko'rinmaydigan sahifa bu yerda ham chiqmaydi (NAV_ITEMS bilan bir manba).

type Natija = {
  key: string
  guruh: string
  title: string
  izoh?: string
  icon: ReactNode
  go: () => void
}

/** Kichik harf, apostrof turlarisiz: «To'lov» = «to`lov» = «tolov» */
const norm = (s: string) => s.toLowerCase().replace(/['‘’`ʻʼ]/g, "")

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState("")
  const [aktiv, setAktiv] = useState(0)
  const navigate = useNavigate()
  const { currentUser } = useCurrentUser()
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    const onOpen = () => setOpen(true)
    window.addEventListener("keydown", onKey)
    window.addEventListener(OCHISH, onOpen)
    return () => {
      window.removeEventListener("keydown", onKey)
      window.removeEventListener(OCHISH, onOpen)
    }
  }, [])

  const { data: modullar } = useQuery({
    queryKey: ["modullar"],
    queryFn: async () => (await UsersService.readUserModullar()).data,
    staleTime: 5 * 60_000,
    enabled: open,
  })
  const items = NAV_ITEMS.filter(
    (i) =>
      i.show(currentUser) &&
      (!i.modul || !modullar || modullar.includes(i.modul)),
  )
  const bor = (path: string) => items.some((i) => i.path === path)
  const buyurtmaBor = bor("/orders")
  const omborBor = items.some((i) => i.path.startsWith("/warehouse"))

  const izla = useDebounced(q.trim(), 250)
  const { data: orders } = useQuery({
    ...getOrdersQueryOptions({ search: izla }),
    enabled: open && buyurtmaBor && izla.length >= 2,
  })
  const { data: katalog } = useQuery({
    ...getCatalogAllQueryOptions(),
    enabled: open && omborBor && izla.length >= 2,
  })

  const natijalar: Natija[] = (() => {
    const t = norm(q.trim())
    const mos = (...s: (string | undefined)[]) =>
      !t || s.some((x) => x && norm(x).includes(t))
    const out: Natija[] = []
    const sahifa = (
      key: string,
      title: string,
      izoh: string | undefined,
      go: () => void,
    ) => {
      if (mos(title, izoh))
        out.push({
          key,
          guruh: "Sahifalar",
          title,
          izoh,
          icon: <FileText className="size-4" />,
          go,
        })
    }
    for (const i of items) {
      if (!i.flat)
        sahifa(`p:${i.path}:${i.title}`, i.title, undefined, () =>
          navigate({ to: i.path }),
        )
      for (const c of i.children ?? [])
        sahifa(`c:${c.path}:${c.title}`, c.title, i.title, () =>
          navigate({ to: c.path, search: c.search }),
        )
    }
    const bolimlar = [
      { path: "/moliya", nom: "Moliya", list: MOLIYA_BOLIMLAR },
      { path: "/soliq", nom: "Soliq", list: SOLIQ_BOLIMLAR },
      { path: "/buxgalteriya", nom: "Buxgalteriya", list: BUX_BOLIMLAR },
    ] as const
    for (const b of bolimlar) {
      if (!bor(b.path)) continue
      for (const x of b.list)
        sahifa(`b:${b.path}:${x.v}`, x.l, b.nom, () =>
          navigate({ to: b.path, search: { b: x.v } as never }),
        )
    }
    if (t.length >= 2) {
      for (const o of (orders?.data ?? []).slice(0, 6))
        out.push({
          key: `o:${o.id}`,
          guruh: "Buyurtmalar",
          title: o.number,
          izoh: [o.client_name, ORDER_STATUS_LABELS[o.status]]
            .filter(Boolean)
            .join(" · "),
          icon: <ClipboardList className="size-4" />,
          go: () =>
            navigate({
              to: "/orders/$orderId",
              params: { orderId: String(o.id) },
            }),
        })
      let n = 0
      for (const r of katalog ?? []) {
        if (n >= 6) break
        if (!mos(r.code, r.name)) continue
        n++
        out.push({
          key: `k:${r.code}`,
          guruh: "Ombor",
          title: r.name,
          izoh: r.code,
          icon: <Package className="size-4" />,
          go: () =>
            navigate({ to: "/warehouse/item/$code", params: { code: r.code } }),
        })
      }
    }
    return out
  })()

  useEffect(() => {
    if (!open) setQ("")
  }, [open])
  useEffect(() => {
    listRef.current
      ?.querySelector(`[data-i="${aktiv}"]`)
      ?.scrollIntoView({ block: "nearest" })
  }, [aktiv])

  const tanla = (n?: Natija) => {
    if (!n) return
    setOpen(false)
    n.go()
  }

  const kutilmoqda = q.trim().length >= 2 && izla !== q.trim()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        showCloseButton={false}
        className="top-[15%] translate-y-0 gap-0 p-0 sm:max-w-xl"
      >
        <DialogTitle className="sr-only">Qidirish</DialogTitle>
        <div className="flex items-center gap-2 border-b px-3">
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <input
            autoFocus
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setAktiv(0)
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault()
                setAktiv((a) => Math.min(a + 1, natijalar.length - 1))
              } else if (e.key === "ArrowUp") {
                e.preventDefault()
                setAktiv((a) => Math.max(a - 1, 0))
              } else if (e.key === "Enter") {
                e.preventDefault()
                tanla(natijalar[aktiv])
              }
            }}
            placeholder="Sahifa, bo'lim, buyurtma raqami yoki tovar…"
            className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="rounded border px-1.5 text-[10px] text-muted-foreground">
            Esc
          </kbd>
        </div>
        <div ref={listRef} className="max-h-[60vh] overflow-y-auto p-1.5">
          {natijalar.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">
              {kutilmoqda
                ? "Qidirilmoqda…"
                : `«${q.trim()}» bo'yicha hech narsa topilmadi`}
            </p>
          )}
          {natijalar.map((n, i) => (
            <div key={n.key}>
              {(i === 0 || natijalar[i - 1].guruh !== n.guruh) && (
                <div className="px-2.5 pt-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  {n.guruh}
                </div>
              )}
              <button
                type="button"
                data-i={i}
                onMouseMove={() => setAktiv(i)}
                onClick={() => tanla(n)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm",
                  i === aktiv && "bg-accent text-accent-foreground",
                )}
              >
                <span className="text-muted-foreground">{n.icon}</span>
                <span className="min-w-0 flex-1 truncate">
                  {n.title}
                  {n.izoh && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {n.izoh}
                    </span>
                  )}
                </span>
                {i === aktiv && (
                  <CornerDownLeft className="size-3.5 text-muted-foreground" />
                )}
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-3 border-t px-3 py-2 text-[11px] text-muted-foreground">
          <span>↑↓ tanlash</span>
          <span>Enter — ochish</span>
          <span>Ctrl+K — ochish / yopish</span>
        </div>
      </DialogContent>
    </Dialog>
  )
}
