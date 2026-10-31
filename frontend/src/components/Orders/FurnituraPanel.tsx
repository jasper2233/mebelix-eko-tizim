// Buyurtma furniturasi: fayldan kelgani (MX Kroy, `.project`) va qo'lda qo'shilgani bitta ro'yxatda.
// Qo'shish klaviaturada tez: kod yoki nom → ↑↓ → Enter → soni → Enter, kursor yana qidiruvga qaytadi.
// Katalogda yo'q nomni ham qo'shsa bo'ladi: u «moslanmagan» bo'lib Ta'minot sahifasiga tushadi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Check, Pencil, Plus, Trash2, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  type FurnituraQator,
  type FurnituraTaklif,
  OmborService,
} from "@/client"
import { useTasdiq } from "@/components/Common/useTasdiq"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

const fmt = (v: string | number) =>
  Number(v)
    .toLocaleString("ru-RU", { maximumFractionDigits: 3 })
    .replace(/ /g, " ")

export const furnituraKey = (orderId: number) => ["ombor", "furnitura", orderId]

export function useFurnitura(orderId: number) {
  return useQuery({
    queryKey: furnituraKey(orderId),
    queryFn: async () =>
      (await OmborService.readOrderFurnitura({ path: { order_id: orderId } }))
        .data,
  })
}

/** Rezerv holati: moslanmagan / yetmaydi / band / berilgan */
function RezervHolat({ q }: { q: FurnituraQator }) {
  if (!q.moslangan) {
    return (
      <Link
        to="/warehouse/taminot"
        className="text-xs text-amber-700 underline underline-offset-2"
      >
        Katalogga moslanmagan
      </Link>
    )
  }
  const yetmaydi = Number(q.kerak) - Number(q.qoplangan)
  return (
    <span className="num text-xs">
      {yetmaydi > 0 ? (
        <span className="font-semibold text-red-700">
          Yetmaydi: {fmt(yetmaydi)}
        </span>
      ) : Number(q.berilgan) > 0 ? (
        <span className="text-emerald-700">Berilgan: {fmt(q.berilgan)}</span>
      ) : (
        <span>Band: {fmt(q.qoplangan)}</span>
      )}
    </span>
  )
}

function Qoshish({ orderId, onDone }: { orderId: number; onDone: () => void }) {
  const [q, setQ] = useState("")
  const [tanlangan, setTanlangan] = useState<FurnituraTaklif | null>(null)
  const [katalogsiz, setKatalogsiz] = useState<string | null>(null)
  const [soni, setSoni] = useState("1")
  const [faol, setFaol] = useState(0)
  const [ochiq, setOchiq] = useState(false)
  const [izlash, setIzlash] = useState("")
  const qidiruv = useRef<HTMLInputElement>(null)
  const soniInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setIzlash(q.trim()), 150)
    return () => clearTimeout(t)
  }, [q])

  const { data: takliflar = [], isFetching } = useQuery({
    queryKey: ["ombor", "furnitura-qidir", izlash],
    queryFn: async () =>
      (await OmborService.furnituraQidir({ query: { q: izlash } })).data,
    enabled: izlash.length >= 2 && tanlangan == null && katalogsiz == null,
    staleTime: 30_000,
  })
  const matn = q.trim()
  // Oxirgi qator — katalogsiz qo'shish: faqat aniq mos kod yo'q bo'lsa
  const katalogsizQator =
    matn.length >= 2 &&
    !takliflar.some((t) => t.code.toLowerCase() === matn.toLowerCase())
  const jami = takliflar.length + (katalogsizQator ? 1 : 0)

  const tozala = () => {
    setQ("")
    setIzlash("")
    setTanlangan(null)
    setKatalogsiz(null)
    setSoni("1")
    setFaol(0)
    setOchiq(false)
    qidiruv.current?.focus()
  }
  const tanla = (i: number) => {
    const t = takliflar[i]
    if (t) {
      setTanlangan(t)
      setQ(`${t.code} · ${t.name}`)
    } else {
      setKatalogsiz(matn)
    }
    setOchiq(false)
    setSoni("1")
    setTimeout(() => {
      soniInput.current?.focus()
      soniInput.current?.select()
    })
  }

  const queryClient = useQueryClient()
  const qosh = useMutation({
    mutationFn: async () =>
      (
        await OmborService.addOrderFurnitura({
          path: { order_id: orderId },
          body: {
            item_id: tanlangan?.item_id ?? null,
            nom: tanlangan ? null : katalogsiz,
            soni: soni.replace(",", "."),
          },
        })
      ).data,
    onSuccess: (r) => {
      queryClient.setQueryData(furnituraKey(orderId), r)
      queryClient.invalidateQueries({ queryKey: ["ombor", "furnitura-qidir"] })
      if (r.ogoh) toast.warning(r.ogoh)
      else toast.success("Furnitura qo'shildi")
      onDone()
      tozala()
    },
    onError: handleError,
  })
  const soniSon = Number(soni.replace(",", "."))
  const tayyor =
    (tanlangan != null || katalogsiz != null) &&
    Number.isFinite(soniSon) &&
    soniSon > 0

  return (
    <div className="mb-3 flex flex-wrap items-start gap-2">
      <div className="relative min-w-72 flex-1">
        <Input
          ref={qidiruv}
          value={q}
          placeholder="Kod yoki nom: kamida 2 harf"
          aria-label="Furnitura qidirish"
          onChange={(e) => {
            setQ(e.target.value)
            setTanlangan(null)
            setKatalogsiz(null)
            setFaol(0)
            setOchiq(true)
          }}
          onFocus={() => setOchiq(true)}
          onBlur={() => setTimeout(() => setOchiq(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              tozala()
            } else if (ochiq && jami > 0 && e.key === "ArrowDown") {
              e.preventDefault()
              setFaol((f) => (f + 1) % jami)
            } else if (ochiq && jami > 0 && e.key === "ArrowUp") {
              e.preventDefault()
              setFaol((f) => (f - 1 + jami) % jami)
            } else if (ochiq && jami > 0 && e.key === "Enter") {
              e.preventDefault()
              tanla(faol)
            }
          }}
        />
        {ochiq && matn.length >= 2 && !tanlangan && !katalogsiz && (
          <div className="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-md border bg-popover shadow-md">
            {takliflar.map((t, i) => (
              <button
                type="button"
                key={t.item_id}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => tanla(i)}
                onMouseEnter={() => setFaol(i)}
                className={cn(
                  "flex w-full items-center gap-3 px-3 py-1.5 text-left text-sm",
                  i === faol && "bg-accent",
                )}
              >
                <span className="num w-28 shrink-0 text-xs text-muted-foreground">
                  {t.code}
                </span>
                <span className="min-w-0 flex-1 truncate">{t.name}</span>
                <span
                  className={cn(
                    "num shrink-0 text-xs",
                    Number(t.erkin) <= 0
                      ? "text-red-700"
                      : "text-muted-foreground",
                  )}
                >
                  {fmt(t.erkin)} {t.unit}
                </span>
              </button>
            ))}
            {takliflar.length === 0 && isFetching && (
              <div className="px-3 py-1.5 text-sm text-muted-foreground">
                Qidirilmoqda…
              </div>
            )}
            {katalogsizQator && (
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => tanla(takliflar.length)}
                onMouseEnter={() => setFaol(takliflar.length)}
                className={cn(
                  "flex w-full items-center gap-2 border-t px-3 py-1.5 text-left text-sm",
                  faol === takliflar.length && "bg-accent",
                )}
              >
                <Plus className="size-3.5 shrink-0" />
                <span className="truncate">
                  «{matn}» ni katalogsiz qo'shish
                </span>
              </button>
            )}
          </div>
        )}
      </div>
      <Input
        ref={soniInput}
        value={soni}
        inputMode="decimal"
        aria-label="Soni"
        className="num w-24 text-right"
        onChange={(e) => setSoni(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && tayyor) {
            e.preventDefault()
            qosh.mutate()
          } else if (e.key === "Escape") {
            tozala()
          }
        }}
      />
      <span className="self-center text-xs text-muted-foreground">
        {tanlangan?.unit ?? "dona"}
      </span>
      <LoadingButton
        loading={qosh.isPending}
        disabled={!tayyor}
        onClick={() => qosh.mutate()}
      >
        <Plus /> Qo'shish
      </LoadingButton>
    </div>
  )
}

function SoniTahrir({
  q,
  orderId,
  onDone,
}: {
  q: FurnituraQator
  orderId: number
  onDone: () => void
}) {
  const queryClient = useQueryClient()
  const [v, setV] = useState(String(Number(q.soni)).replace(".", ","))
  const saqla = useMutation({
    mutationFn: async () =>
      (
        await OmborService.updateOrderFurnitura({
          path: { order_id: orderId, qator_id: q.id ?? 0 },
          body: { soni: v.replace(",", ".") },
        })
      ).data,
    onSuccess: (r) => {
      queryClient.setQueryData(furnituraKey(orderId), r)
      onDone()
    },
    onError: handleError,
  })
  return (
    <span className="inline-flex items-center justify-end gap-1">
      <Input
        autoFocus
        value={v}
        inputMode="decimal"
        aria-label="Yangi soni"
        className="num h-7 w-20 text-right"
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") saqla.mutate()
          if (e.key === "Escape") onDone()
        }}
      />
      <Button
        size="icon"
        variant="ghost"
        className="size-7"
        title="Saqlash"
        onClick={() => saqla.mutate()}
      >
        <Check />
      </Button>
      <Button
        size="icon"
        variant="ghost"
        className="size-7"
        title="Bekor qilish"
        onClick={onDone}
      >
        <X />
      </Button>
    </span>
  )
}

export function FurnituraPanel({
  orderId,
  canEdit,
}: {
  orderId: number
  canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const { data } = useFurnitura(orderId)
  const [tasdiqOyna, sora] = useTasdiq()
  const [tahrir, setTahrir] = useState<number | null>(null)
  const rezervYangila = () =>
    queryClient.invalidateQueries({ queryKey: ["ombor", "rezerv", orderId] })
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
  const qatorlar = data?.qatorlar ?? []

  return (
    <div>
      {tasdiqOyna}
      {canEdit && <Qoshish orderId={orderId} onDone={rezervYangila} />}
      {qatorlar.length === 0 ? (
        <p className="rounded-md border p-6 text-center text-sm text-muted-foreground">
          Furnitura yo'q
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Kod</TableHead>
              <TableHead>Nomi</TableHead>
              <TableHead className="text-right">Soni</TableHead>
              <TableHead>Birlik</TableHead>
              <TableHead>Manba</TableHead>
              <TableHead>Rezerv</TableHead>
              {canEdit && <TableHead />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {qatorlar.map((q) => (
              <TableRow key={`${q.manba}-${q.id ?? q.kalit}`}>
                <TableCell className="num text-xs text-muted-foreground">
                  {q.code ?? "—"}
                </TableCell>
                <TableCell className="font-medium">{q.nom}</TableCell>
                <TableCell className="num text-right font-semibold">
                  {tahrir != null && tahrir === q.id ? (
                    <SoniTahrir
                      q={q}
                      orderId={orderId}
                      onDone={() => {
                        setTahrir(null)
                        rezervYangila()
                      }}
                    />
                  ) : (
                    fmt(q.soni)
                  )}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {q.birlik}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {q.manba === "qolda" ? `Qo'lda: ${q.kim ?? "—"}` : "Kroydan"}
                </TableCell>
                <TableCell>
                  <RezervHolat q={q} />
                </TableCell>
                {canEdit && (
                  <TableCell className="whitespace-nowrap text-right">
                    {q.id != null && (
                      <>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-7"
                          title="Sonini o'zgartirish"
                          onClick={() => setTahrir(q.id ?? null)}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-7 text-destructive"
                          title="O'chirish"
                          onClick={() => {
                            const id = q.id
                            if (id == null) return
                            sora({
                              title: `${q.nom} o'chirilsinmi?`,
                              description: `${fmt(q.soni)} ${q.birlik} ro'yxatdan chiqadi va rezervi bo'shaydi.`,
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
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
