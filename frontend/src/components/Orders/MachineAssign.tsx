// Ish markazi tanlovi (TZ 6.4.1): posts with several machines get an explicit manager choice.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { type OrderDetail, OrdersService } from "@/client"
import { SelectField } from "@/components/Common/SelectField"
import { Card } from "@/components/ui/card"
import { LoadingButton } from "@/components/ui/loading-button"
import { POST_COLORS } from "@/lib/mes"
import {
  crudCallbacks,
  getMachinesQueryOptions,
  getPostsQueryOptions,
} from "@/queries/mes"

export function MachineAssign({
  order,
  onSaved,
}: {
  order: OrderDetail
  onSaved: () => void
}) {
  const { data: posts } = useQuery(getPostsQueryOptions())
  const { data: machines } = useQuery(getMachinesQueryOptions())
  const [selection, setSelection] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(order.machine_assignments ?? {}).map(([k, v]) => [
        k,
        String(v),
      ]),
    ),
  )
  const queryClient = useQueryClient()
  const cb = crudCallbacks(
    queryClient,
    ["orders", order.id],
    "Ish markazlari biriktirildi",
  )

  const choiceposts = (posts ?? [])
    .filter((p) => p.requires_assignment_choice)
    .sort((a, b) => a.order_index - b.order_index)

  const mutation = useMutation({
    mutationFn: () =>
      OrdersService.assignOrderMachines({
        orderId: order.id,
        requestBody: {
          assignments: Object.fromEntries(
            Object.entries(selection)
              .filter(([, v]) => v)
              .map(([k, v]) => [k, Number(v)]),
          ) as never,
        },
      }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onSaved()
    },
  })

  if (!choiceposts.length) return null

  return (
    <Card className="mb-6 p-4">
      <h2 className="mb-3 text-base font-semibold">Ish markazi tanlovi</h2>
      <div className="flex flex-wrap items-end gap-4">
        {choiceposts.map((post) => {
          // Faqat AKTIV: ta'mirdagi/noaktivga server ham biriktirmaydi (409)
          const options = (machines ?? []).filter(
            (m) => m.post_id === post.id && m.status === "active",
          )
          return (
            <div key={post.id} className="min-w-[200px]">
              <div
                className="mb-1 text-2xs font-bold uppercase tracking-wider"
                style={{ color: POST_COLORS[post.code] }}
              >
                {post.code}
              </div>
              <SelectField
                value={selection[post.code] ?? ""}
                onChange={(v) =>
                  setSelection((prev) => ({ ...prev, [post.code]: v }))
                }
                placeholder={
                  options.length ? "Ish markazini tanlang" : "AKTIV markaz yo'q"
                }
                options={options.map((m) => ({
                  value: String(m.id),
                  label: m.name,
                }))}
              />
            </div>
          )
        })}
        <LoadingButton
          loading={mutation.isPending}
          disabled={!Object.values(selection).some(Boolean)}
          onClick={() => mutation.mutate()}
        >
          Biriktirish
        </LoadingButton>
      </div>
    </Card>
  )
}
