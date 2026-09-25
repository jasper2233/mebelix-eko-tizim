import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Pencil, ReceiptText } from "lucide-react"
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
  // Katalog va guruh MANZILDA: yon menyudagi kategoriya havolalari shu yerga
  // tushadi, havola nusxalab yuborilsa ham o'sha ro'yxat ochiladi.
  validateSearch: (
    s: Record<string, unknown>,
  ): { katalog?: string; guruh?: string } => ({
    katalog:
      typeof s.katalog === "string" && /^[MFX]$/.test(s.katalog)
        ? s.katalog
        : undefined,
    guruh:
      typeof s.guruh === "string" && /^[MFX]-[A-Z]{2}$/.test(s.guruh)
        ? s.guruh
        : undefined,
  }),
})

function WarehousePage() {
  const { currentUser } = useCurrentUser()
  const canWrite = isWarehouseWriter(currentUser)
  const navigate = Route.useNavigate()
  // Katalog harfi va TO'LIQ guruh kodi (`M-LD`) manzildan keladi
  const { katalog: catalog = "", guruh = "" } = Route.useSearch()
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

  // Manzildagi filtr — sahifa ham nolga qaytadi
  const yonalt = (next: { katalog?: string; guruh?: string }) => {
    setPage(0)
    navigate({ search: next, replace: true })
  }

  const guruhlarHammasi = tree.data?.groups ?? []
  // Tanlangan kategoriya sarlavhada aytiladi: sahifada tab yo'q (ular yon
  // menyuda), ya'ni qaysi ro'yxat ochiqligini boshqa hech narsa ko'rsatmaydi
  const kategoriya = { M: "Material", F: "Furnitura", X: "Xizmat" }[catalog]
  const guruhNomi = guruhlarHammasi.find(
    (g) => `${g.catalog}-${g.group_code}` === guruh,
  )?.group_name

  // Guruh ro'yxati TANLANGAN katalog ichidan. Tanlov qiymati TO'LIQ kod
  // (`M-LG`), faqat `group_code` emas: `LG` ikki katalogda ham bor — `M-LG`
  // (LEGE fasad paneli) va `X-LG` (logistika), `KM`/`KR` esa kromka nomini
  // ikkovida takrorlaydi. Faqat guruh harfi bilan filtrlaganda «Hammasi»
  // tanlangan holatda boshqa katalogning pozitsiyalari ham chiqib ketardi.
  const guruhlar = guruhlarHammasi
    .filter((g) => !catalog || g.catalog === catalog)
    .map((g) => ({
      value: `${g.catalog}-${g.group_code}`,
      label: g.group_name,
      hint: `${g.catalog}-${g.group_code} · ${g.count}`,
    }))

  return (
    <div>
      <PageHeader
        title="Mahsulotlar ombori"
        description={
          data
            ? [
                guruhNomi ?? kategoriya,
                `${data.count} pozitsiya${debounced ? " topildi" : ""}`,
                "kod, artikul va qoldiq bilan",
              ]
                .filter(Boolean)
                .join(" · ")
            : "Katalog: material, furnitura va xizmatlar"
        }
        actions={
          <div className="flex w-full flex-wrap items-center gap-2 md:w-auto">
            <SearchInput
              className="w-full md:w-72"
              placeholder="Kod, nom, artikul yoki dekor"
              value={search}
              onChange={filtr(setSearch)}
            />
            {/* Sotuv listi katalogdan qatorlarni oladi — shuning uchun kirish
                joyi shu yerda, alohida menyu bandi emas */}
            <Button asChild>
              <Link to="/sotuv">
                <ReceiptText className="size-4" /> Sotuv listi
              </Link>
            </Button>
          </div>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SelectField
          className="w-full sm:w-64"
          value={guruh}
          onChange={(v) =>
            yonalt({ katalog: catalog || undefined, guruh: v || undefined })
          }
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
