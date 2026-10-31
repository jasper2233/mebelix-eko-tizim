// Buyurtmaning materiallari va furniturasi bitta jadvalda, rezerv holati bilan (EKO TZ §4.3) — menejer, direktor,
// texnolog, skladchi. Kroy (.project) yuklanganda backend o'zi quradi; to'lov chegarasi (muddat + foiz) bajarilsa
// material buyurtmaga «yechiladi». To'siq bo'lsa — sababi va direktor ruxsati tugmasi.
// Furnitura qo'lda ham qo'shiladi (`FurnituraPanel`): qator rezervniki, qo'lda qismi tahrirlanadi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Pencil, ShieldCheck, Trash2, TriangleAlert } from "lucide-react"
import { useState } from "react"

import { type FurnituraQator, OmborService, type RezervRead } from "@/client"
import { useTasdiq } from "@/components/Common/useTasdiq"
import {
  furnituraKey,
  Qoshish,
  SoniTahrir,
  useFurnitura,
} from "@/components/Orders/FurnituraPanel"
import { Button } from "@/components/ui/button"
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
import { handleError } from "@/utils"

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

//: Jadval tartibi: avval materiallar, oxirida furnitura
const TUR: Record<string, { nom: string; tartib: number }> = {
  sheet: { nom: "List", tartib: 0 },
  band: { nom: "Kromka", tartib: 1 },
  linear: { nom: "Pogonaj", tartib: 2 },
  hardware: { nom: "Furnitura", tartib: 3 },
}

const rezervKey = (orderId: number) => ["ombor", "rezerv", orderId]

export function useRezerv(orderId: number, enabled = true) {
  return useQuery({
    queryKey: rezervKey(orderId),
    enabled,
    // 404 = rezerv hali yo'q (fayl yuklanmagan yoki qoidadan oldingi buyurtma) — xato emas
    queryFn: async () =>
      (
        await OmborService.readOrderRezerv({
          path: { order_id: orderId },
          throwOnError: false,
        })
      ).data ?? null,
  })
}

export function RezervPanel({
  orderId,
  canEdit,
}: {
  orderId: number
  canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const { currentUser: user } = useCurrentUser()
  const key = rezervKey(orderId)
  const { data, isLoading, isError } = useRezerv(orderId)
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
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium">Rezerv</span>
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
        <RezervBody data={data} orderId={orderId} canEdit={canEdit} />
      ) : (
        <>
          {canEdit && (
            <Qoshish
              orderId={orderId}
              onDone={() => queryClient.invalidateQueries({ queryKey: key })}
            />
          )}
          <p className="text-sm text-muted-foreground">
            Rezerv yo'q: kroy (.project) yuklanganda o'zi quriladi. Qoidadan
            oldin ochilgan buyurtmada «Qayta hisoblash» ni bosing.
          </p>
        </>
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

/** Furnitura qatorining manbasi: kroydan, qo'lda yoki ikkalasidan (miqdorlar qo'shilgan) */
function manbaMatni(fayl?: FurnituraQator, qolda?: FurnituraQator): string {
  if (fayl && qolda) {
    return `Kroydan ${fmtQty(fayl.soni)} + qo'lda ${fmtQty(qolda.soni)}: ${qolda.kim ?? "—"}`
  }
  return qolda ? `Qo'lda: ${qolda.kim ?? "—"}` : "Kroydan"
}

function RezervBody({
  data,
  orderId,
  canEdit,
}: {
  data: RezervRead
  orderId: number
  canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const { data: furnitura } = useFurnitura(orderId)
  const [tasdiqOyna, sora] = useTasdiq()
  const [tahrir, setTahrir] = useState<number | null>(null)
  const rezervYangila = () =>
    queryClient.invalidateQueries({ queryKey: rezervKey(orderId) })
  const ochir = useMutation({
    mutationFn: async (id: number) =>
      (
        await OmborService.deleteOrderFurnitura({
          path: { order_id: orderId, qator_id: id },
        })
      ).data,
    onSuccess: (r) => {
      queryClient.setQueryData(furnituraKey(orderId), r)
      rezervYangila()
    },
    onError: handleError,
  })
  const qatorlar = furnitura?.qatorlar ?? []
  const lines = [...data.lines].sort(
    (a, b) =>
      (TUR[a.kind]?.tartib ?? 9) - (TUR[b.kind]?.tartib ?? 9) ||
      (a.item_name ?? a.tashqi_nom).localeCompare(b.item_name ?? b.tashqi_nom),
  )
  const moslanmagan = data.lines.filter((l) => l.item_id == null).length
  return (
    <>
      {tasdiqOyna}
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
      {canEdit && <Qoshish orderId={orderId} onDone={rezervYangila} />}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Kod</TableHead>
            <TableHead>Material</TableHead>
            <TableHead>Turi</TableHead>
            <TableHead className="text-right">Kerak</TableHead>
            <TableHead className="text-right">Band</TableHead>
            <TableHead className="text-right">Berilgan</TableHead>
            <TableHead className="text-right">Yetmaydi</TableHead>
            <TableHead>Manba</TableHead>
            {canEdit && <TableHead />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((l) => {
            const biriki =
              l.kind === "hardware"
                ? qatorlar.filter((q) => q.kalit === l.tashqi_kalit)
                : []
            const fayl = biriki.find((q) => q.manba === "fayl")
            const qolda = biriki.find((q) => q.manba === "qolda")
            const yetmaydi = num(l.kerak_qty) - num(l.qoplangan_qty)
            // Band — omborda shu buyurtmaga ajratilgani (sexga hali berilmagan); berilgan — sexda
            const band = Math.max(num(l.qoplangan_qty) - num(l.berilgan_qty), 0)
            const ortiqcha = num(l.berilgan_qty) - num(l.kerak_qty)
            return (
              <TableRow key={l.id}>
                <TableCell className="num whitespace-nowrap text-xs text-muted-foreground">
                  {l.item_code ?? qolda?.code ?? fayl?.code ?? "—"}
                </TableCell>
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
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                  {TUR[l.kind]?.nom ?? l.kind}
                </TableCell>
                <TableCell className="num whitespace-nowrap text-right">
                  {qolda && tahrir === qolda.id ? (
                    <SoniTahrir
                      q={qolda}
                      orderId={orderId}
                      onDone={() => {
                        setTahrir(null)
                        rezervYangila()
                      }}
                    />
                  ) : l.item_id == null ? (
                    `${fmtQty(l.fayl_qty)} ${l.fayl_birlik}`
                  ) : (
                    `${fmtQty(l.kerak_qty)} ${l.item_unit ?? ""}`
                  )}
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
                <TableCell className="text-xs text-muted-foreground">
                  {l.kind === "hardware" ? manbaMatni(fayl, qolda) : "Kroydan"}
                </TableCell>
                {canEdit && (
                  <TableCell className="whitespace-nowrap text-right">
                    {qolda?.id != null && (
                      <>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-7"
                          title="Qo'lda qo'shilgan sonini o'zgartirish"
                          onClick={() => setTahrir(qolda.id ?? null)}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-7 text-destructive"
                          title="Qo'lda qo'shilganini o'chirish"
                          onClick={() => {
                            const id = qolda.id
                            if (id == null) return
                            sora({
                              title: `${qolda.nom} o'chirilsinmi?`,
                              description: `Qo'lda qo'shilgan ${fmtQty(qolda.soni)} ${qolda.birlik} ro'yxatdan chiqadi va rezervi bo'shaydi.`,
                              confirmText: "O'chirish",
                              destructive: true,
                              onConfirm: () => ochir.mutate(id),
                            })
                          }}
                        >
                          <Trash2 />
                        </Button>
                      </>
                    )}
                  </TableCell>
                )}
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
