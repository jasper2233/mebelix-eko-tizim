// Ish markazi tanlovi: posts with several machines get an explicit manager choice.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { type OrderDetail, OrdersService } from "@/client"
import { SelectField } from "@/components/Common/SelectField"
import { LoadingButton } from "@/components/ui/loading-button"
import { POST_COLORS } from "@/lib/mes"
import {
  crudCallbacks,
  getMachinesQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"

/** Tanlovlarni solishtirish uchun normal shakl: bo'sh (biriktirilmagan)
 *  qiymatlar tashlanadi, tartib barqaror. */
const norm = (s: Record<string, string>) =>
  JSON.stringify(
    Object.entries(s)
      .filter(([, v]) => v)
      .sort(),
  )

export function MachineAssign({ order }: { order: OrderDetail }) {
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { data: machines } = useQuery(getMachinesQueryOptions())
  const assigned = Object.fromEntries(
    Object.entries(order.machine_assignments ?? {}).map(([k, v]) => [
      k,
      String(v),
    ]),
  )
  const [selection, setSelection] = useState<Record<string, string>>(assigned)
  const queryClient = useQueryClient()
  // ["orders"] prefiksi buyurtmaning o'zini ham, reestrni ham qamraydi —
  // shuning uchun chaqiruvchida qo'shimcha invalidatsiya kerak emas.
  const cb = crudCallbacks(
    queryClient,
    ["orders"],
    "Ish markazlari biriktirildi",
  )

  const choiceposts = (posts ?? [])
    .filter((p) => p.requires_assignment_choice)
    .sort((a, b) => a.order_index - b.order_index)

  const mutation = useMutation({
    mutationFn: () =>
      OrdersService.assignOrderMachines({
        path: { order_id: order.id },
        body: {
          assignments: Object.fromEntries(
            Object.entries(selection)
              .filter(([, v]) => v)
              .map(([k, v]) => [k, Number(v)]),
          ) as never,
        },
      }),
    ...cb,
  })

  if (!choiceposts.length) return null

  return (
    // Bitta ixcham qator (karta emas): bitta select uchun sarlavhali karta
    // sahifada og'ir turardi.
    <div className="mb-6 flex flex-wrap items-center gap-3 text-sm">
      <span className="text-muted-foreground">Ish markazi:</span>
      {choiceposts.map((post) => {
        // Faqat AKTIV: ta'mirdagi/noaktivga server ham biriktirmaydi (409)
        const options = (machines ?? []).filter(
          (m) => m.post_id === post.id && m.status === "active",
        )
        return (
          <div key={post.id} className="flex items-center gap-2">
            <span
              className="text-2xs font-bold uppercase tracking-wider"
              style={{ color: POST_COLORS[post.code] }}
            >
              {post.code}
            </span>
            <SelectField
              className="h-8 w-56"
              value={selection[post.code] ?? ""}
              onChange={(v) =>
                setSelection((prev) => ({ ...prev, [post.code]: v }))
              }
              placeholder={
                options.length ? "Ish markazini tanlang" : "AKTIV markaz yo'q"
              }
              emptyLabel="Biriktirilmagan"
              options={options.map((m) => ({
                value: String(m.id),
                label: m.name,
              }))}
            />
          </div>
        )
      })}
      <LoadingButton
        size="sm"
        loading={mutation.isPending}
        // Faqat O'ZGARGANDA: "biror narsa tanlangan" sharti biriktirishni bekor qilishga yo'l bermasdi;
        // bo'sh tanlov ham yuboriladi (server dict'ni butunlay almashtiradi).
        disabled={norm(selection) === norm(assigned)}
        onClick={() => mutation.mutate()}
      >
        Biriktirish
      </LoadingButton>
    </div>
  )
}
