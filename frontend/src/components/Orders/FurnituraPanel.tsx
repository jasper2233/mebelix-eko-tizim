// Furniturani qo'lda qo'shish va sonini o'zgartirish; ro'yxatning o'zi — materiallar bilan birga `RezervPanel` da.
// Qo'shish klaviaturada tez: kod yoki nom → ↑↓ → Enter → soni → Enter, kursor yana qidiruvga qaytadi.
// Katalogda yo'q nomni ham qo'shsa bo'ladi: u «moslanmagan» bo'lib Ta'minot sahifasiga tushadi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, Plus, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import {
  type FurnituraQator,
  type FurnituraTaklif,
  OmborService,
} from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
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

/** Qo'shish qatori: qidiruv, takliflar, soni */
export function Qoshish({
  orderId,
  onDone,
}: {
  orderId: number
  onDone: () => void
}) {
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

export function SoniTahrir({
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
