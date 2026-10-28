// Ta'minot ehtiyoji (EKO TZ §4.3, Q12, Q23): rezervlarda yetmayotgan materiallar — nima, qancha,
// nechta buyurtma kutyapti. Katalogga hali moslanmagan fayl materiallari ham shu yerda: bir marta
// pozitsiyaga bog'lanadi, keyingi buyurtmalarda o'zi topiladi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Link2 } from "lucide-react"
import { useMemo, useState } from "react"

import { OmborService, type ShortageRead } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Button } from "@/components/ui/button"
import { cardSurface } from "@/components/ui/card"
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { fmtQty, num, parseNum } from "@/lib/warehouse"
import { getCatalogAllQueryOptions } from "@/queries/mes"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/warehouse/taminot")({
  component: TaminotPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Ta'minot ehtiyoji | MebeliX" }] }),
})

const KIND_NOM: Record<string, string> = {
  sheet: "list",
  band: "kromka",
  hardware: "furnitura",
}

function TaminotPage() {
  const { currentUser } = useCurrentUser()
  const canMap = isWarehouseWriter(currentUser)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["ombor", "taminot"],
    queryFn: async () => (await OmborService.readSupplyNeeds()).data,
  })
  const [moslash, setMoslash] = useState<ShortageRead | null>(null)
  const rows = data ?? []
  const moslanmagan = rows.filter((r) => r.item_id == null)
  const yetmaydi = rows.filter((r) => r.item_id != null)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Ta'minot ehtiyoji"
        description="Buyurtmalarga band qilinishi kerak, lekin omborda yetmayotgan materiallar"
      />
      {isError ? (
        <QueryError onRetry={refetch} />
      ) : isLoading ? (
        <Skeleton className="h-40" />
      ) : (
        <>
          {moslanmagan.length > 0 && (
            <section className={cn(cardSurface, "p-4")}>
              <h2 className="mb-1 font-semibold">
                Katalogga moslanmagan materiallar ({moslanmagan.length})
              </h2>
              <p className="mb-3 text-sm text-muted-foreground">
                Loyiha faylidagi material qaysi katalog pozitsiyasi ekanini bir
                marta ko'rsating — keyingi buyurtmalarda o'zi topiladi.
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Fayldagi nomi</TableHead>
                    <TableHead>Turi</TableHead>
                    <TableHead className="text-right">Kerak</TableHead>
                    <TableHead className="text-right">Buyurtmalar</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {moslanmagan.map((r) => (
                    <TableRow key={`${r.kind}:${r.tashqi_kalit}`}>
                      <TableCell>
                        {r.nom}
                        {r.tashqi_kalit !== r.nom.toLowerCase() && (
                          <span className="ml-2 font-mono text-xs text-muted-foreground">
                            {r.tashqi_kalit}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>{KIND_NOM[r.kind ?? ""] ?? r.kind}</TableCell>
                      <TableCell className="num text-right">
                        {fmtQty(r.kerak)} {r.birlik}
                      </TableCell>
                      <TableCell className="num text-right">
                        {r.buyurtmalar}
                      </TableCell>
                      <TableCell className="text-right">
                        {canMap && (
                          <Button size="sm" onClick={() => setMoslash(r)}>
                            <Link2 className="size-4" />
                            Moslash
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </section>
          )}
          <section className={cn(cardSurface, "p-4")}>
            <h2 className="mb-3 font-semibold">Yetmayotgan materiallar</h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Material</TableHead>
                  <TableHead className="text-right">Kerak</TableHead>
                  <TableHead className="text-right">Band</TableHead>
                  <TableHead className="text-right">Yetmaydi</TableHead>
                  <TableHead className="text-right">Buyurtmalar</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {yetmaydi.length === 0 ? (
                  <EmptyRow colSpan={5}>Hamma rezerv to'liq qoplangan</EmptyRow>
                ) : (
                  yetmaydi.map((r) => (
                    <TableRow key={r.item_id}>
                      <TableCell>{r.nom}</TableCell>
                      <TableCell className="num text-right">
                        {fmtQty(r.kerak)} {r.birlik}
                      </TableCell>
                      <TableCell className="num text-right">
                        {fmtQty(r.qoplangan)}
                      </TableCell>
                      <TableCell className="num text-right font-semibold text-red-700">
                        {fmtQty(r.yetmaydi)}
                      </TableCell>
                      <TableCell className="num text-right">
                        {r.buyurtmalar}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </section>
        </>
      )}
      <MoslashDialog row={moslash} onClose={() => setMoslash(null)} />
    </div>
  )
}

function MoslashDialog({
  row,
  onClose,
}: {
  row: ShortageRead | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const { data: catalog } = useQuery({
    ...getCatalogAllQueryOptions(),
    enabled: row != null,
  })
  const [q, setQ] = useState("")
  const [itemId, setItemId] = useState<number | null>(null)
  const [koef, setKoef] = useState("1")
  const t = q.trim().toLowerCase()
  const hits = useMemo(
    () =>
      t.length < 2
        ? []
        : (catalog ?? [])
            .filter(
              (c) =>
                c.code.toLowerCase().includes(t) ||
                c.name.toLowerCase().includes(t),
            )
            .slice(0, 30),
    [catalog, t],
  )
  const chosen = catalog?.find((c) => c.id === itemId)
  const k = parseNum(koef)

  const save = useMutation({
    mutationFn: () =>
      OmborService.mapProjectMaterial({
        body: {
          kind: row?.kind as "sheet" | "band" | "hardware",
          tashqi_kalit: row?.tashqi_kalit ?? "",
          item_id: itemId as number,
          koef: String(k),
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ombor"] })
      close()
    },
    onError: handleError,
  })
  const close = () => {
    setQ("")
    setItemId(null)
    setKoef("1")
    onClose()
  }

  return (
    <Dialog open={row != null} onOpenChange={(o) => !o && close()}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Materialni katalogga moslash</DialogTitle>
          <DialogDescription>
            Faylda: «{row?.nom}» · {fmtQty(row?.kerak)} {row?.birlik}
          </DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          placeholder="Katalogdan qidirish: kod yoki nom (kamida 2 harf)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="max-h-64 overflow-y-auto rounded border">
          {hits.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setItemId(c.id)}
              className={cn(
                "flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-muted",
                c.id === itemId && "bg-primary/10 font-semibold",
              )}
            >
              <span className="w-28 shrink-0 font-mono text-xs">{c.code}</span>
              <span className="flex-1">{c.name}</span>
              <span className="text-xs text-muted-foreground">{c.unit}</span>
            </button>
          ))}
          {t.length >= 2 && hits.length === 0 && (
            <p className="p-3 text-sm text-muted-foreground">Topilmadi</p>
          )}
        </div>
        <label
          htmlFor="moslash-koef"
          className="flex items-center gap-3 text-sm"
        >
          <span className="flex-1">
            1 {row?.birlik} = necha {chosen?.unit ?? "katalog birligi"}?
            <span className="block text-xs text-muted-foreground">
              Birliklar bir xil bo'lsa — 1
            </span>
          </span>
          <Input
            id="moslash-koef"
            className="num w-28 text-right"
            value={koef}
            onChange={(e) => setKoef(e.target.value)}
          />
        </label>
        {chosen && k != null && k > 0 && (
          <p className="text-sm">
            Rezervga:{" "}
            <b className="num">
              {fmtQty(num(row?.kerak) * k)} {chosen.unit ?? ""}
            </b>{" "}
            «{chosen.name}»
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={close}>
            Bekor
          </Button>
          <LoadingButton
            loading={save.isPending}
            disabled={itemId == null || k == null || k <= 0}
            onClick={() => save.mutate()}
          >
            Moslash
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
