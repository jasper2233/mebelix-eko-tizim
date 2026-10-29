// «Kroy» — buyurtmani MX Kroy da ochish (EKO TZ §6, K1 + K6). Backend MX da loyihani yaratadi yoki
// yangilaydi va MES foydalanuvchisi nomidan (SSO, RS256) kirish manzilini qaytaradi.
// Oyna so'rovdan OLDIN ochiladi: aks holda brauzer `await` dan keyingi `window.open` ni bloklaydi.

import { useMutation, useQuery } from "@tanstack/react-query"
import { Scissors } from "lucide-react"

import { IntegratsiyaService } from "@/client"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCurrentUser } from "@/hooks/useCurrentUser"
import { handleError } from "@/utils"

//: Backend `integratsiya/routes.py: KroyUser` bilan bir xil
const ROLLAR = new Set(["admin", "director", "texnolog", "manager"])

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
  if (!ruxsat || !data?.enabled) return null
  return (
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
  )
}
