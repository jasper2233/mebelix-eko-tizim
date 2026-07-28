import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { useState } from "react"

import { AddClient } from "@/components/Clients/AddClient"
import { PageHeader } from "@/components/Common/PageHeader"
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
import { useDebounced } from "@/hooks/useDebounced"
import { formatDate } from "@/lib/mes"
import { getClientsQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/clients")({
  component: ClientsPage,
  head: () => ({ meta: [{ title: "Mijozlar | MebeliX" }] }),
})

function ClientsPage() {
  const [search, setSearch] = useState("")
  const debounced = useDebounced(search.trim())
  const { data, isLoading } = useQuery({
    ...getClientsQueryOptions(debounced),
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <PageHeader
        title="Mijozlar"
        description="Buyurtmachilar reestri"
        actions={<AddClient />}
      />
      <div className="mb-4 relative max-w-sm">
        <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
        <Input
          placeholder="Ism yoki telefon bo'yicha qidirish"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-8"
        />
      </div>
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>F.I.Sh / Kompaniya</TableHead>
                <TableHead>Telefon</TableHead>
                <TableHead>Manzil</TableHead>
                <TableHead className="text-right">Buyurtmalar</TableHead>
                <TableHead>Qo'shilgan</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.data.length ? (
                data.data.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">{c.full_name}</TableCell>
                    <TableCell className="num">{c.phone ?? "—"}</TableCell>
                    <TableCell className="max-w-[240px] truncate">
                      {c.address ?? "—"}
                    </TableCell>
                    <TableCell className="num text-right font-semibold">
                      {c.orders_count}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(c.created_at)}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-24 text-center text-muted-foreground"
                  >
                    {debounced
                      ? `"${debounced}" bo'yicha mijoz topilmadi.`
                      : "Hali mijoz yo'q — \"+ Yangi mijoz\" bilan qo'shing."}
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
