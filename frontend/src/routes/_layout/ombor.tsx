import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Trash2, TriangleAlert } from "lucide-react"
import { useState } from "react"

import type { StockItemRead } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
import { num, qty, uzs } from "@/components/Stock/format"
import { MoveDialog } from "@/components/Stock/MoveDialog"
import { SaleDialog } from "@/components/Stock/SaleDialog"
import { SalesView } from "@/components/Stock/SalesView"
import {
  DeleteItem,
  ImportCatalog,
  ItemDialog,
} from "@/components/Stock/StockDialogs"
import { Badge } from "@/components/ui/badge"
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { useDebounced } from "@/hooks/useDebounced"
import { requireAccess } from "@/lib/guards"
import { isStockStaff } from "@/lib/mes"
import {
  getStockGroupsQueryOptions,
  getStockQueryOptions,
  getStockSummaryQueryOptions,
} from "@/queries/mes"

export const Route = createFileRoute("/_layout/ombor")({
  component: OmborPage,
  beforeLoad: requireAccess(isStockStaff),
  head: () => ({ meta: [{ title: "Materiallar ombori | MebeliX" }] }),
})

const isLow = (i: StockItemRead) =>
  num(i.min_qty) > 0 && num(i.qty) < num(i.min_qty)

function OmborPage() {
  const [search, setSearch] = useState("")
  const [catalog, setCatalog] = useState("")
  const [group, setGroup] = useState("")
  const [low, setLow] = useState(false)
  const [moveFor, setMoveFor] = useState<StockItemRead | null>(null)
  const [editFor, setEditFor] = useState<StockItemRead | null>(null)
  const [deleteFor, setDeleteFor] = useState<StockItemRead | null>(null)
  const [sellFor, setSellFor] = useState<StockItemRead | null>(null)
  // Katalog va sotuvlar — bitta sahifada ikki ko'rinish: omborchi kun
  // davomida ular orasida tez-tez o'tadi
  const [view, setView] = useState<"katalog" | "sotuv">("katalog")
  const debounced = useDebounced(search.trim())
  const { currentUser } = useCurrentUser()
  // Backend bilan BIR XIL shart (`StockUser`): omborchining butun ishi shu
  // sahifada, uni faqat ko'rish huquqi bilan qoldirish katalogni ham,
  // pozitsiya qo'shishni ham imkonsiz qilardi
  const canEdit = isStockStaff(currentUser)

  const { data, isLoading, isError, refetch } = useQuery({
    ...getStockQueryOptions({
      search: debounced,
      catalog: (catalog || undefined) as "F" | "M" | undefined,
      groupCode: group,
      low,
    }),
    placeholderData: keepPreviousData,
  })
  const { data: groups } = useQuery(getStockGroupsQueryOptions())
  const { data: summary } = useQuery(getStockSummaryQueryOptions())

  // Katalog almashganda guruh chipi eskirib qoladi (RC furniturada, LD materialda)
  const visibleGroups = (groups ?? []).filter(
    (g) => !catalog || g.catalog === catalog,
  )

  return (
    <div>
      <PageHeader
        title="Materiallar ombori"
        description="Xomashyo va furnitura qoldig'i — TMO dan ayrim"
        actions={
          canEdit ? (
            <div className="flex gap-2">
              <ImportCatalog />
              <ItemDialog groups={groups ?? []} />
            </div>
          ) : undefined
        }
      />

      <Tabs value={view} onValueChange={(v) => setView(v as typeof view)}>
        <TabsList className="mb-4 h-9">
          <TabsTrigger value="katalog">Katalog</TabsTrigger>
          <TabsTrigger value="sotuv">Sotuvlar</TabsTrigger>
        </TabsList>
      </Tabs>

      {view === "sotuv" && <SalesView />}

      <div hidden={view !== "katalog"}>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Stat label="Pozitsiya" value={String(summary?.items ?? "—")} />
          <Stat
            label="Tugayapti"
            value={String(summary?.low ?? "—")}
            tone={summary?.low ? "warn" : undefined}
          />
          <Stat
            label="Qoldiq qiymati"
            value={summary ? `${uzs(summary.value_uzs)} so'm` : "—"}
          />
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Tabs
            value={catalog}
            onValueChange={(v) => {
              setCatalog(v)
              setGroup("")
            }}
          >
            <TabsList className="h-9">
              <TabsTrigger value="">Hammasi</TabsTrigger>
              <TabsTrigger value="M">Material</TabsTrigger>
              <TabsTrigger value="F">Furnitura</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button
            variant={low ? "default" : "outline"}
            size="sm"
            onClick={() => setLow(!low)}
          >
            <TriangleAlert /> Tugayaptilar
          </Button>
          <SearchInput
            className="ml-auto w-full max-w-xs"
            placeholder="Nomi yoki kodi"
            value={search}
            onChange={setSearch}
          />
        </div>

        {/* Guruh chiplari — 28 ta guruh, kompyuter ekranida bir qatorga sig'adi */}
        <div className="mb-4 flex flex-wrap gap-1.5">
          <Chip active={!group} onClick={() => setGroup("")}>
            Barcha guruh
          </Chip>
          {visibleGroups.map((g) => (
            <Chip
              key={`${g.catalog}-${g.group_code}`}
              active={group === g.group_code}
              onClick={() =>
                setGroup(group === g.group_code ? "" : g.group_code)
              }
            >
              {g.group_name}
              <span className="ml-1.5 text-muted-foreground">{g.items}</span>
              {g.low > 0 && (
                <span className="ml-1 text-(--status-cancelled)">▲{g.low}</span>
              )}
            </Chip>
          ))}
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
                  <TableHead>Kod</TableHead>
                  <TableHead>Nomi</TableHead>
                  <TableHead>Guruh</TableHead>
                  <TableHead className="text-right">Qoldiq</TableHead>
                  <TableHead className="text-right">Min</TableHead>
                  <TableHead className="text-right">Xarid</TableHead>
                  <TableHead className="text-right">Sotuv</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.data.length ? (
                  data.data.map((i) => (
                    <TableRow key={i.id}>
                      <TableCell className="num whitespace-nowrap font-medium">
                        {i.code}
                      </TableCell>
                      <TableCell>
                        {i.name}
                        {!!i.size && (
                          <span className="ml-1.5 text-2xs text-muted-foreground">
                            {i.size}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {i.group_name}
                      </TableCell>
                      <TableCell className="num text-right">
                        {isLow(i) ? (
                          <Badge className="bg-(--status-cancelled) text-white">
                            {qty(i.qty)}
                          </Badge>
                        ) : (
                          <b>{qty(i.qty)}</b>
                        )}
                        {!!i.unit && (
                          <span className="ml-1 text-2xs text-muted-foreground">
                            {i.unit}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="num text-right text-muted-foreground">
                        {num(i.min_qty) > 0 ? qty(i.min_qty) : "—"}
                      </TableCell>
                      <TableCell className="num text-right text-muted-foreground">
                        {i.purchase_uzs ? uzs(i.purchase_uzs) : "—"}
                      </TableCell>
                      <TableCell className="num text-right">
                        {i.sale_uzs ? uzs(i.sale_uzs) : "—"}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setMoveFor(i)}
                          >
                            Kirim / Chiqim
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={num(i.qty) <= 0}
                            title={
                              num(i.qty) <= 0 ? "Qoldiq yo'q" : "Mijozga sotish"
                            }
                            onClick={() => setSellFor(i)}
                          >
                            Sotish
                          </Button>
                          {canEdit && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                title="Tahrirlash"
                                onClick={() => setEditFor(i)}
                              >
                                <Pencil />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive"
                                title="O'chirish"
                                onClick={() => setDeleteFor(i)}
                              >
                                <Trash2 />
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <EmptyRow colSpan={8}>
                    {debounced || group || low
                      ? "Shu shartga mos pozitsiya yo'q."
                      : "Katalog bo'sh — tepadagi \"Excel'dan yuklash\" tugmasi bilan boshlang."}
                  </EmptyRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {moveFor && (
        <MoveDialog
          key={moveFor.id}
          item={moveFor}
          onClose={() => setMoveFor(null)}
        />
      )}
      {editFor && (
        <ItemDialog
          key={editFor.id}
          groups={groups ?? []}
          item={editFor}
          onClose={() => setEditFor(null)}
        />
      )}
      {sellFor && (
        <SaleDialog
          key={sellFor.id}
          item={sellFor}
          onClose={() => setSellFor(null)}
        />
      )}
      <DeleteItem item={deleteFor} onClose={() => setDeleteFor(null)} />
    </div>
  )
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: "warn"
}) {
  return (
    <div className="rounded-lg border bg-card px-4 py-3">
      <div className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={`num mt-0.5 text-2xl font-bold ${tone === "warn" ? "text-(--status-cancelled)" : ""}`}
      >
        {value}
      </div>
    </div>
  )
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-sm transition-colors ${
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "bg-card hover:border-primary/40"
      }`}
    >
      {children}
    </button>
  )
}
