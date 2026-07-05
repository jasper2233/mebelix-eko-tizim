import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { UsersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface DeleteUserProps {
  id: string
  onSuccess: () => void
}

const DeleteUser = ({ id, onSuccess }: DeleteUserProps) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => UsersService.deleteUser({ userId: Number.parseInt(id) }),
    onSuccess: () => {
      showSuccessToast("Foydalanuvchi muvaffaqiyatli o'chirildi")
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
        Foydalanuvchini o'chirish
      </DropdownMenuItem>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Foydalanuvchini o'chirish"
        description={
          <>
            Bu foydalanuvchiga tegishli barcha elementlar ham{" "}
            <strong>butunlay o'chiriladi.</strong> Ishonchingiz komilmi? Bu
            amalni qaytarib bo'lmaydi.
          </>
        }
        confirmText="O'chirish"
        destructive
        loading={mutation.isPending}
        onConfirm={() => mutation.mutate()}
      />
    </>
  )
}

export default DeleteUser
