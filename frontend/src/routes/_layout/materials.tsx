import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { useState } from "react"

import { PageHeader } from "@/components/Common/PageHeader"
import { Badge } from "@/components/ui/badge"
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
import { MATERIAL_TYPE_LABELS } from "@/lib/mes"
import { getMaterialsQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/materials")({
  component: MaterialsPage,
  head: () => ({ meta: [{ title: "Materiallar | MebeliX" }] }),
})

function MaterialsPage() {
  const [search, setSearch] = useState("")
  const [type, setType] = useState("")
  const { data, isLoading } = useQuery(
    getMaterialsQueryOptions(
      search,
      (type || undefined) as "sheet" | "band" | "hardware" | undefined,
    ),
  )

  return (
    <div>
      <PageHeader
        title="Materiallar"
        description="Project fayllardan avtomatik to'ldiriladi (TZ 4.5)"
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
        <div className="relative ml-auto w-full max-w-xs">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            placeholder="Nomi yoki kodi"
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
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-24 text-center text-muted-foreground"
                  >
                    Materiallar hali yo'q — birinchi .project fayl yuklanganda
                    avtomatik qo'shiladi.
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
