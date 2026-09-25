import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil } from "lucide-react"
import { useState } from "react"

import type { CatalogItemRead } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { RowAction } from "@/components/Common/RowAction"
import { SearchInput } from "@/components/Common/SearchInput"
import { TablePagination } from "@/components/Common/TablePagination"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { CatalogEdit } from "@/components/Warehouse/CatalogEdit"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useDebounced } from "@/hooks/useDebounced"
import { requireAccess } from "@/lib/guards"
import { formatMoney, isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import {
  getCatalogGroupsQueryOptions,
  getCatalogItemsQueryOptions,
  PAGE_SIZE,
} from "@/queries/mes"

export const Route = createFileRoute("/_layout/warehouse")({
  component: WarehousePage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Mahsulotlar ombori | MebeliX" }] }),
})

//: Katalog harfining ma'nosi — kod o'zi aytmaydi (`docs/14` §1)
const KATALOG: Record<string, string> = {
  M: "Material",
  F: "Furnitura",
  X: "Xizmat",
}

function WarehousePage() {
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const [catalog, setCatalog] = useState<string | undefined>()
  const [groupCode, setGroupCode] = useState<string | undefined>()
  const [lowStock, setLowStock] = useState(false)
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(0)
  const [editFor, setEditFor] = useState<CatalogItemRead | null>(null)
  const debounced = useDebounced(search.trim())

  const tree = useQuery(getCatalogGroupsQueryOptions())
  const { data, isLoading, isError, refetch } = useQuery({
    ...getCatalogItemsQueryOptions(
      { catalog, groupCode, lowStock, search: debounced },
      page * PAGE_SIZE,
    ),
    placeholderData: keepPreviousData,
  })

  // Filtr o'zgarganda birinchi sahifaga: 5-sahifada turib guruh almashtirgan
  // odam bo'sh jadval ko'rardi
  const tanla = (c?: string, g?: string) => {
    setCatalog(c)
    setGroupCode(g)
    setPage(0)
  }

  const guruhlar = (tree.data?.groups ?? []).filter(
    (g) => !catalog || g.catalog === catalog,
  )
  const jami = Object.values(tree.data?.totals ?? {}).reduce((a, b) => a + b, 0)

  return (
    <div>
      <PageHeader
        title="Mahsulotlar ombori"
        description={
          data
            ? `${data.count} pozitsiya${debounced ? " topildi" : ""} — kod, artikul va qoldiq bilan`
            : "Katalog: material, furnitura va xizmatlar"
        }
        actions={
          <div className="flex w-full flex-wrap items-center gap-2 md:w-auto">
            <SearchInput
              className="w-full md:w-80"
              placeholder="Kod, nom, artikul yoki dekor"
              value={search}
              onChange={(v) => {
                setSearch(v)
                setPage(0)
              }}
            />
            {/* «Kam qolgan» — omborchining birinchi savoli: nimani buyurtma
                qilish kerak. Chegara qo'yilmagan pozitsiya bu yerga tushmaydi. */}
            <Button
              variant={lowStock ? "default" : "outline"}
              onClick={() => {
                setLowStock((v) => !v)
                setPage(0)
              }}
            >
              Kam qolgan
            </Button>
          </div>
        }
      />

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Kategoriya daraxti: katalog harfi -> guruh. Kod shu ikkalasidan
            boshlanadi, ya'ni ro'yxat aynan kod tartibida bo'linadi. */}
        <nav className="shrink-0 lg:w-64">
          <ul className="space-y-1">
            <li>
              <CategoryButton
                active={!catalog && !groupCode}
                onClick={() => tanla(undefined, undefined)}
                label="Hammasi"
                count={jami}
              />
            </li>
            {Object.entries(KATALOG).map(([harf, nom]) => (
              <li key={harf}>
                <CategoryButton
                  active={catalog === harf && !groupCode}
                  onClick={() => tanla(harf, undefined)}
                  label={nom}
                  count={tree.data?.totals[harf] ?? 0}
                />
                {catalog === harf && (
                  <ul className="mt-1 space-y-1 border-l border-border pl-3">
                    {guruhlar.map((g) => (
                      <li key={`${g.catalog}-${g.group_code}`}>
                        <CategoryButton
                          small
                          active={groupCode === g.group_code}
                          onClick={() => tanla(harf, g.group_code)}
                          label={g.group_name}
                          code={`${g.catalog}-${g.group_code}`}
                          count={g.count}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 flex-1">
          {isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : isError ? (
            <QueryError onRetry={() => refetch()} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Kod</TableHead>
                  <TableHead>Nomi</TableHead>
                  <TableHead>Artikul</TableHead>
                  <TableHead className="text-right">Qoldiq</TableHead>
                  <TableHead>Joy</TableHead>
                  <TableHead className="text-right">Xarid</TableHead>
                  <TableHead className="text-right">Sotuv</TableHead>
                  {canWrite && <TableHead className="w-10" />}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.data.length ? (
                  data.data.map((i) => {
                    const kam =
                      i.min_quantity !== null &&
                      Number(i.quantity) < Number(i.min_quantity)
                    return (
                      <TableRow key={i.id}>
                        {/* Kod — omborchi uchun asosiy ustun, shuning uchun
                            birinchi va monoshrift (`num`) */}
                        <TableCell className="num whitespace-nowrap font-semibold">
                          {i.code}
                        </TableCell>
                        <TableCell className="max-w-[320px]" title={i.name}>
                          <span className="block truncate">{i.name}</span>
                          <span className="block truncate text-sm text-muted-foreground">
                            {[i.group_name, i.size_text, i.matrix]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </TableCell>
                        <TableCell className="num text-muted-foreground">
                          {i.article ?? "—"}
                        </TableCell>
                        <TableCell className="num text-right">
                          <span
                            className={cn(
                              "font-semibold",
                              kam && "text-destructive",
                            )}
                            title={
                              kam
                                ? `Eng kam qoldiq ${Number(i.min_quantity)} — buyurtma qilish kerak`
                                : undefined
                            }
                          >
                            {Number(i.quantity)}
                          </span>
                          {i.unit && (
                            <span className="ml-1 text-sm text-muted-foreground">
                              {i.unit}
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {i.location ?? "—"}
                        </TableCell>
                        <TableCell className="num text-right text-muted-foreground">
                          {formatMoney(i.purchase_price)}
                        </TableCell>
                        <TableCell className="num text-right font-semibold">
                          {formatMoney(i.sale_price)}
                        </TableCell>
                        {canWrite && (
                          <TableCell>
                            <RowAction
                              icon={Pencil}
                              title="Qoldiq, joy va narxni tahrirlash"
                              onClick={() => setEditFor(i)}
                            />
                          </TableCell>
                        )}
                      </TableRow>
                    )
                  })
                ) : (
                  <EmptyRow colSpan={canWrite ? 8 : 7}>
                    {debounced
                      ? `"${debounced}" bo'yicha pozitsiya topilmadi.`
                      : lowStock
                        ? "Chegaradan past pozitsiya yo'q."
                        : "Katalog bo'sh — scripts/catalog_import.py bilan yuklanadi."}
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
        </div>
      </div>

      <CatalogEdit
        key={editFor?.id}
        item={editFor}
        onClose={() => setEditFor(null)}
      />
    </div>
  )
}

function CategoryButton({
  active,
  onClick,
  label,
  code,
  count,
  small,
}: {
  active: boolean
  onClick: () => void
  label: string
  code?: string
  count: number
  small?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left transition-colors",
        small ? "text-sm" : "font-medium",
        active ? "bg-sidebar-accent text-sidebar-primary" : "hover:bg-muted/60",
      )}
    >
      <span className="min-w-0 truncate">
        {code && <span className="num mr-2 text-muted-foreground">{code}</span>}
        {label}
      </span>
      <span className="num shrink-0 text-sm text-muted-foreground">
        {count}
      </span>
    </button>
  )
}
