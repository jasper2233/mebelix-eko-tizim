import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { AddClient } from "@/components/Clients/AddClient"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
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
import { requireAccess } from "@/lib/guards"
import { formatDate, isManagement } from "@/lib/mes"
import { getClientsQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/clients")({
  component: ClientsPage,
  // Sidebar ko'rinishi bilan bir xil rollar to'plami (lib/mes)
  beforeLoad: requireAccess(isManagement),
  head: () => ({ meta: [{ title: "Mijozlar | MebeliX" }] }),
})

function ClientsPage() {
  const [search, setSearch] = useState("")
  const debounced = useDebounced(search.trim())
  const { data, isLoading, isError, refetch } = useQuery({
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
      <div className="mb-4 flex">
        <SearchInput
          className="ml-auto w-full max-w-xs"
          placeholder="Ism yoki telefon bo'yicha qidirish"
          value={search}
          onChange={setSearch}
        />
      </div>
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
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
                    <TableCell
                      className="max-w-[220px] truncate font-medium"
                      title={c.full_name}
                    >
                      {c.full_name}
                    </TableCell>
                    <TableCell className="num">{c.phone ?? "—"}</TableCell>
                    <TableCell className="max-w-[240px] truncate">
                      {c.address ?? "—"}
                    </TableCell>
                    <TableCell className="num text-right font-semibold">
                      {c.orders_count}
                    </TableCell>
                    <TableCell className="num text-muted-foreground">
                      {formatDate(c.created_at)}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <EmptyRow colSpan={5}>
                  {debounced
                    ? `"${debounced}" bo'yicha mijoz topilmadi.`
                    : "Hali mijoz yo'q — \"+ Yangi mijoz\" bilan qo'shing."}
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
