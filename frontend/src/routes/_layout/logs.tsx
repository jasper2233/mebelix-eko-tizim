import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { PageHeader } from "@/components/Common/PageHeader"
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
import { formatDateTime } from "@/lib/mes"
import { getAuditLogsQueryOptions } from "@/queries/mes"

export const Route = createFileRoute("/_layout/logs")({
  component: LogsPage,
  head: () => ({ meta: [{ title: "Logs | MebeliX" }] }),
})

const MODULES = [
  { value: "", label: "Hammasi" },
  { value: "orders", label: "Buyurtmalar" },
  { value: "sessions", label: "Sessiyalar" },
  { value: "employees", label: "Hodimlar" },
  { value: "clients", label: "Mijozlar" },
  { value: "users", label: "Foydalanuvchilar" },
]

function LogsPage() {
  const [module, setModule] = useState("")
  const { data, isLoading } = useQuery(getAuditLogsQueryOptions({ module }))

  return (
    <div>
      <PageHeader
        title="Tizim loglari"
        description="Kim qachon nima qilgan — to'liq audit"
      />
      <Tabs value={module} onValueChange={setModule} className="mb-4">
        <TabsList className="h-9 flex-wrap">
          {MODULES.map((m) => (
            <TabsTrigger key={m.value} value={m.value} className="text-xs">
              {m.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Vaqt</TableHead>
                <TableHead>Modul</TableHead>
                <TableHead>Amal</TableHead>
                <TableHead>Izoh</TableHead>
                <TableHead>IP</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.data.length ? (
                data.data.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="num whitespace-nowrap text-xs">
                      {formatDateTime(log.created_at)}
                    </TableCell>
                    <TableCell className="text-xs font-semibold uppercase">
                      {log.module}
                    </TableCell>
                    <TableCell className="text-xs">{log.action}</TableCell>
                    <TableCell className="max-w-[380px] truncate text-sm">
                      {log.message ?? "—"}
                    </TableCell>
                    <TableCell className="num text-xs text-muted-foreground">
                      {log.ip ?? "—"}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-24 text-center text-muted-foreground"
                  >
                    Yozuvlar yo'q.
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
