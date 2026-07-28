import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { UsersService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const DeleteAccount = () => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { logout } = useAuth()

  const mutation = useMutation({
    mutationFn: () => UsersService.deleteUserMe(),
    onSuccess: () => {
      showSuccessToast("Hisobingiz muvaffaqiyatli o'chirildi")
      setOpen(false)
      logout()
    },
    onError: handleError(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["currentUser"] })
    },
  })

  return (
    <div className="max-w-md mt-4 rounded-lg border border-destructive/50 p-4">
      <h3 className="text-base font-semibold text-destructive">
        Hisobni o'chirish
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Hisobingiz va unga tegishli barcha ma'lumotlarni butunlay o'chiring.
      </p>
      <Button
        variant="destructive"
        className="mt-3"
        onClick={() => setOpen(true)}
      >
        Hisobni o'chirish
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Tasdiqlash kerak"
        description={
          <>
            Hisobingizdagi barcha ma'lumotlar{" "}
            <strong>butunlay o'chiriladi.</strong> Ishonchingiz komil bo'lsa,
            davom etish uchun <strong>"O'chirish"</strong> tugmasini bosing. Bu
            amalni qaytarib bo'lmaydi.
          </>
        }
        confirmText="O'chirish"
        destructive
        loading={mutation.isPending}
        onConfirm={() => mutation.mutate()}
      />
    </div>
  )
}

export default DeleteAccount
