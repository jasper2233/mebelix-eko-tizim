import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
import { Badge } from "@/components/ui/badge"
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
import { useDebounced } from "@/hooks/useDebounced"
import { requireAccess } from "@/lib/guards"
import { isProductionStaff, MATERIAL_TYPE_LABELS } from "@/lib/mes"
import { getMaterialsQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/materials")({
  component: MaterialsPage,
  // Sidebar ko'rinishi bilan bir xil rollar to'plami (lib/mes)
  beforeLoad: requireAccess(isProductionStaff),
  head: () => ({ meta: [{ title: "Materiallar | MebeliX" }] }),
})

function MaterialsPage() {
  const [search, setSearch] = useState("")
  const [type, setType] = useState("")
  const debounced = useDebounced(search.trim())
  const { data, isLoading, isError, refetch } = useQuery({
    ...getMaterialsQueryOptions(
      debounced,
      (type || undefined) as "sheet" | "band" | "hardware" | undefined,
    ),
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <PageHeader
        title="Materiallar"
        description="Project fayllardan avtomatik to'ldiriladi"
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={type} onValueChange={setType}>
          <TabsList className="h-9">
            <TabsTrigger value="">Hammasi</TabsTrigger>
            <TabsTrigger value="sheet">List</TabsTrigger>
            <TabsTrigger value="band">Kromka</TabsTrigger>
            <TabsTrigger value="hardware">Furnitura</TabsTrigger>
          </TabsList>
        </Tabs>
        <SearchInput
          className="ml-auto w-full max-w-xs"
          placeholder="Nomi yoki kodi"
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
                <TableHead>Nomi</TableHead>
                <TableHead>Kod</TableHead>
                <TableHead>Turi</TableHead>
                <TableHead className="text-right">Qalinlik</TableHead>
                <TableHead className="text-right">O'lcham</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.data.length ? (
                data.data.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium">{m.name}</TableCell>
                    <TableCell className="num text-muted-foreground">
                      {m.code ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {MATERIAL_TYPE_LABELS[m.type]}
                      </Badge>
                    </TableCell>
                    <TableCell className="num text-right">
                      {m.thickness ? `${m.thickness} mm` : "—"}
                    </TableCell>
                    <TableCell className="num text-right">
                      {m.length && m.width
                        ? `${m.length} × ${m.width}`
                        : m.width
                          ? `eni ${m.width} mm`
                          : "—"}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <EmptyRow colSpan={5}>
                  Materiallar hali yo'q — birinchi .project fayl yuklanganda
                  avtomatik qo'shiladi.
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
