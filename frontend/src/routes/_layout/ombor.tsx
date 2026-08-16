import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Minus, Plus, TriangleAlert } from "lucide-react"
import { useState } from "react"

import { type StockItemRead, StockService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
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
import { isProductionStaff } from "@/lib/mes"
import {
  crudCallbacks,
  getStockGroupsQueryOptions,
  getStockQueryOptions,
  getStockSummaryQueryOptions,
} from "@/queries/mes"

export const Route = createFileRoute("/_layout/ombor")({
  component: OmborPage,
  beforeLoad: requireAccess(isProductionStaff),
  head: () => ({ meta: [{ title: "Materiallar ombori | MebeliX" }] }),
})

const num = (v: string | number | null | undefined) => Number(v ?? 0)
const uzs = (v: string | number | null | undefined) =>
  num(v).toLocaleString("ru-RU")
/** Qoldiq butun bo'lsa kasrsiz: 174 dona "174.000" bo'lib ko'rinmasin */
const qty = (v: string | number) =>
  Number.isInteger(num(v))
    ? String(num(v))
    : num(v).toFixed(3).replace(/0+$/, "")

const isLow = (i: StockItemRead) =>
  num(i.min_qty) > 0 && num(i.qty) < num(i.min_qty)

function OmborPage() {
  const [search, setSearch] = useState("")
  const [catalog, setCatalog] = useState("")
  const [group, setGroup] = useState("")
  const [low, setLow] = useState(false)
  const [moveFor, setMoveFor] = useState<StockItemRead | null>(null)
  const debounced = useDebounced(search.trim())

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
      />

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
            onClick={() => setGroup(group === g.group_code ? "" : g.group_code)}
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
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setMoveFor(i)}
                      >
                        Kirim / Chiqim
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <EmptyRow colSpan={8}>
                  {debounced || group || low
                    ? "Shu shartga mos pozitsiya yo'q."
                    : "Katalog bo'sh — `python -m app.commands.import_stock_catalog` bilan yuklang."}
                </EmptyRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {moveFor && (
        <MoveDialog
          key={moveFor.id}
          item={moveFor}
          onClose={() => setMoveFor(null)}
        />
      )}
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

/** KIRIM / CHIQIM — qoldiqni qo'lda yozish emas, O'ZGARISH miqdori.
 *
 * Omborchi "20 ta keldi" deb o'ylaydi, "endi 174 ta bo'ldi" deb emas. Delta
 * bo'lgani uchun ikki kishi bir vaqtda yozsa ham hech biri yo'qolmaydi —
 * absolyut qiymat esa bir-birini bosib ketardi. */
function MoveDialog({
  item,
  onClose,
}: {
  item: StockItemRead
  onClose: () => void
}) {
  const [amount, setAmount] = useState("")
  const [sign, setSign] = useState<1 | -1>(1)
  const [note, setNote] = useState("")
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["stock"], "Qoldiq yangilandi")
  const mutation = useMutation({
    mutationFn: () =>
      StockService.moveStockItem({
        itemId: item.id,
        requestBody: {
          delta: String(sign * Number(amount)),
          note: note || null,
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })

  const value = Number(amount)
  const after = num(item.qty) + sign * value
  const valid = amount !== "" && value > 0 && after >= 0

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{item.name}</DialogTitle>
          <DialogDescription>
            {item.code} · hozirgi qoldiq <b>{qty(item.qty)}</b>
            {item.unit ? ` ${item.unit}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2">
          <Button
            type="button"
            variant={sign === 1 ? "default" : "outline"}
            className="flex-1"
            onClick={() => setSign(1)}
          >
            <Plus /> Kirim
          </Button>
          <Button
            type="button"
            variant={sign === -1 ? "default" : "outline"}
            className="flex-1"
            onClick={() => setSign(-1)}
          >
            <Minus /> Chiqim
          </Button>
        </div>

        <Input
          value={amount}
          onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
          inputMode="decimal"
          placeholder="Miqdor"
          className="h-12 text-center text-xl"
          autoFocus
        />
        <Input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Izoh (kimdan keldi, qayerga ketdi)"
          maxLength={200}
        />

        <p className="text-sm text-muted-foreground">
          Yangi qoldiq:{" "}
          <b className={after < 0 ? "text-(--status-cancelled)" : ""}>
            {amount === "" ? qty(item.qty) : after}
          </b>
          {after < 0 && " — manfiy bo'lib bo'lmaydi"}
        </p>

        <DialogFooter>
          <LoadingButton
            disabled={!valid}
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Saqlash
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
