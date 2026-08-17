import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Trash2 } from "lucide-react"
import { useState } from "react"

import type { StockItemRead } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { SearchInput } from "@/components/Common/SearchInput"
import { SelectField } from "@/components/Common/SelectField"
import { num, qty, uzs } from "@/components/Stock/format"
import { MoveDialog } from "@/components/Stock/MoveDialog"
import { SaleDialog } from "@/components/Stock/SaleDialog"
import { SalesView } from "@/components/Stock/SalesView"
import { DeleteItem, ItemDialog } from "@/components/Stock/StockDialogs"
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
  PAGE_SIZE,
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
  // Guruh KATALOG bilan birga saqlanadi ("F|AK"): guruh kodi faqat katalog
  // ichida noyob — `AK` ham "Aksessuar va dekor" (F), ham "Akril fasad" (M).
  // Faqat kodni yuborish ikkala guruhning qatorlarini aralashtirib yuborardi.
  const [group, setGroup] = useState("")
  const [low, setLow] = useState(false)
  const [page, setPage] = useState(0)
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
  // tovar qo'shishni ham imkonsiz qilardi
  const canEdit = isStockStaff(currentUser)

  const { data, isLoading, isError, refetch } = useQuery({
    ...getStockQueryOptions({
      search: debounced,
      catalog: ((group ? group.split("|")[0] : catalog) || undefined) as
        | "F"
        | "M"
        | undefined,
      groupCode: group ? group.split("|")[1] : "",
      low,
      page,
    }),
    placeholderData: keepPreviousData,
  })
  const total = data?.count ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  /** Filtr o'zgarganda sahifa boshiga: 4-sahifada turib filtrni almashtirgan
   *  odam aks holda bo'sh jadval ko'rardi. */
  const reset =
    <T,>(set: (v: T) => void) =>
    (v: T) => {
      set(v)
      setPage(0)
    }
  const { data: groups } = useQuery(getStockGroupsQueryOptions())
  const { data: summary } = useQuery(getStockSummaryQueryOptions())

  // Katalog almashganda guruh chipi eskirib qoladi (RC furniturada, LD materialda)
  // ALIFBO tartibi, yetishmovchilik bo'yicha EMAS: ro'yxat ichida har
  // variantning raqami baribir yonida turadi, ya'ni saralash hech narsa
  // qo'shmaydi — lekin har kirim/chiqimdan keyin o'rinlar almashib, guruhni
  // ko'z bilan topish imkonsiz bo'lardi.
  const visibleGroups = (groups ?? [])
    .filter((g) => !catalog || g.catalog === catalog)
    .sort((a, b) => a.group_name.localeCompare(b.group_name))

  return (
    <div>
      <PageHeader
        title="Materiallar ombori"
        // Ombor qiymati oylik hisobot raqami: sahifada qoladi, lekin o'z
        // kartasini olib yurmaydi
        description={`Xomashyo va furnitura qoldig'i — TMO dan ayrim${
          summary ? ` · ombor qiymati ${uzs(summary.value_uzs)} so'm` : ""
        }`}
        actions={canEdit ? <ItemDialog groups={groups ?? []} /> : undefined}
      />

      <Tabs value={view} onValueChange={(v) => setView(v as typeof view)}>
        <TabsList className="mb-4 h-9">
          <TabsTrigger value="katalog">Katalog</TabsTrigger>
          <TabsTrigger value="sotuv">Sotuvlar</TabsTrigger>
        </TabsList>
      </Tabs>

      {view === "sotuv" && <SalesView />}

      <div hidden={view !== "katalog"}>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Tabs
            value={catalog}
            onValueChange={reset((v: string) => {
              setCatalog(v)
              setGroup("")
            })}
          >
            <TabsList className="h-9">
              <TabsTrigger value="">Hammasi</TabsTrigger>
              <TabsTrigger value="M">Material</TabsTrigger>
              <TabsTrigger value="F">Furnitura</TabsTrigger>
            </TabsList>
          </Tabs>
          {/* Guruh TANLOVI, chip qatori emas. 28 chip gorizontal skrollda
              turganda 19 tasi amalda ko'rinmasdi — sichqoncha g'ildiragi
              gorizontal skrollni bajarmaydi. Ro'yxatda hammasi bir vaqtda
              ochiladi, klaviaturadan yoziladi va vertikal joy olmaydi.
              Yorliq NOM bilan boshlanadi: klaviatura qidiruvi variantni
              boshidan izlaydi, kod oldinda tursa "ruchka" deb yozib bo'lmasdi. */}
          <SelectField
            className="w-64"
            value={group}
            onChange={reset(setGroup)}
            emptyLabel="Barcha guruh"
            placeholder="Barcha guruh"
            options={visibleGroups.map((g) => ({
              value: `${g.catalog}|${g.group_code}`,
              label: g.group_name,
              hint:
                g.low > 0
                  ? `${g.catalog}-${g.group_code} · ${g.low} kam`
                  : `${g.catalog}-${g.group_code}`,
            }))}
          />
          {/* Boolean filtr — ilovaning O'Z naqshi: matn O'ZGARMAYDI, faol
              holat TO'LDIRISH bilan ko'rsatiladi. Aynan shu naqsh shu
              sahifaning ikkinchi tabida ham bor ("Faqat qarzdorlar",
              `SalesView`), shuning uchun nomi ham u bilan bir og'izdan
              gapiradi.

              Ilgari bu filtr jadval ustidagi xabar kartasi ICHIDA turardi va
              matni holatga qarab almashardi ("Hammasini ko'rsatish"). Ikki
              nuqsoni bor edi: (1) filtr holati sahifada ikki joyga bo'lingan —
              jadval nega qisqarganini izlagan odam FILTR QATORIGA qaraydi,
              kartaga qaramaydi; (2) to'la bo'yalgan tugma "yoqilgan" deydi,
              ustidagi "Hammasini ko'rsatish" matni esa teskarisini o'qitadi.

              Raqam tugmaning USTIDA: "shular" nima ekanini bosishdan oldin
              aytadi. Yetishmovchilik yo'q bo'lsa chip umuman chizilmaydi —
              bosilmaydigan "0 kam" o'lik boshqaruv bo'lardi. */}
          {!!summary?.low && (
            <Button
              size="sm"
              variant={low ? "default" : "outline"}
              className="h-9"
              aria-pressed={low}
              title="Minimal zaxiradan past tovarlar"
              onClick={() => {
                setLow(!low)
                setPage(0)
              }}
            >
              Faqat kam qoldiq{" "}
              <span className="num font-bold">{summary.low}</span>
            </Button>
          )}
          <SearchInput
            className="ml-auto w-full max-w-xs"
            placeholder="Nomi, kodi yoki guruhi"
            value={search}
            onChange={reset(setSearch)}
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
                  {/* Bo'sh joyni NOMI ustuni yutadi. Busiz jadval besh ustunga
                      tushgach konteynerni to'ldirish uchun cho'zilib, Narx bilan
                      amallar orasida katta bo'shliq qolardi. */}
                  <TableHead className="whitespace-nowrap">Kod</TableHead>
                  <TableHead className="w-full">Nomi</TableHead>
                  {/* "Guruh" ustuni YO'Q: u kod prefiksida (F-RC-001 -> F-RC),
                      tanlangan guruh esa tepadagi ro'yxatda ko'rinib turadi.
                      "Min" ham alohida ustun emas — qoldiq katagining ostida. */}
                  <TableHead className="whitespace-nowrap text-right">
                    Qoldiq
                  </TableHead>
                  <TableHead className="whitespace-nowrap text-right">
                    Narx
                  </TableHead>
                  {/* Yopishqoq ustun OLIB TASHLANDI: `bg-card` qatorning
                      o'z foni va `hover` holati bilan mos kelmasdi, natijada
                      amallar ustuni butun jadval bo'ylab boshqa rangda ko'rinib,
                      vertikal chiziq yasardi. Guruh va Min ustunlari ketgach
                      jadval besh ustunga tushdi va odatdagi ekranda sig'adi,
                      ya'ni yopishqoqlik faqat zarar keltirardi. */}
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
                        <div className="text-2xs text-muted-foreground">
                          {num(i.min_qty) > 0
                            ? `min ${qty(i.min_qty)}`
                            : "\u00a0"}
                        </div>
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
                  <EmptyRow colSpan={5}>
                    {debounced || group || low
                      ? "Shu shartga mos tovar yo'q."
                      : "Katalog bo'sh — \"Tovar qo'shish\" bilan boshlang."}
                  </EmptyRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}

        {/* 638 tovardan 100 tasi ko'rsatiladi. Busiz sahifa o'zining bosh
            vazifasida yolg'on gapirardi: "296 tovar past" deb yozib, bosilsa
            100 tasini ko'rsatardi va omborchi qolgan 196 tasini kam buyurtma
            qilardi. */}
        {total > 0 && (
          <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
            <span className="text-sm text-muted-foreground">
              <span className="num">{total}</span> tadan{" "}
              <span className="num">
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)}
              </span>
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page === 0}
              onClick={() => setPage((n) => n - 1)}
            >
              Oldingi
            </Button>
            <span className="num text-sm text-muted-foreground">
              {page + 1} / {pages}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page + 1 >= pages}
              onClick={() => setPage((n) => n + 1)}
            >
              Keyingi
            </Button>
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
