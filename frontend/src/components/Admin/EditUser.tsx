import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { type UserAdminUpdate, type UserRead, UsersService } from "@/client"
import {
  buildUserFormSchema,
  isMachineBoundRole,
  type UserFormData,
  UserFormFields,
} from "@/components/Admin/UserForm"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Form } from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { formatUzPhone } from "@/lib/validation"
import { handleError } from "@/utils"

const formSchema = buildUserFormSchema(false)

interface EditUserProps {
  user: UserRead
  onSuccess: () => void
}

export function EditUser({ user, onSuccess }: EditUserProps) {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()

  const form = useForm<UserFormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      phone: formatUzPhone(user.phone),
      name: user.name ?? undefined,
      role: user.role,
      machine_id: user.machine_id ? String(user.machine_id) : "",
      is_superuser: user.is_superuser,
      is_active: user.is_active,
    },
  })

  const mutation = useMutation({
    mutationFn: (requestBody: UserAdminUpdate) =>
      UsersService.updateUser({
        userId: Number.parseInt(user.id, 10),
        requestBody,
      }),
    onSuccess: () => {
      toast.success("Foydalanuvchi muvaffaqiyatli yangilandi")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const onSubmit = (data: UserFormData) => {
    const payload: UserAdminUpdate = {
      phone: data.phone,
      name: data.name,
      role: data.role,
      // Stanok faqat terminal/tablo uchun; boshqa rolga o'tishda bog'lam uziladi
      machine_id:
        isMachineBoundRole(data.role) && data.machine_id
          ? Number(data.machine_id)
          : null,
      is_superuser: data.is_superuser,
      is_active: data.is_active,
    }
    if (data.password) {
      payload.password = data.password
    }
    mutation.mutate(payload)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        Foydalanuvchini tahrirlash
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
              <DialogTitle>Foydalanuvchini tahrirlash</DialogTitle>
              <DialogDescription>
                Foydalanuvchi ma'lumotlarini quyida yangilang.
              </DialogDescription>
            </DialogHeader>
            <UserFormFields form={form} passwordRequired={false} />
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Bekor qilish
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Saqlash
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
