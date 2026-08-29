import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Trash2 } from "lucide-react"
import { useState } from "react"

import type { ClientRead } from "@/client"
import { AddClient } from "@/components/Clients/AddClient"
import { ClientCard } from "@/components/Clients/ClientCard"
import { ClientSegment } from "@/components/Clients/ClientSegment"
import { DeleteClient } from "@/components/Clients/DeleteClient"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { RowAction } from "@/components/Common/RowAction"
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useDebounced } from "@/hooks/useDebounced"
import { requireAccess } from "@/lib/guards"
import { formatDate, formatMoney, isManagement, isManager } from "@/lib/mes"
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
  const { currentUser } = useCurrentUser()
  // Yozish huquqi backend bilan bir xil: `ManagerUser` — menejer, admin,
  // superuser. Rolni bu yerda qayta ta'riflamaymiz, `lib/mes` dagi yagona
  // manbadan olinadi.
  // `isManagement` DIREKTORNI ham qamrab oladi, backend esa `ManagerUser` —
  // ya'ni menejer va admin. Kengroq shart tugmalarni direktorga ham ko'rsatib,
  // u bosganda 403 olardi.
  const canWrite = isManager(currentUser)
  const [editFor, setEditFor] = useState<ClientRead | null>(null)
  const [deleteFor, setDeleteFor] = useState<ClientRead | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)
  const { data, isLoading, isError, refetch } = useQuery({
    ...getClientsQueryOptions(debounced),
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <PageHeader
        title="Mijozlar"
        // Umumiy son sarlavhada: qidiruv paytida esa topilganlar soni —
        // "nechta mijoz bor?" savoliga sahifalamasdan javob.
        description={
          data
            ? debounced
              ? `${data.count} ta topildi — aylanma bo'yicha tartiblangan`
              : `${data.count} mijoz — aylanma bo'yicha tartiblangan`
            : "Buyurtmachilar reestri"
        }
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
                <TableHead className="text-right">Buyurtmalar</TableHead>
                <TableHead className="text-right">Umumiy summa</TableHead>
                {/* "Reyting" emas, ABC: qisqartma ustun sarlavhasida
                    tushuntirilmaydi, har belgining tooltip'i bor. */}
                <TableHead className="text-center">ABC</TableHead>
                <TableHead>Qo'shilgan</TableHead>
                {canWrite && <TableHead />}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.data.length ? (
                data.data.map((c) => (
                  <TableRow
                    key={c.id}
                    onClick={() => setOpenId(c.id)}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") setOpenId(c.id)
                    }}
                    className="cursor-pointer"
                  >
                    <TableCell
                      className="max-w-[260px] font-medium"
                      title={c.full_name}
                    >
                      <span className="block truncate">{c.full_name}</span>
                      {/* Telefon nom ostida: alohida ustun kenglik yeb,
                          summa va ABC ni chetga surib yuborardi. */}
                      <span className="num block text-sm text-muted-foreground">
                        {c.phone ?? "—"}
                      </span>
                    </TableCell>
                    <TableCell className="num text-right font-semibold">
                      {c.orders_count}
                    </TableCell>
                    <TableCell className="num text-right">
                      <span className="block font-semibold">
                        {formatMoney(c.total_amount)}
                      </span>
                      {/* Ulush summani KONTEKSTGA qo'yadi: "50 mln" ko'p ham,
                          kam ham bo'lishi mumkin — 5.8% esa aniq javob. */}
                      <span className="block text-sm text-muted-foreground">
                        {(c.share_pct ?? 0).toFixed(1)}%
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <ClientSegment segment={c.segment} />
                    </TableCell>
                    <TableCell className="num text-muted-foreground">
                      {formatDate(c.created_at)}
                    </TableCell>
                    {canWrite && (
                      <TableCell
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => e.stopPropagation()}
                      >
                        <div className="flex justify-end gap-1">
                          <RowAction
                            icon={Pencil}
                            title="Tahrirlash"
                            onClick={() => setEditFor(c)}
                          />
                          <RowAction
                            icon={Trash2}
                            title="O'chirish"
                            danger
                            onClick={() => setDeleteFor(c)}
                          />
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              ) : (
                <EmptyRow colSpan={canWrite ? 6 : 5}>
                  {debounced
                    ? `"${debounced}" bo'yicha mijoz topilmadi.`
                    : "Hali mijoz yo'q — \"+ Yangi mijoz\" bilan qo'shing."}
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
      {editFor && (
        <AddClient client={editFor} onClose={() => setEditFor(null)} />
      )}
      <DeleteClient client={deleteFor} onClose={() => setDeleteFor(null)} />
      <ClientCard clientId={openId} onClose={() => setOpenId(null)} />
    </div>
  )
}
