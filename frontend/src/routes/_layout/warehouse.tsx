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
import { SelectField } from "@/components/Common/SelectField"
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
const KATALOG: { value: string; label: string }[] = [
  { value: "", label: "Hammasi" },
  { value: "M", label: "Material" },
  { value: "F", label: "Furnitura" },
  { value: "X", label: "Xizmat" },
]

function WarehousePage() {
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const [catalog, setCatalog] = useState("")
  //: `M-LD` ko'rinishidagi TO'LIQ guruh kodi (katalog harfi bilan)
  const [guruh, setGuruh] = useState("")
  const [status, setStatus] = useState("")
  const [lowStock, setLowStock] = useState(false)
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(0)
  const [editFor, setEditFor] = useState<CatalogItemRead | null>(null)
  const debounced = useDebounced(search.trim())

  const tree = useQuery(getCatalogGroupsQueryOptions())
  const { data, isLoading, isError, refetch } = useQuery({
    ...getCatalogItemsQueryOptions(
      {
        // Guruh tanlansa katalog ham o'shanikidan olinadi (`M-LG` -> M + LG):
        // «Hammasi» tabida turib guruh tanlash ham to'g'ri ishlasin
        catalog: guruh ? guruh.slice(0, 1) : catalog,
        groupCode: guruh ? guruh.slice(2) : undefined,
        status: status as "Aktiv" | "Arxiv" | undefined,
        lowStock,
        search: debounced,
      },
      page * PAGE_SIZE,
    ),
    placeholderData: keepPreviousData,
  })

  // Har filtr o'zgarganda birinchi sahifaga: 5-sahifada turib guruh
  // almashtirgan odam bo'sh jadval ko'rardi
  const filtr =
    <T,>(set: (v: T) => void) =>
    (v: T) => {
      set(v)
      setPage(0)
    }

  // Guruh ro'yxati TANLANGAN katalog ichidan. Tanlov qiymati TO'LIQ kod
  // (`M-LG`), faqat `group_code` emas: `LG` ikki katalogda ham bor — `M-LG`
  // (LEGE fasad paneli) va `X-LG` (logistika), `KM`/`KR` esa kromka nomini
  // ikkovida takrorlaydi. Faqat guruh harfi bilan filtrlaganda «Hammasi»
  // tanlangan holatda boshqa katalogning pozitsiyalari ham chiqib ketardi.
  const guruhlar = (tree.data?.groups ?? [])
    .filter((g) => !catalog || g.catalog === catalog)
    .map((g) => ({
      value: `${g.catalog}-${g.group_code}`,
      label: g.group_name,
      hint: `${g.catalog}-${g.group_code} · ${g.count}`,
    }))

  const soni = (harf: string) =>
    harf
      ? (tree.data?.totals[harf] ?? 0)
      : Object.values(tree.data?.totals ?? {}).reduce((a, b) => a + b, 0)

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
          <SearchInput
            className="w-full md:w-80"
            placeholder="Kod, nom, artikul yoki dekor"
            value={search}
            onChange={filtr(setSearch)}
          />
        }
      />

      {/* Katalog harfi — kodning BIRINCHI qismi, ya'ni eng yirik bo'linish.
          Tab sifatida: uchta band, doim ko'rinib turadi, bir bosishda almashadi.
          Guruh (35 ta) esa ro'yxatga sig'maydi — u ochiluvchi tanlovda. */}
      <Tabs
        value={catalog}
        onValueChange={(v) => {
          setCatalog(v)
          setGuruh("") // boshqa katalogning guruhi tanlanib qolmasin
          setPage(0)
        }}
        className="mb-4"
      >
        <TabsList className="h-9">
          {KATALOG.map((k) => (
            <TabsTrigger key={k.value} value={k.value}>
              {k.label}
              <span className="num ml-1.5 text-muted-foreground">
                {soni(k.value)}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SelectField
          className="w-full sm:w-64"
          value={guruh}
          onChange={filtr(setGuruh)}
          options={guruhlar}
          placeholder="Guruh"
          emptyLabel="Barcha guruhlar"
        />
        <SelectField
          className="w-full sm:w-40"
          value={status}
          onChange={filtr(setStatus)}
          options={[
            { value: "Aktiv", label: "Aktiv" },
            { value: "Arxiv", label: "Arxiv" },
          ]}
          placeholder="Holat"
          emptyLabel="Har qanday holat"
        />
        {/* Omborchining birinchi savoli: nimani buyurtma qilish kerak.
            Chegara qo'yilmagan pozitsiya bu ro'yxatga tushmaydi. */}
        <Button
          variant={lowStock ? "default" : "outline"}
          onClick={() => filtr(setLowStock)(!lowStock)}
        >
          Kam qolgan
        </Button>
      </div>

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
                    {/* Kod — omborchi javonda aynan shuni izlaydi: birinchi
                        ustun va monoshrift */}
                    <TableCell className="num whitespace-nowrap font-semibold">
                      {i.code}
                    </TableCell>
                    <TableCell className="min-w-[240px]" title={i.name}>
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
                    <TableCell className="num whitespace-nowrap text-right">
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
                    <TableCell className="num whitespace-nowrap text-right text-muted-foreground">
                      {formatMoney(i.purchase_price)}
                    </TableCell>
                    <TableCell className="num whitespace-nowrap text-right font-semibold">
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

      <CatalogEdit
        key={editFor?.id}
        item={editFor}
        onClose={() => setEditFor(null)}
      />
    </div>
  )
}
