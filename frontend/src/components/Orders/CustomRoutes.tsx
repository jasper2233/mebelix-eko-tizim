// Nostandart detallar (TZ 6.3.3): matritsada "nostandart" deb belgilangan detallar
// ro'yxati. Texnolog jarayonni bosib tanlaydi, tanlangan TARTIB raqamlanadi
// (1, 2, 3...) va aynan shu ketma-ketlik ishlab chiqarish marshruti bo'ladi.
// Bitta jarayon takrorlanishi mumkin: kromka -> prisadka -> yana kromka.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { OrdersService } from "@/client"
import { Button } from "@/components/ui/button"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatSize, PROCESS_OPS, ROUTE_START_POSTS } from "@/lib/mes"
import { crudCallbacks, getOrderMatrixQueryOptions } from "@/queries/mes"

// Qadoqlash (15) va ombor (16) ro'yxatda YO'Q: ularni texnolog tanlamaydi — qadoqlashni anketadagi "Upakovka
// qilish" bayrog'i yoqilgan bo'lsa backend har detalga oxirgi qadam qilib o'zi
// qo'shadi. Tugma qo'yilsa ikkita manba paydo bo'lardi.
const CODES = Object.keys(PROCESS_OPS)
  .map(Number)
  .filter((c) => !["UPAKOVKA", "OMBOR"].includes(PROCESS_OPS[c].post))
  .sort((a, b) => a - b)

export function CustomRoutes({
  orderId,
  editable,
}: {
  orderId: number
  editable: boolean
}) {
  const { data: matrix, isLoading } = useQuery(
    getOrderMatrixQueryOptions(orderId),
  )
  // part_id -> jarayon kodlari TARTIB bilan. Faqat tegilgan detallar bu yerda.
  const [draft, setDraft] = useState<Record<number, number[]>>({})
  const queryClient = useQueryClient()
  const cb = crudCallbacks(
    queryClient,
    ["orders", orderId, "matrix"],
    "Marshrutlar saqlandi",
  )

  const mutation = useMutation({
    mutationFn: () =>
      OrdersService.editOrderMatrix({
        orderId,
        requestBody: {
          edits: Object.entries(draft).map(([partId, codes]) => ({
            part_id: Number(partId),
            stages: {},
            route_codes: codes,
          })),
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      setDraft({})
    },
  })

  if (isLoading) return <Skeleton className="h-48 w-full" />

  const parts = (matrix?.parts ?? []).filter((p) => p.is_custom)
  if (!parts.length) {
    return (
      <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
        Nostandart detal yo'q. Detallar matritsasida "Nostandart" ustunidan
        belgilang — shundan keyin bu yerda marshrutini chizasiz.
      </p>
    )
  }

  const codesOf = (partId: number, routes: { process_code: number }[]) =>
    draft[partId] ?? routes.map((r) => r.process_code)

  const toggle = (partId: number, current: number[], code: number) => {
    const at = current.lastIndexOf(code)
    // Oxirgi tanlovni qayta bosish — bekor qilish; boshqa holatda yangi qadam.
    const next =
      at === current.length - 1 && at >= 0
        ? current.slice(0, -1)
        : [...current, code]
    setDraft((prev) => ({ ...prev, [partId]: next }))
  }

  const dirty = Object.keys(draft).length > 0
  const badRoute = (codes: number[]) =>
    codes.length === 0 ||
    !ROUTE_START_POSTS.includes(PROCESS_OPS[codes[0]]?.post)
  // Saqlashni faqat TEGILGAN detallar bloklaydi: bir detalning marshrutini
  // saqlash uchun buyurtmadagi barcha nostandart detal to'ldirilgan bo'lishi
  // shart emas edi — texnolog ishni bo'lib-bo'lib kiritadi.
  const blocking = Object.entries(draft).filter(([, codes]) => badRoute(codes))
  const incomplete = parts.filter((p) => badRoute(codesOf(p.id, p.routes)))

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Jarayonni bosing — tanlangan tartibda raqamlanadi. Bir jarayonni qayta
          bosish yangi qadam qo'shadi; oxirgisini bosish bekor qiladi. Marshrut
          Arra yoki Rover'dan boshlanishi shart.
        </p>
        {editable && (
          <div className="flex items-center gap-2">
            {dirty && (
              <Button variant="ghost" size="sm" onClick={() => setDraft({})}>
                Bekor qilish
              </Button>
            )}
            <LoadingButton
              size="sm"
              loading={mutation.isPending}
              disabled={!dirty || blocking.length > 0}
              onClick={() => mutation.mutate()}
            >
              Saqlash
            </LoadingButton>
          </div>
        )}
      </div>

      {incomplete.length > 0 && (
        <p className="mb-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          {incomplete.length} detalning marshruti to'liq emas: yo bo'sh, yo Arra
          / Rover'dan boshlanmagan. Ishlab chiqarishga uzatib bo'lmaydi.
        </p>
      )}

      <div className="space-y-2">
        {parts.map((part) => {
          const codes = codesOf(part.id, part.routes)
          const bad = badRoute(codes)
          return (
            <div
              key={part.id}
              className="rounded-lg border p-3"
              style={
                bad ? { borderColor: "var(--status-cancelled)" } : undefined
              }
            >
              <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-medium">
                  {part.product_code}_{part.code}
                </span>
                <span className="text-xs text-muted-foreground">
                  {part.name}
                </span>
                <span className="num text-xs text-muted-foreground">
                  {formatSize(part.length, part.width, part.thickness)} ·{" "}
                  {part.count} dona
                </span>
                <span className="ml-auto num text-xs font-semibold">
                  {codes.length ? codes.join(" / ") : "marshrut tanlanmagan"}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {CODES.map((code) => {
                  const op = PROCESS_OPS[code]
                  // Qadam raqamlari: bitta jarayon bir necha marta tanlansa hammasi
                  const picks = codes
                    .map((c, i) => (c === code ? i + 1 : 0))
                    .filter(Boolean)
                  return (
                    <button
                      key={code}
                      type="button"
                      disabled={!editable}
                      onClick={() => toggle(part.id, codes, code)}
                      className={
                        picks.length
                          ? "rounded-md border border-primary bg-primary/10 px-2 py-1 text-xs font-medium"
                          : "rounded-md border px-2 py-1 text-xs text-muted-foreground hover:bg-muted disabled:hover:bg-transparent"
                      }
                      title={`${code} · ${op.post}`}
                    >
                      {picks.length > 0 && (
                        <span className="num mr-1 font-bold text-primary">
                          {picks.join(",")}
                        </span>
                      )}
                      {op.name}
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
