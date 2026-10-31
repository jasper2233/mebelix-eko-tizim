// Materialni sexga berish (EKO TZ §4.4): omborchi buyurtmani tanlaydi va list/rulon yorlig'ini
// skanerlaydi. Kromka ruloni sexga o'tadi va sexda qoladi — keyingi buyurtma avval undan oladi
// (varaqada «sexda» ustuni). Furnitura — katalog kodi yoki zavod shtrix-kodi + son.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  BellRing,
  CheckCircle2,
  ScanLine,
  TriangleAlert,
  Undo2,
} from "lucide-react"
import { useRef, useState } from "react"

import {
  type BerishOrder,
  type BerishRead,
  type BirlikRead,
  OmborService,
} from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { formatDateTime, isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { fmtQty, num, parseNum } from "@/lib/warehouse"
import { extractErrorMessage, handleError } from "@/utils"

export const Route = createFileRoute("/_layout/warehouse/berish")({
  component: BerishPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Material berish | MebeliX" }] }),
})

function BerishPage() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Material berish"
        description="Kroy bo'yicha materialni sexga skaner bilan berish. Kromka ruloni sexda qoladi — keyingi buyurtmalar avval undan oladi."
      />
      <Tabs defaultValue="buyurtmalar">
        <TabsList>
          <TabsTrigger value="buyurtmalar">Buyurtmalar</TabsTrigger>
          <TabsTrigger value="sex">Sexdagi rulonlar</TabsTrigger>
        </TabsList>
        <TabsContent value="buyurtmalar">
          <Navbat />
        </TabsContent>
        <TabsContent value="sex">
          <SexRulonlar />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function Navbat() {
  const queryClient = useQueryClient()
  const { currentUser } = useCurrentUser()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["ombor", "berish"],
    queryFn: async () => (await OmborService.listBerishOrders()).data,
    refetchInterval: 30_000,
  })
  // Sexdan so'rovlar (EKO TZ §4.4): arrachi/kromkachi terminaldan «Material so'rash» bosgan
  const { data: sorovlar } = useQuery({
    queryKey: ["ombor", "sorovlar"],
    queryFn: async () => (await OmborService.listMaterialSorovlar()).data,
    refetchInterval: 15_000,
  })
  const yopish = useMutation({
    mutationFn: (id: number) =>
      OmborService.closeMaterialSorov({ path: { sorov_id: id } }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["ombor", "sorovlar"] }),
    onError: handleError,
  })
  const [tanlangan, setTanlangan] = useState<number | null>(null)
  if (isError) return <QueryError onRetry={refetch} />
  if (isLoading) return <Skeleton className="h-40" />
  const rows = data ?? []
  const joriy = tanlangan ?? rows.find((r) => !r.tosiq)?.order_id ?? null
  return (
    <div className="flex flex-col gap-4">
      {(sorovlar ?? []).length > 0 && (
        <section className="rounded-lg border-2 border-amber-400 bg-amber-50 p-3">
          <h2 className="mb-2 flex items-center gap-2 font-semibold text-amber-900">
            <BellRing className="size-4" /> Sexdan so'rovlar ({sorovlar?.length}
            )
          </h2>
          <div className="flex flex-col gap-1">
            {sorovlar?.map((s) => (
              <div
                key={s.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm"
              >
                <button
                  type="button"
                  className="font-semibold underline"
                  onClick={() => setTanlangan(s.order_id)}
                >
                  {s.order_number}
                </button>
                <span>{POST_NOM[s.post] ?? s.post}</span>
                <span className="text-muted-foreground">
                  {formatDateTime(s.created_at)}
                  {s.created_by ? ` · ${s.created_by}` : ""}
                </span>
                {s.izoh && <span>«{s.izoh}»</span>}
                {isWarehouseWriter(currentUser) && (
                  <LoadingButton
                    size="sm"
                    variant="outline"
                    className="ml-auto"
                    loading={yopish.isPending && yopish.variables === s.id}
                    onClick={() => yopish.mutate(s.id)}
                  >
                    Yetkazildi
                  </LoadingButton>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
      <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
        <section className={cn(cardSurface, "flex flex-col gap-1 p-2")}>
          {rows.length === 0 && (
            <p className="p-3 text-sm text-muted-foreground">
              Berishni kutayotgan buyurtma yo'q
            </p>
          )}
          {rows.map((r) => (
            <NavbatRow
              key={r.order_id}
              r={r}
              active={r.order_id === joriy}
              onClick={() => setTanlangan(r.order_id)}
            />
          ))}
        </section>
        {joriy != null ? (
          <Varaqa orderId={joriy} />
        ) : (
          <section className={cn(cardSurface, "p-6 text-muted-foreground")}>
            Buyurtmani tanlang
          </section>
        )}
      </div>
    </div>
  )
}

const POST_NOM: Record<string, string> = {
  ARRA: "Arra — list",
  KROMKA: "Kromka — lenta",
  OVAL: "Oval kromka — lenta",
}

function NavbatRow({
  r,
  active,
  onClick,
}: {
  r: BerishOrder
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md px-3 py-2 text-left text-sm hover:bg-muted",
        active && "bg-primary/10",
      )}
    >
      <div className="flex items-center gap-2">
        <b>{r.order_number}</b>
        <span className="num ml-auto text-xs text-muted-foreground">
          {r.tayyor}/{r.qatorlar}
        </span>
      </div>
      <div className="truncate text-xs text-muted-foreground">
        {r.client ?? "—"}
      </div>
      {r.tosiq && (
        <div className="mt-0.5 text-xs text-amber-700">
          To'lov/ruxsat kutilmoqda
        </div>
      )}
    </button>
  )
}

type Xabar = { ok: boolean; text: string; warn: string[] }

function Varaqa({ orderId }: { orderId: number }) {
  const queryClient = useQueryClient()
  const { currentUser } = useCurrentUser()
  const canGive = isWarehouseWriter(currentUser)
  const key = ["ombor", "berish", orderId]
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: key,
    queryFn: async () =>
      (await OmborService.readBerishVaraqa({ path: { order_id: orderId } }))
        .data,
  })
  const [kod, setKod] = useState("")
  const [soni, setSoni] = useState("")
  const [xabar, setXabar] = useState<Xabar | null>(null)
  // Qaytarish rejimi (EKO 3f): kroy berilgandan keyin o'zgargan — ortiqchasi sexdan omborga skan bilan qaytadi
  const [qaytarish, setQaytarish] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const skan = useMutation({
    mutationFn: async () => {
      const opts = {
        path: { order_id: orderId },
        body: {
          kod: kod.trim(),
          qty: parseNum(soni) ? String(parseNum(soni)) : null,
        },
      }
      return (
        qaytarish
          ? await OmborService.berishQaytar(opts)
          : await OmborService.berishSkan(opts)
      ).data
    },
    onSuccess: (res) => {
      queryClient.setQueryData<BerishRead>(key, res.varaqa)
      queryClient.invalidateQueries({
        queryKey: ["ombor", "berish"],
        exact: true,
      })
      queryClient.invalidateQueries({ queryKey: ["ombor", "sorovlar"] })
      setXabar({ ok: true, text: res.xabar, warn: res.ogohlantirish })
      setKod("")
      setSoni("")
    },
    onError: (e) => {
      setXabar({ ok: false, text: extractErrorMessage(e), warn: [] })
      setKod("")
    },
    onSettled: () => inputRef.current?.focus(),
  })

  if (isError) return <QueryError onRetry={refetch} />
  if (isLoading || !data) return <Skeleton className="h-60" />
  // Furnitura berilganicha qaytadi: qo'lda xato ko'p kiritilgani shu yo'l bilan tuzatiladi
  const ortiqchaBor = data.lines.some(
    (l) =>
      l.item_id != null &&
      (num(l.berilgan) > num(l.kerak) ||
        (l.kind === "hardware" && num(l.berilgan) > 0)),
  )

  return (
    <section className={cn(cardSurface, "flex flex-col gap-3 p-4")}>
      <h2 className="font-semibold">
        {data.order_number}{" "}
        {data.holat === "sarflandi" && (
          <span className="ml-2 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-900">
            To'liq berilgan
          </span>
        )}
      </h2>
      {data.tosiq && (
        <div className="flex items-start gap-2 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <span>Material berilmaydi: {data.tosiq}</span>
        </div>
      )}
      {canGive && ortiqchaBor && (
        <div className="flex items-center gap-2 text-sm">
          <Button
            size="sm"
            variant={qaytarish ? "default" : "outline"}
            onClick={() => {
              setQaytarish(!qaytarish)
              setXabar(null)
            }}
          >
            <Undo2 className="size-4" />
            {qaytarish ? "Qaytarish rejimi yoqilgan" : "Omborga qaytarish"}
          </Button>
          {qaytarish && (
            <span className="text-amber-800">
              List — yorlig'ini skanerlang; rulon — yorlig'i va metr; furnitura
              — kodi va soni
            </span>
          )}
        </div>
      )}
      {canGive &&
        (qaytarish || (!data.tosiq && data.holat !== "sarflandi")) && (
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (kod.trim()) skan.mutate()
            }}
          >
            <ScanLine className="size-5 text-muted-foreground" />
            <Input
              ref={inputRef}
              autoFocus
              className="max-w-sm font-mono"
              placeholder="Yorliqni skanerlang (EK…) yoki furnitura kodi"
              value={kod}
              onChange={(e) => setKod(e.target.value)}
            />
            <Input
              className="num w-24 text-right"
              inputMode="decimal"
              placeholder="soni"
              title="Faqat furnitura uchun: nechta"
              value={soni}
              onChange={(e) => setSoni(e.target.value.replace(/[^0-9.,]/g, ""))}
            />
            <LoadingButton type="submit" loading={skan.isPending}>
              {qaytarish ? "Qaytarish" : "Berish"}
            </LoadingButton>
          </form>
        )}
      {xabar && (
        <div
          className={cn(
            "rounded border p-2 text-sm",
            xabar.ok
              ? "border-emerald-300 bg-emerald-50 text-emerald-900"
              : "border-red-300 bg-red-50 text-red-900",
          )}
        >
          <div className="flex items-start gap-2">
            {xabar.ok ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
            ) : (
              <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            )}
            <span>{xabar.text}</span>
          </div>
          {xabar.warn.map((w) => (
            <div key={w} className="mt-1 pl-6 font-semibold text-amber-800">
              {w}
            </div>
          ))}
        </div>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Material</TableHead>
            <TableHead className="text-right">Kerak</TableHead>
            <TableHead className="text-right">Berilgan</TableHead>
            <TableHead className="text-right">Qoldi</TableHead>
            <TableHead>Qayerdan</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.lines.length === 0 ? (
            <EmptyRow colSpan={5}>Rezerv yo'q</EmptyRow>
          ) : (
            data.lines.map((l) => {
              const tayyor = l.item_id != null && num(l.qoldi) <= 0
              return (
                <TableRow
                  key={l.line_id}
                  className={cn(tayyor && "text-muted-foreground")}
                >
                  <TableCell>
                    <div className={cn(tayyor && "line-through")}>{l.nom}</div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {l.code ??
                        (l.item_id == null ? "katalogga moslanmagan" : "")}
                    </div>
                  </TableCell>
                  <TableCell className="num text-right">
                    {fmtQty(l.kerak)} {l.unit ?? ""}
                  </TableCell>
                  <TableCell className="num text-right">
                    {fmtQty(l.berilgan)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "num text-right",
                      num(l.qoldi) > 0 && "font-semibold",
                    )}
                  >
                    {num(l.berilgan) > num(l.kerak) && l.item_id != null ? (
                      // Kroy berilgandan keyin o'zgargan: ortig'i sexda — omborga qaytarilishi kerak
                      <span className="text-xs font-semibold text-amber-700">
                        ortiqcha {fmtQty(num(l.berilgan) - num(l.kerak))}
                      </span>
                    ) : tayyor ? (
                      "✓"
                    ) : (
                      fmtQty(l.qoldi)
                    )}
                  </TableCell>
                  <TableCell className="text-xs">
                    <Qayerdan l={l} tayyor={tayyor} />
                  </TableCell>
                </TableRow>
              )
            })
          )}
        </TableBody>
      </Table>
    </section>
  )
}

function Qayerdan({
  l,
  tayyor,
}: {
  l: BerishRead["lines"][number]
  tayyor: boolean
}) {
  if (tayyor || l.item_id == null) return null
  if (!l.birlikli) return <span>katalog kodi + son</span>
  return (
    <div className="flex flex-col gap-0.5">
      {l.sexda.map((u) => (
        <span key={u.id} className="font-semibold text-emerald-800">
          sexda: <span className="font-mono">{u.barkod}</span> ·{" "}
          {fmtQty(u.qoldiq)} m
        </span>
      ))}
      <span className="text-muted-foreground">
        omborda {l.omborda} ta {l.rulon ? "rulon" : "birlik"}
        {num(l.yorliqsiz) > 0 && (
          <span className="text-amber-700">
            {" "}
            · yorliqsiz {fmtQty(l.yorliqsiz)}
          </span>
        )}
      </span>
    </div>
  )
}

function SexRulonlar() {
  const queryClient = useQueryClient()
  const { currentUser } = useCurrentUser()
  const canEdit = isWarehouseWriter(currentUser)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["ombor", "birliklar", "sex"],
    queryFn: async () =>
      (await OmborService.listBirliklar({ query: { joy: "sex" } })).data,
  })
  const done = () => queryClient.invalidateQueries({ queryKey: ["ombor"] })
  const tugadi = useMutation({
    mutationFn: (barkod: string) =>
      OmborService.birlikTugadi({ path: { barkod } }),
    onSuccess: done,
    onError: handleError,
  })
  const omborga = useMutation({
    mutationFn: (barkod: string) =>
      OmborService.birlikOmborga({ path: { barkod } }),
    onSuccess: done,
    onError: handleError,
  })
  if (isError) return <QueryError onRetry={refetch} />
  if (isLoading) return <Skeleton className="h-40" />
  const rows: BirlikRead[] = data ?? []
  return (
    <section className={cn(cardSurface, "p-4")}>
      <p className="mb-3 text-sm text-muted-foreground">
        Sexga berilgan, hali tugamagan rulonlar. Hisobdagi qoldiq kroy bo'yicha
        hisoblanadi; rulon amalda tugasa «Tugadi» — farq hisobdan chiqariladi.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Barkod</TableHead>
            <TableHead>Material</TableHead>
            <TableHead className="text-right">Rulon</TableHead>
            <TableHead className="text-right">Qoldiq (hisobda)</TableHead>
            <TableHead>Sexga berilgan</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <EmptyRow colSpan={6}>Sexda ochiq rulon yo'q</EmptyRow>
          ) : (
            rows.map((u) => (
              <TableRow key={u.id}>
                <TableCell className="font-mono">{u.barkod}</TableCell>
                <TableCell>
                  {u.item_name}
                  <div className="font-mono text-xs text-muted-foreground">
                    {u.item_code}
                  </div>
                </TableCell>
                <TableCell className="num text-right">
                  {fmtQty(u.hajm)} {u.unit ?? ""}
                </TableCell>
                <TableCell className="num text-right font-semibold">
                  {fmtQty(u.qoldiq)} {u.unit ?? ""}
                </TableCell>
                <TableCell className="text-xs">
                  {u.sexga_at ? formatDateTime(u.sexga_at) : "—"}
                </TableCell>
                <TableCell className="text-right">
                  {canEdit && u.barkod && (
                    <div className="flex justify-end gap-2">
                      <LoadingButton
                        size="sm"
                        variant="outline"
                        loading={
                          omborga.isPending && omborga.variables === u.barkod
                        }
                        onClick={() => omborga.mutate(u.barkod as string)}
                      >
                        Omborga
                      </LoadingButton>
                      <LoadingButton
                        size="sm"
                        variant="outline"
                        loading={
                          tugadi.isPending && tugadi.variables === u.barkod
                        }
                        onClick={() => tugadi.mutate(u.barkod as string)}
                      >
                        Tugadi
                      </LoadingButton>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </section>
  )
}
