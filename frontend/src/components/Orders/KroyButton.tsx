// «Kroy» — buyurtmani MX Kroy da ochish (EKO TZ §6, K1 + K6). Backend MX da loyihani yaratadi yoki
// yangilaydi va MES foydalanuvchisi nomidan (SSO, RS256) kirish manzilini qaytaradi.
// Oyna so'rovdan OLDIN ochiladi: aks holda brauzer `await` dan keyingi `window.open` ni bloklaydi.
// `opener` saqlanadi: MX dagi «MES ga yuborish» shu oynaga xabar beradi va texnolog buyurtmaga qaytadi (`MxKroyQaytish`).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Scissors, TriangleAlert } from "lucide-react"
import { useEffect } from "react"
import { toast } from "sonner"

import { IntegratsiyaService } from "@/client"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { formatDateTime } from "@/lib/mes"
import { handleError } from "@/utils"

//: Backend `integratsiya/routes.py: KroyUser` bilan bir xil
const ROLLAR = new Set(["admin", "director", "texnolog", "manager"])

const useKroyHolat = (enabled: boolean) =>
  useQuery({
    queryKey: ["integ", "kroy", "holat"],
    queryFn: async () => (await IntegratsiyaService.kroyHolat()).data,
    enabled,
    staleTime: 5 * 60_000,
  })

/** MX oynasidan «kroy yuborildi» xabari: buyurtma ochiladi, fokus shu oynaga, MX oynasi yopiladi. `_layout` da bitta. */
export function MxKroyQaytish() {
  const { currentUser: u } = useCurrentUser()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data } = useKroyHolat(
    Boolean(u?.is_superuser || ROLLAR.has(u?.role ?? "")),
  )
  const mxOrigin = data?.mx_origin

  useEffect(() => {
    if (!mxOrigin) return
    const on = (e: MessageEvent) => {
      if (e.origin !== mxOrigin || e.data?.type !== "mx-kroy-yuborildi") return
      const orderId = Number(e.data.order_id)
      queryClient.invalidateQueries({ queryKey: ["orders"] })
      queryClient.invalidateQueries({ queryKey: ["ombor"] })
      queryClient.invalidateQueries({ queryKey: ["integ", "kroy", "versiya"] })
      navigate({
        to: "/orders/$orderId",
        params: { orderId: String(orderId) },
      })
      toast.success(
        `${e.data.order_number}: kroy qabul qilindi (${e.data.version}-versiya)`,
      )
      for (const w of (e.data.warnings ?? []).slice(0, 3)) toast.warning(w)
      window.focus()
      ;(e.source as Window | null)?.close()
    }
    window.addEventListener("message", on)
    return () => window.removeEventListener("message", on)
  }, [mxOrigin, navigate, queryClient])
  return null
}

/** Buyurtmadagi kroy versiyasi: kim, qachon; MX da qayta ochilgan bo'lsa ogohlantirish; qayta yuborilganda farq */
export function KroyVersiyaPanel({ orderId }: { orderId: number }) {
  const { currentUser: u } = useCurrentUser()
  const ruxsat = Boolean(u?.is_superuser || ROLLAR.has(u?.role ?? ""))
  const { data } = useQuery({
    queryKey: ["integ", "kroy", "versiya", orderId],
    queryFn: async () =>
      (
        await IntegratsiyaService.kroyVersiyalar({
          path: { order_id: orderId },
        })
      ).data,
    enabled: ruxsat,
  })
  const v = data?.versiyalar[0]
  if (!data || !v) return null
  return (
    <div className="mb-6 flex flex-col gap-2 rounded-md border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-medium">Kroy {v.versiya}-versiya</span>
        <span className="text-muted-foreground">
          {v.manba === "mx" ? "MX dan yuborgan" : "MES da olgan"}: {v.kim},{" "}
          {formatDateTime(v.vaqt)}
        </span>
        <span className="num text-muted-foreground">
          {v.listlar} list, {v.nusxalar} detal
        </span>
      </div>
      {data.qayta_ochilgan && (
        <div className="flex items-center gap-2 text-amber-800">
          <TriangleAlert className="size-4 shrink-0" />
          Loyiha MX da qayta ochilgan: bu kroy eskirgan bo'lishi mumkin. Yangi
          versiya yuborilishini kuting.
        </div>
      )}
      {data.farq.length > 0 && (
        <div>
          <div className="text-muted-foreground">
            {data.versiyalar[1]?.versiya}-versiyadan farqi:
          </div>
          <ul className="list-inside list-disc">
            {data.farq.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function KroyButton({ orderId }: { orderId: number }) {
  const { currentUser: u } = useCurrentUser()
  const ruxsat = Boolean(u?.is_superuser || ROLLAR.has(u?.role ?? ""))
  const { data, isPending } = useKroyHolat(ruxsat)
  const ochish = useMutation({
    mutationFn: async (w: Window | null) => {
      const res = (
        await IntegratsiyaService.kroyOchish({ path: { order_id: orderId } })
      ).data
      return { w, url: res.url }
    },
    onSuccess: ({ w, url }) => {
      if (w) w.location.href = url
      else window.location.href = url
    },
    onError: (e, w) => {
      w?.close()
      handleError(e)
    },
  })
  // Holat kelguncha joy band: aks holda qatordagi tugmalar yuklanish paytida siljiydi va bosish «Ishlab chiqarishga
  // uzatish» ga tushib ketadi (sinovda shunday bo'lgan)
  if (ruxsat && isPending) {
    return (
      <>
        <LoadingButton variant="outline" disabled>
          <Scissors /> Kroy (MX)
        </LoadingButton>
      </>
    )
  }
  if (!ruxsat || !data?.enabled) return null
  return (
    <>
      <LoadingButton
        variant="outline"
        loading={ochish.isPending}
        onClick={() => {
          ochish.mutate(window.open("about:blank", "_blank"))
        }}
      >
        <Scissors /> Kroy (MX)
      </LoadingButton>
    </>
  )
}
