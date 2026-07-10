import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { useState } from "react"

import { PageHeader } from "@/components/Common/PageHeader"
import { StatusBadge } from "@/components/Common/StatusBadge"
import { AddOrder } from "@/components/Orders/AddOrder"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCurrentUser from "@/hooks/useCurrentUser"
import { formatDate } from "@/lib/mes"
import { getOrdersQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/orders/")({
  component: OrdersPage,
  head: () => ({ meta: [{ title: "Buyurtmalar | MebeliX" }] }),
})

const TABS = [
  { value: "", label: "Hammasi" },
  { value: "draft", label: "Qoralama" },
  { value: "technical_review", label: "Texnologda" },
  { value: "production", label: "Jarayonda" },
  { value: "completed", label: "Tayyor (sexda)" },
  { value: "delivered", label: "Topshirilgan" },
  { value: "cancelled", label: "Bekor qilingan" },
]

function OrdersPage() {
  const [status, setStatus] = useState("")
  const [search, setSearch] = useState("")
  const { data, isLoading } = useQuery(
    getOrdersQueryOptions({ status, search }),
  )
  const { currentUser } = useCurrentUser()
  const canCreate =
    currentUser?.is_superuser ||
    currentUser?.role === "admin" ||
    currentUser?.role === "manager"

  return (
    <div>
      <PageHeader
        title="Buyurtmalar reestri"
        description="Tizimdagi barcha shartnomalar va ishlab chiqarish holati"
        actions={canCreate ? <AddOrder /> : undefined}
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={status} onValueChange={setStatus}>
          <TabsList className="h-9 flex-wrap">
            {TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value} className="text-xs">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative ml-auto w-full max-w-xs">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            placeholder="Raqam, nom yoki mijoz"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Buyurtma</TableHead>
                <TableHead>Kontragent</TableHead>
                <TableHead>Ochilgan</TableHead>
                <TableHead>Muddat</TableHead>
                <TableHead>Holat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.data.length ? (
                data.data.map((o) => (
                  <TableRow key={o.id} className="cursor-pointer">
                    <TableCell>
                      <Link
                        to="/orders/$orderId"
                        params={{ orderId: String(o.id) }}
                        className="block font-semibold text-primary hover:underline"
                      >
                        {o.number}
                        {o.project_name && (
                          <span className="block text-xs font-normal text-muted-foreground">
                            {o.project_name}
                          </span>
                        )}
                      </Link>
                    </TableCell>
                    <TableCell>{o.client_name}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(o.created_at)}
                    </TableCell>
                    <TableCell className="num">
                      {formatDate(o.deadline)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={o.status} />
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-24 text-center text-muted-foreground"
                  >
                    Buyurtmalar topilmadi.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
