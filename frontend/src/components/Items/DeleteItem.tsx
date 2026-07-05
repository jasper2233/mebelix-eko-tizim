import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { ItemsService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface DeleteItemProps {
  id: number
  onSuccess: () => void
}

const DeleteItem = ({ id, onSuccess }: DeleteItemProps) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => ItemsService.deleteItem({ id }),
    onSuccess: () => {
      showSuccessToast("Element muvaffaqiyatli o'chirildi")
      setOpen(false)
      onSuccess()
    },
    onError: handleError(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  return (
    <>
      <DropdownMenuItem
        variant="destructive"
        onSelect={(e) => e.preventDefault()}
        onClick={() => setOpen(true)}
      >
        <Trash2 />
        Elementni o'chirish
      </DropdownMenuItem>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Elementni o'chirish"
        description="Bu element butunlay o'chiriladi. Ishonchingiz komilmi? Bu amalni qaytarib bo'lmaydi."
        confirmText="O'chirish"
        destructive
        loading={mutation.isPending}
        onConfirm={() => mutation.mutate()}
      />
    </>
  )
}

export default DeleteItem
