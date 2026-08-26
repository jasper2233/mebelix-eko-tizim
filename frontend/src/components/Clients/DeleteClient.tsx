import { useMutation, useQueryClient } from "@tanstack/react-query"

import { type ClientRead, ClientsService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { crudCallbacks } from "@/queries/mes"

export function DeleteClient({
  client,
  onClose,
}: {
  client: ClientRead | null
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const cb = crudCallbacks(queryClient, ["clients"], "Mijoz o'chirildi")
  const mutation = useMutation({
    mutationFn: (id: number) =>
      ClientsService.deleteClient({ path: { client_id: id } }),
    ...cb,
    onSuccess: () => {
      cb.onSuccess()
      onClose()
    },
  })
  return (
    <ConfirmDialog
      open={!!client}
      onOpenChange={(v) => !v && onClose()}
      title="Mijozni o'chirish"
      // Buyurtmasi bor mijozni server 409 bilan rad etadi va nechta ekanini
      // aytadi — bu yerda takrorlanmaydi, aks holda ikki joyda qoida yuritilardi
      description={
        client
          ? `${client.full_name} reestrdan chiqadi. Buyurtmasi bor mijozni o'chirib bo'lmaydi — avval ularni boshqa mijozga o'tkazish yoki bekor qilish kerak.`
          : ""
      }
      confirmText="O'chirish"
      destructive
      loading={mutation.isPending}
      onConfirm={() => client && mutation.mutate(client.id)}
    />
  )
}
