import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Trash2 } from "lucide-react"
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

export const Route = createFileRoute("/_layout/stock")({
  component: StockPage,
  beforeLoad: requireAccess(isStockStaff),
  head: () => ({ meta: [{ title: "Materiallar ombori | MebeliX" }] }),
})

const isLow = (i: StockItemRead) =>
  num(i.min_qty) > 0 && num(i.qty) < num(i.min_qty)

function StockPage() {
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
  // Yetishmovchilik bo'yicha kamayish tartibida: birinchi chiplar aynan
  // buyurtma berish kerak bo'lgan guruhlar. Alifbo tartibi bu yerda hech
  // qanday ma'lumot bermasdi.
  const visibleGroups = (groups ?? [])
    .filter((g) => !catalog || g.catalog === catalog)
    .sort((a, b) => b.low - a.low || b.items - a.items)

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
        {/* KUNNING ISHI bitta jumlada. Ilgari uchta teng karta turardi
            (pozitsiya / tugayapti / qoldiq qiymati) — ular 85px joy olib,
            ma'lumotni pastga surardi va faqat bittasi harakatga chorlardi.
            Endi u jumla O'ZI filtr: "Tugayaptilar" degan alohida tugma ham
            aynan shu ishni qilardi, ikkitasi ortiqcha edi. */}
        <button
          type="button"
          onClick={() => setLow(!low)}
          aria-pressed={low}
          className={`mb-4 flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 rounded-lg border px-4 py-3 text-left transition-colors ${
            low
              ? "border-(--brand-gold-deep) bg-(--brand-gold)/10"
              : "bg-card hover:border-(--brand-gold)"
          }`}
        >
          {summary?.low ? (
            <>
              <span className="num text-3xl font-black text-(--brand-gold-deep)">
                {summary.low}
              </span>
              <span className="text-lg font-semibold">
                pozitsiya minimal zaxiradan past
              </span>
            </>
          ) : (
            <span className="text-lg font-semibold">
              Hamma pozitsiya zaxirada yetarli
            </span>
          )}
          <span className="ml-auto text-sm text-muted-foreground">
            {summary?.items ?? "—"} pozitsiya · ombor qiymati{" "}
            <span className="num">{uzs(summary?.value_uzs)}</span> so'm
          </span>
          <span className="w-full text-2xs uppercase tracking-wider text-muted-foreground">
            {low
              ? "faqat shular ko'rsatilmoqda — bekor qilish uchun bosing"
              : "ro'yxatni ochish uchun bosing"}
          </span>
        </button>

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
          <SearchInput
            className="ml-auto w-full max-w-xs"
            placeholder="Nomi yoki kodi"
            value={search}
            onChange={setSearch}
          />
        </div>

        {/* Guruh chiplari BITTA qatorda, yetishmovchilik bo'yicha kamayish
            tartibida: 28 guruh uch qatorga yoyilganda 84 raqam bir vaqtda
            ko'rinardi va hech biri ajralib turmasdi. Endi birinchi o'nta —
            aynan buyurtma berish kerak bo'lganlari. Kod (`F-RC`) oldinda:
            u zavodning o'z manzil tizimi, guruh nomi esa uzun. */}
        <div className="mb-4 flex gap-1.5 overflow-x-auto pb-1">
          <Chip active={!group} onClick={() => setGroup("")}>
            Barchasi
          </Chip>
          {visibleGroups.map((g) => (
            <Chip
              key={`${g.catalog}-${g.group_code}`}
              active={group === g.group_code}
              onClick={() =>
                setGroup(group === g.group_code ? "" : g.group_code)
              }
            >
              <span className="num mr-1.5 text-muted-foreground">
                {g.catalog}-{g.group_code}
              </span>
              {g.group_name}
              {g.low > 0 ? (
                <span className="num ml-1.5 font-semibold text-(--brand-gold-deep)">
                  {g.low}
                </span>
              ) : (
                <span className="num ml-1.5 text-muted-foreground">
                  {g.items}
                </span>
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
                  {/* Guruh ustuni FILTR YOQILGANDA yashiriladi: 45 qator
                      ketma-ket bir xil qiymatni takrorlab turardi */}
                  {!group && <TableHead>Guruh</TableHead>}
                  <TableHead className="text-right">Qoldiq</TableHead>
                  <TableHead className="text-right">Min</TableHead>
                  {/* Xarid va sotuv bitta katakda: ikkalasi ham kerak, lekin
                      ikkita ustun jadvalni amallar ustunidan siqib chiqarardi */}
                  <TableHead className="text-right">Narx</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.data.length ? (
                  data.data.map((i) => (
                    <TableRow key={i.id}>
                      <TableCell className="num whitespace-nowrap text-muted-foreground">
                        {i.code}
                      </TableCell>
                      <TableCell className="font-medium">
                        {i.name}
                        {!!i.size && (
                          <span className="ml-1.5 text-2xs text-muted-foreground">
                            {i.size}
                          </span>
                        )}
                      </TableCell>
                      {!group && (
                        <TableCell className="text-muted-foreground">
                          {i.group_name}
                        </TableCell>
                      )}
                      {/* IKKI darajali signal. Ilgari nol ham, kamaygan ham bir
                          xil qizil edi — omborchi "ish to'xtadi" bilan
                          "buyurtma bering" ni ajrata olmasdi. Qizil = nol,
                          oltin = minimal zaxiradan past. */}
                      <TableCell className="num text-right">
                        <span
                          className={
                            num(i.qty) <= 0
                              ? "rounded px-1.5 py-0.5 font-bold text-white bg-(--status-cancelled)"
                              : isLow(i)
                                ? "font-bold text-(--brand-gold-deep)"
                                : "font-bold"
                          }
                        >
                          {qty(i.qty)}
                        </span>
                        {!!i.unit && (
                          <span className="ml-1 text-2xs text-muted-foreground">
                            {i.unit}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="num text-right text-muted-foreground">
                        {num(i.min_qty) > 0 ? qty(i.min_qty) : "—"}
                      </TableCell>
                      <TableCell className="num whitespace-nowrap text-right leading-tight">
                        <div className="font-medium">
                          {i.sale_uzs ? uzs(i.sale_uzs) : "—"}
                        </div>
                        <div className="text-2xs text-muted-foreground">
                          xarid {i.purchase_uzs ? uzs(i.purchase_uzs) : "—"}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
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
                                size="icon"
                                className="size-8 text-muted-foreground"
                                title="Tahrirlash"
                                onClick={() => setEditFor(i)}
                              >
                                <Pencil />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="size-8 text-muted-foreground hover:text-destructive"
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
                  <EmptyRow colSpan={group ? 6 : 7}>
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
