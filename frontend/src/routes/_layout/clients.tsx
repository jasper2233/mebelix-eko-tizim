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
import { RowOpenCell } from "@/components/Common/RowOpen"
import { SearchInput } from "@/components/Common/SearchInput"
import { TablePagination } from "@/components/Common/TablePagination"
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
import { formatUzPhone } from "@/lib/validation"
import { getClientsQueryOptions, PAGE_SIZE } from "@/queries/mes"

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
  const [page, setPage] = useState(0)
  const { data, isLoading, isError, refetch } = useQuery({
    ...getClientsQueryOptions(debounced, page * PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <PageHeader
        title="Mijozlar"
        // Umumiy son sarlavhada: qidiruv paytida esa topilganlar soni.
        // Jadval bir sahifada PAGE_SIZE qator chizadi — qolganiga jadval
        // ostidagi sahifalagich orqali yetiladi.
        description={
          data
            ? debounced
              ? `${data.count} ta topildi — aylanma bo'yicha tartiblangan`
              : `${data.count} mijoz — aylanma bo'yicha tartiblangan`
            : "Buyurtmachilar reestri"
        }
        // Yaratish ham `ManagerUser` — direktorga tugma ko'rsatilmaydi, aks
        // holda bosgach POST /clients dan 403 olardi.
        // Qidiruv sarlavha qatorida, tugma yonida — alohida qator bo'sh joy
        // bilan vertikal joy yeb turardi (buyurtmalar reestrida ham qidiruv
        // boshqaruv qatorida).
        actions={
          <div className="flex w-full flex-wrap items-center gap-2 md:w-auto">
            <SearchInput
              className="w-full md:w-72"
              placeholder="Ism yoki telefon bo'yicha qidirish"
              value={search}
              // Qidiruv o'zgarganda birinchi sahifaga: aks holda 3-sahifada
              // turib qidirgan odam bo'sh jadval ko'rardi.
              onChange={(v) => {
                setSearch(v)
                setPage(0)
              }}
            />
            {canWrite && <AddClient />}
          </div>
        }
      />
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>F.I.Sh / Kompaniya</TableHead>
              <TableHead className="text-right">Buyurtmalar</TableHead>
              <TableHead className="text-right">Umumiy summa</TableHead>
              {/* "Reyting" emas, ABC: qisqartma ustun sarlavhasida
                    tushuntirilmaydi, har belgining tooltip'i bor. */}
              <TableHead
                className="text-center"
                title="ABC segment — aylanmadagi og'irlik: A — birinchi 80%, B — 80–95%, C — oxirgi 5%"
              >
                ABC
              </TableHead>
              <TableHead>Qo'shilgan</TableHead>
              {canWrite && <TableHead />}
              {/* Strelka ustuni — qator mijoz kartasini ochadi */}
              <TableHead className="w-8" />
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
                    {/* Telefon o'qiladigan formatda — buyurtma formasi bilan bir xil */}
                    <span className="num block text-sm text-muted-foreground">
                      {c.phone ? formatUzPhone(c.phone) : "—"}
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
                        {/* Buyurtmasi bor mijoz o'chirilmaydi (backend 409) —
                            qatorda soni bor, tugma oldindan o'chiq */}
                        <RowAction
                          icon={Trash2}
                          title={
                            (c.orders_count ?? 0) > 0
                              ? `${c.orders_count} ta buyurtmasi bor — o'chirib bo'lmaydi`
                              : "O'chirish"
                          }
                          danger
                          disabled={(c.orders_count ?? 0) > 0}
                          onClick={() => setDeleteFor(c)}
                        />
                      </div>
                    </TableCell>
                  )}
                  <RowOpenCell />
                </TableRow>
              ))
            ) : (
              <EmptyRow colSpan={canWrite ? 7 : 6}>
                {debounced
                  ? `"${debounced}" bo'yicha mijoz topilmadi.`
                  : "Hali mijoz yo'q — \"+ Yangi mijoz\" bilan qo'shing."}
              </EmptyRow>
            )}
          </TableBody>
        </Table>
      )}
      <TablePagination
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.count ?? 0}
        onPage={setPage}
      />
      {editFor && (
        <AddClient client={editFor} onClose={() => setEditFor(null)} />
      )}
      <DeleteClient client={deleteFor} onClose={() => setDeleteFor(null)} />
      <ClientCard clientId={openId} onClose={() => setOpenId(null)} />
    </div>
  )
}
