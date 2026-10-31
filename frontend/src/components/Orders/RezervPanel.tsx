// Buyurtmaning material rezervi (EKO TZ §4.3) — ofis darajasi (menejer, direktor, texnolog, skladchi).
// Kroy (.project) yuklanganda backend o'zi quradi; to'lov chegarasi (muddat + foiz) bajarilsa
// material buyurtmaga «yechiladi». To'siq bo'lsa — sababi va direktor ruxsati tugmasi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { ShieldCheck, TriangleAlert } from "lucide-react"

import { OmborService, type RezervRead } from "@/client"
import { SectionTitle } from "@/components/Common/SectionTitle"
import { Card } from "@/components/ui/card"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { formatDateTime, formatMoney, isManager } from "@/lib/mes"
import { cn } from "@/lib/utils"
import { fmtQty, num } from "@/lib/warehouse"
import { crudCallbacks } from "@/queries/mes"

//: Backend `services/rezerv.py` holatlari
const HOLAT: Record<string, { text: string; cls: string }> = {
  faol: {
    text: "Band qilingan — to'lov kutilmoqda",
    cls: "bg-amber-100 text-amber-900",
  },
  yechildi: {
    text: "Buyurtmaga biriktirilgan",
    cls: "bg-emerald-100 text-emerald-900",
  },
  muddati_otdi: {
    text: "Muddati o'tgan — material bo'shatilgan",
    cls: "bg-red-100 text-red-900",
  },
  sarflandi: { text: "Sarflangan", cls: "bg-muted text-muted-foreground" },
  bekor: { text: "Bekor qilingan", cls: "bg-muted text-muted-foreground" },
}

export function RezervPanel({ orderId }: { orderId: number }) {
  const queryClient = useQueryClient()
  const { currentUser: user } = useCurrentUser()
  const key = ["ombor", "rezerv", orderId]
  const { data, isLoading, isError } = useQuery({
    queryKey: key,
    // 404 = rezerv hali yo'q (fayl yuklanmagan yoki qoidadan oldingi buyurtma) — xato emas
    queryFn: async () =>
      (
        await OmborService.readOrderRezerv({
          path: { order_id: orderId },
          throwOnError: false,
        })
      ).data ?? null,
  })
  const cb = crudCallbacks(queryClient, key, "Rezerv yangilandi")
  const qayta = useMutation({
    mutationFn: () =>
      OmborService.rebuildOrderRezerv({ path: { order_id: orderId } }),
    ...cb,
  })
  const tasdiq = useMutation({
    mutationFn: () =>
      OmborService.approveOrderRezerv({ path: { order_id: orderId } }),
    ...crudCallbacks(queryClient, key, "Direktor ruxsati berildi"),
  })

  const isDirector = Boolean(
    user?.is_superuser || user?.role === "director" || user?.role === "admin",
  )
  const canRebuild = isManager(user) || user?.role === "texnolog"

  if (isLoading || isError) return null

  return (
    <Card className="mb-6 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <SectionTitle>Material rezervi</SectionTitle>
        {data && <HolatBadge holat={data.holat} />}
        <div className="ml-auto flex gap-2">
          {canRebuild && (
            <LoadingButton
              size="sm"
              variant="outline"
              loading={qayta.isPending}
              onClick={() => qayta.mutate()}
            >
              Qayta hisoblash
            </LoadingButton>
          )}
          {data?.tosiq && isDirector && (
            <LoadingButton
              size="sm"
              loading={tasdiq.isPending}
              onClick={() => tasdiq.mutate()}
            >
              <ShieldCheck className="size-4" />
              To'lovsiz ruxsat berish
            </LoadingButton>
          )}
        </div>
      </div>
      {data ? (
        <RezervBody data={data} />
      ) : (
        <p className="text-sm text-muted-foreground">
          Rezerv yo'q: kroy (.project) yuklanganda o'zi quriladi. Qoidadan oldin
          ochilgan buyurtmada «Qayta hisoblash» ni bosing.
        </p>
      )}
    </Card>
  )
}

function HolatBadge({ holat }: { holat: string }) {
  const h = HOLAT[holat] ?? { text: holat, cls: "bg-muted" }
  return (
    <span className={cn("rounded px-2 py-0.5 text-xs font-semibold", h.cls)}>
      {h.text}
    </span>
  )
}

function RezervBody({ data }: { data: RezervRead }) {
  const moslanmagan = data.lines.filter((l) => l.item_id == null).length
  return (
    <>
      <div className="mb-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span>
          To'langan: <b className="num">{formatMoney(data.tolangan)}</b> /{" "}
          <span className="num">{formatMoney(data.chegara)}</span> kerak
        </span>
        {data.holat === "faol" && (
          <span>
            Muddat: <b>{formatDateTime(data.muddat)}</b>
          </span>
        )}
        {data.tasdiq_at && (
          <span className="text-emerald-700">
            Direktor ruxsati: {formatDateTime(data.tasdiq_at)}
          </span>
        )}
      </div>
      {data.tosiq && (
        <div className="mb-3 flex items-start gap-2 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <span>{data.tosiq}</span>
        </div>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Material</TableHead>
            <TableHead className="text-right">Kerak</TableHead>
            <TableHead className="text-right">Band</TableHead>
            <TableHead className="text-right">Berilgan</TableHead>
            <TableHead className="text-right">Yetmaydi</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.lines.map((l) => {
            const yetmaydi = num(l.kerak_qty) - num(l.qoplangan_qty)
            // Band — omborda shu buyurtmaga ajratilgani (sexga hali berilmagan); berilgan — sexda
            const band = Math.max(num(l.qoplangan_qty) - num(l.berilgan_qty), 0)
            const ortiqcha = num(l.berilgan_qty) - num(l.kerak_qty)
            return (
              <TableRow key={l.id}>
                <TableCell>
                  <div>{l.item_name ?? l.tashqi_nom}</div>
                  {l.item_id == null ? (
                    <div className="text-xs text-amber-700">
                      Katalogga moslanmagan
                    </div>
                  ) : (
                    l.item_name !== l.tashqi_nom && (
                      <div className="text-xs text-muted-foreground">
                        faylda: {l.tashqi_nom}
                      </div>
                    )
                  )}
                </TableCell>
                <TableCell className="num text-right">
                  {l.item_id == null
                    ? `${fmtQty(l.fayl_qty)} ${l.fayl_birlik}`
                    : `${fmtQty(l.kerak_qty)} ${l.item_unit ?? ""}`}
                </TableCell>
                <TableCell className="num text-right">
                  {l.item_id == null ? "—" : band > 0 ? fmtQty(band) : "—"}
                </TableCell>
                <TableCell className="num text-right">
                  {num(l.berilgan_qty) > 0 ? fmtQty(l.berilgan_qty) : "—"}
                  {ortiqcha > 0 && (
                    <div className="text-xs font-semibold text-amber-700">
                      ortiqcha {fmtQty(ortiqcha)} — sexdan qaytarish
                    </div>
                  )}
                </TableCell>
                <TableCell
                  className={cn(
                    "num text-right",
                    yetmaydi > 0 && "font-semibold text-red-700",
                  )}
                >
                  {l.item_id == null
                    ? "—"
                    : yetmaydi > 0
                      ? fmtQty(yetmaydi)
                      : "—"}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      {moslanmagan > 0 && (
        <p className="mt-2 text-sm">
          {moslanmagan} ta material katalogga moslanmagan —{" "}
          <Link to="/warehouse/taminot" className="underline">
            Ta'minot sahifasida moslang
          </Link>
          .
        </p>
      )}
    </>
  )
}
