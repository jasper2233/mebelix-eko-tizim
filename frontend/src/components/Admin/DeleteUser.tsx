import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { UsersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { handleError } from "@/utils"

interface DeleteUserProps {
  id: string
  onSuccess: () => void
}

export function DeleteUser({ id, onSuccess }: DeleteUserProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () =>
      UsersService.deleteUser({ userId: Number.parseInt(id, 10) }),
    onSuccess: () => {
      toast.success("Foydalanuvchi muvaffaqiyatli o'chirildi")
      setOpen(false)
      onSuccess()
    },
    onError: handleError,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
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
            Foydalanuvchi <strong>o'chirilgan deb belgilanadi</strong> va
            tizimga kira olmaydi. Ishonchingiz komilmi?
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
