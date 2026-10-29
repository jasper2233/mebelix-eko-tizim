// Qoldiq bo'laklari (EKO TZ §4.4): kroydan ortgan foydali list bo'laklari. Arra terminali ularga
// `ATX-…` yorlig'ini chiqaradi; omborchi shu yorliqni skanerlab qabul qiladi. Boshqa buyurtmaga
// berish — «Material berish» sahifasida xuddi shu skan bilan. Bo'lak qoldiqqa (`quantity`) kirmaydi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ScanLine } from "lucide-react"
import { useMemo, useState } from "react"

import { OmborService } from "@/client"
import { EmptyRow } from "@/components/Common/EmptyRow"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
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
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { requireAccess } from "@/lib/guards"
import { formatDateTime, isWarehouseStaff, isWarehouseWriter } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { num } from "@/lib/warehouse"
import { extractErrorMessage, handleError } from "@/utils"

export const Route = createFileRoute("/_layout/warehouse/bolaklar")({
  component: BolaklarPage,
  beforeLoad: requireAccess(isWarehouseStaff),
  head: () => ({ meta: [{ title: "Qoldiq bo'laklari | MebeliX" }] }),
})

function BolaklarPage() {
  const queryClient = useQueryClient()
  const { currentUser } = useCurrentUser()
  const canEdit = isWarehouseWriter(currentUser)
  const key = ["ombor", "bolaklar"]
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: key,
    queryFn: async () => (await OmborService.listBolaklar()).data,
  })
  const [kod, setKod] = useState("")
  const [q, setQ] = useState("")
  const [xabar, setXabar] = useState<{ ok: boolean; text: string } | null>(null)
  const qabul = useMutation({
    mutationFn: async () =>
      (await OmborService.qabulBolak({ body: { kod: kod.trim() } })).data,
    onSuccess: (b) => {
      setXabar({
        ok: true,
        text: `${b.barkod}: ${b.material_nom}, ${num(b.uzunlik)}×${num(b.eni)} mm — omborda`,
      })
      setKod("")
      queryClient.invalidateQueries({ queryKey: key })
    },
    onError: (e) => {
      setXabar({ ok: false, text: extractErrorMessage(e) })
      setKod("")
    },
  })
  const chiqit = useMutation({
    mutationFn: (id: number) =>
      OmborService.chiqitBolak({ path: { bolak_id: id } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
    onError: handleError,
  })
  const t = q.trim().toLowerCase()
  const rows = useMemo(
    () =>
      (data ?? []).filter(
        (b) =>
          !t ||
          b.material_nom.toLowerCase().includes(t) ||
          (b.item_name ?? "").toLowerCase().includes(t),
      ),
    [data, t],
  )

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Qoldiq bo'laklari"
        description="Kroydan ortgan foydali list bo'laklari. Arra yorlig'ini (ATX-…) skanerlab qabul qiling; boshqa buyurtmaga «Material berish» sahifasida skan bilan beriladi."
      />
      <section className={cn(cardSurface, "flex flex-col gap-3 p-4")}>
        <div className="flex flex-wrap items-center gap-2">
          {canEdit && (
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault()
                if (kod.trim()) qabul.mutate()
              }}
            >
              <ScanLine className="size-5 text-muted-foreground" />
              <Input
                autoFocus
                className="w-72 font-mono"
                placeholder="ATX-… yorlig'ini skanerlang"
                value={kod}
                onChange={(e) => setKod(e.target.value)}
              />
              <LoadingButton type="submit" loading={qabul.isPending}>
                Qabul
              </LoadingButton>
            </form>
          )}
          <Input
            className="ml-auto w-64"
            placeholder="Material bo'yicha qidirish"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        {xabar && (
          <div
            className={cn(
              "rounded border p-2 text-sm",
              xabar.ok
                ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                : "border-red-300 bg-red-50 text-red-900",
            )}
          >
            {xabar.text}
          </div>
        )}
        {isError ? (
          <QueryError onRetry={refetch} />
        ) : isLoading ? (
          <Skeleton className="h-40" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Yorliq</TableHead>
                <TableHead>Material</TableHead>
                <TableHead className="text-right">O'lcham, mm</TableHead>
                <TableHead>Qaysi kroydan</TableHead>
                <TableHead>Qabul</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <EmptyRow colSpan={6}>Omborda qoldiq bo'lagi yo'q</EmptyRow>
              ) : (
                rows.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell className="font-mono text-xs">
                      {b.barkod}
                    </TableCell>
                    <TableCell>
                      {b.item_name ?? b.material_nom}
                      {!b.item_id && (
                        <div className="text-xs text-amber-700">
                          katalogga moslanmagan
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="num text-right font-semibold">
                      {num(b.uzunlik)} × {num(b.eni)}
                    </TableCell>
                    <TableCell>{b.manba_order}</TableCell>
                    <TableCell className="text-xs">
                      {formatDateTime(b.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      {canEdit && (
                        <LoadingButton
                          size="sm"
                          variant="outline"
                          loading={
                            chiqit.isPending && chiqit.variables === b.id
                          }
                          onClick={() => chiqit.mutate(b.id)}
                        >
                          Chiqitga
                        </LoadingButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  )
}
