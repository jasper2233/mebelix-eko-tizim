// «Kroy» — buyurtmani MX Kroy da ochish (EKO TZ §6, K1 + K6). Backend MX da loyihani yaratadi yoki
// yangilaydi va MES foydalanuvchisi nomidan (SSO, RS256) kirish manzilini qaytaradi.
// Oyna so'rovdan OLDIN ochiladi: aks holda brauzer `await` dan keyingi `window.open` ni bloklaydi.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, Scissors } from "lucide-react"
import { toast } from "sonner"

import { IntegratsiyaService } from "@/client"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { handleError } from "@/utils"

//: Backend `integratsiya/routes.py: KroyUser` / `KroyTexnolog` bilan bir xil
const ROLLAR = new Set(["admin", "director", "texnolog", "manager"])
const YUKLOVCHI = new Set(["admin", "director", "texnolog"])

export function KroyButton({ orderId }: { orderId: number }) {
  const { currentUser: u } = useCurrentUser()
  const ruxsat = Boolean(u?.is_superuser || ROLLAR.has(u?.role ?? ""))
  const { data } = useQuery({
    queryKey: ["integ", "kroy", "holat"],
    queryFn: async () => (await IntegratsiyaService.kroyHolat()).data,
    enabled: ruxsat,
    staleTime: 5 * 60_000,
  })
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
  const queryClient = useQueryClient()
  // K2: MX dagi tayyor kroy (detallar, QR, xarita, qoldiq, sarf, stanok fayllari) — `.project` o'rnida
  const olish = useMutation({
    mutationFn: async () =>
      (await IntegratsiyaService.kroyOlish({ path: { order_id: orderId } }))
        .data,
    onSuccess: (r) => {
      toast.success(r.message)
      for (const w of (r.warnings ?? []).slice(0, 3)) toast.warning(w)
      queryClient.invalidateQueries({ queryKey: ["orders"] })
      queryClient.invalidateQueries({ queryKey: ["ombor"] })
    },
    onError: handleError,
  })
  if (!ruxsat || !data?.enabled) return null
  const yuklay = Boolean(u?.is_superuser || YUKLOVCHI.has(u?.role ?? ""))
  return (
    <>
      {yuklay && (
        <LoadingButton
          variant="outline"
          loading={olish.isPending}
          title="MX dagi tayyor kroyni buyurtmaga yuklash (.project o'rnida)"
          onClick={() => olish.mutate()}
        >
          <Download /> Kroyni olish
        </LoadingButton>
      )}
      <LoadingButton
        variant="outline"
        loading={ochish.isPending}
        onClick={() => {
          const w = window.open("about:blank", "_blank")
          if (w) w.opener = null
          ochish.mutate(w)
        }}
      >
        <Scissors /> Kroy (MX)
      </LoadingButton>
    </>
  )
}
